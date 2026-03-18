"""
bot/services/api_clients/rixapi.py — RixAPI client implementation.
RixAPI servers use Rix-Api-User header and /api/token/group endpoint.
Supports multi-group natively.
"""
from __future__ import annotations

from typing import Any

from .base import BaseAPIClient


class RixAPIClient(BaseAPIClient):
    """Client for RixAPI servers."""
    
    @property
    def api_type(self) -> str:
        return "rixapi"

    @property
    def supports_multi_group(self) -> bool:
        """RixAPI natively supports multi-group."""
        return True

    def get_headers(self, server: dict) -> dict[str, str]:
        """RixAPI uses Rix-Api-User header."""
        headers = super().get_headers(server)
        
        # Override with RixAPI-specific header
        user_header = server.get("auth_user_header") or server.get("user_id_header") or "rix-api-user"
        user_value = server.get("auth_user_value") or server.get("user_id_header") or ""
        
        if user_value:
            headers[user_header] = str(user_value)
        
        return headers

    def get_groups_endpoint(self, server: dict) -> str:
        """RixAPI uses /api/token/group"""
        custom = server.get("groups_endpoint")
        if custom:
            return custom.rstrip("/")
        
        base = server.get("base_url", "").rstrip("/")
        return f"{base}/api/token/group"

    def parse_groups(self, data: dict) -> list[dict]:
        """
        Parse RixAPI groups response.
        
        RixAPI format: [{"group": "Azure", "ratio": 0.3, "desc": "..."}, ...]
        """
        groups = []
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    groups.append({
                        "name": item.get("group") or item.get("name") or "unknown",
                        "ratio": item.get("ratio") or item.get("multiplier") or 1.0,
                        "desc": item.get("desc") or item.get("description") or "",
                    })
        elif isinstance(data, dict):
            # Sometimes RixAPI returns object with group names as keys
            for name, info in data.items():
                if isinstance(info, dict):
                    groups.append({
                        "name": name,
                        "ratio": info.get("ratio", 1.0),
                        "desc": info.get("desc", ""),
                    })
                else:
                    groups.append({
                        "name": name,
                        "ratio": 1.0,
                        "desc": "",
                    })
        
        return groups

    def build_create_payload(
        self, quota: int, group: str, name: str, **kwargs
    ) -> dict[str, Any]:
        """
        Build RixAPI create payload.
        
        RixAPI supports TokenGroup for multi-group.
        """
        # Check if multi-group (comma-separated)
        is_multi = "," in group
        
        if is_multi:
            groups = [g.strip() for g in group.split(",")]
            return {
                "remain_quota": quota,
                "expired_time": kwargs.get("expired_time", -1),
                "name": name,
                "TokenGroup": groups,  # RixAPI uses TokenGroup array
            }
        else:
            return {
                "remain_quota": quota,
                "expired_time": kwargs.get("expired_time", -1),
                "name": name,
                "group": group,
            }

    def build_update_payload(
        self, current_data: dict, new_quota: int, **kwargs
    ) -> dict[str, Any]:
        """
        Build RixAPI update payload.
        
        CRITICAL: Preserve ALL fields, only change remain_quota.
        """
        payload = {
            "id": current_data.get("id"),
            "remain_quota": new_quota,
        }
        
        # Preserve all known fields
        for key in [
            "name", "group", "TokenGroup", "expired_time",
            "key", "user_id", "created_time", "updated_time",
            "status", "is_active", "mj_mode", "rate_limits",
        ]:
            if key in current_data:
                payload[key] = current_data[key]
        
        # Ensure expired_time
        if "expired_time" not in payload:
            payload["expired_time"] = -1
        
        return payload
