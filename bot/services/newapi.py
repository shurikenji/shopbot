"""
bot/services/newapi.py — Client gọi NewAPI (đa server).
Hỗ trợ: get groups, create token, search token, update token.
Mỗi server có base_url, user_id_header, access_token riêng.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


def _headers(server: dict) -> dict[str, str]:
    """Tạo headers cho NewAPI request."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "New-Api-User": str(server["user_id_header"]),
        "Authorization": f"Bearer {server['access_token']}",
    }


async def get_groups(server: dict) -> dict[str, Any]:
    """
    Lấy danh sách groups từ server.
    GET {base_url}/api/user/self/groups
    Returns: {"Azure": {"desc":"...","ratio":0.3}, ...}
    """
    url = f"{server['base_url'].rstrip('/')}/api/user/self/groups"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=_headers(server), timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("success"):
                    return data.get("data", {})
                logger.error("get_groups failed: %s", data.get("message", "Unknown error"))
                return {}
    except Exception as e:
        logger.error("get_groups exception: %s", e)
        return {}


async def create_token(
    server: dict,
    quota: int,
    group: str,
    name: str,
    expired_time: int = -1,
) -> Optional[dict]:
    """
    Tạo token mới trên server.
    POST {base_url}/api/token/
    Body: {remain_quota, expired_time, unlimited_quota, model_limits_enabled, name, group, allow_ips}
    Returns: full response data dict hoặc None nếu lỗi.
    """
    url = f"{server['base_url'].rstrip('/')}/api/token/"
    body = {
        "remain_quota": quota,
        "expired_time": expired_time,
        "unlimited_quota": False,
        "model_limits_enabled": False,
        "name": name,
        "group": group,
        "allow_ips": "",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=body, headers=_headers(server),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    logger.info("Token created on %s: name=%s, quota=%d", server["name"], name, quota)
                    return data
                logger.error("create_token failed on %s: %s", server["name"], data.get("message"))
                return None
    except Exception as e:
        logger.error("create_token exception on %s: %s", server["name"], e)
        return None


async def search_token(
    server: dict,
    api_key: str,
) -> Optional[dict]:
    """
    Tìm token trên server bằng api_key.
    GET {base_url}/api/token/search?keyword=&token={api_key_without_sk_prefix}

    LƯU Ý: api_key gửi KHÔNG có prefix "sk-".
    Ví dụ key là "sk-abc123" thì token param = "abc123"

    Returns: token data dict hoặc None nếu không tìm thấy.
    """
    # Bỏ prefix "sk-" nếu có
    token_param = api_key
    if token_param.startswith("sk-"):
        token_param = token_param[3:]

    url = f"{server['base_url'].rstrip('/')}/api/token/search"
    params = {"keyword": "", "token": token_param}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=_headers(server),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    tokens = data.get("data", [])
                    if tokens:
                        # Tìm token khớp CHÍNH XÁC với chuỗi user nhập
                        for t in tokens:
                            if t.get("key") == token_param:
                                return t
                    logger.warning("search_token: no exact match for key on %s", server["name"])
                    return None
                logger.error("search_token failed on %s: %s", server["name"], data.get("message"))
                return None
    except Exception as e:
        logger.error("search_token exception on %s: %s", server["name"], e)
        return None



async def search_token_by_name(
    server: dict,
    name: str,
) -> Optional[dict]:
    """
    Tìm token trên server bằng tên (keyword).
    GET {base_url}/api/token/search?keyword={name}

    Dùng khi create_token không trả về key trong response.
    Returns: token data dict hoặc None.
    """
    url = f"{server['base_url'].rstrip('/')}/api/token/search"
    params = {"keyword": name}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=_headers(server),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    tokens = data.get("data", [])
                    if tokens and len(tokens) > 0:
                        # Tìm token có name khớp chính xác
                        for t in tokens:
                            if t.get("name") == name:
                                return t
                        # Fallback: trả token đầu tiên
                        return tokens[0]
                    return None
                logger.error("search_token_by_name failed on %s: %s", server["name"], data.get("message"))
                return None
    except Exception as e:
        logger.error("search_token_by_name exception on %s: %s", server["name"], e)
        return None


async def update_token(
    server: dict,
    token_id: int,
    remain_quota: int,
    name: Optional[str] = None,
    group: Optional[str] = None,
) -> Optional[dict]:
    """
    Cập nhật quota cho token.
    PUT {base_url}/api/token/
    Body: {id, remain_quota, name, group}
    Returns: updated token data dict hoặc None nếu lỗi.
    """
    url = f"{server['base_url'].rstrip('/')}/api/token/"
    body: dict[str, Any] = {
        "id": token_id,
        "remain_quota": remain_quota,
        "expired_time": -1,
    }
    if name is not None:
        body["name"] = name
    if group is not None:
        body["group"] = group

    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(
                url, json=body, headers=_headers(server),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    logger.info(
                        "Token %d updated on %s: remain_quota=%d",
                        token_id, server["name"], remain_quota,
                    )
                    return data.get("data")
                logger.error("update_token failed on %s: %s", server["name"], data.get("message"))
                return None
    except Exception as e:
        logger.error("update_token exception on %s: %s", server["name"], e)
        return None


async def get_token_quota(server: dict, api_key: str) -> Optional[int]:
    """
    Helper: lấy remain_quota hiện tại của token.
    Returns: remain_quota (int) hoặc None nếu lỗi.
    """
    token = await search_token(server, api_key)
    if token:
        return token.get("remain_quota")
    return None
