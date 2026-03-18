"""Verification for admin server group routes without external API calls."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bot.config import settings
from db.database import close_db
from db.models import init_db
from db.queries.servers import create_server


class _FakeGroupClient:
    async def get_groups(self, server: dict) -> list[dict]:
        _ = server
        return [
            {
                "name": "premium",
                "ratio": 1.5,
                "desc": "Premium route",
                "category": "AI",
            }
        ]

    def get_supports_multi_group(self, server: dict) -> bool:
        _ = server
        return True


class _FakeTranslator:
    is_configured = True

    async def translate_groups(self, groups: list[dict], api_type: str) -> list[dict]:
        _ = api_type
        return [
            {
                **group,
                "label_en": "Premium",
                "label_vi": "Cao cấp",
                "desc_en": "Premium route",
            }
            for group in groups
        ]


async def _seed_manual_server() -> int:
    return await create_server(
        name="Manual Group Server",
        base_url="https://example.com",
        user_id_header="new-api-user",
        access_token="secret",
        price_per_unit=1000,
        quota_per_unit=1000,
        api_type="newapi",
        supports_multi_group=1,
        manual_groups="vip, standard",
    )


async def _seed_fetched_server() -> int:
    return await create_server(
        name="Fetched Group Server",
        base_url="https://example.com",
        user_id_header="new-api-user",
        access_token="secret",
        price_per_unit=1000,
        quota_per_unit=1000,
        api_type="newapi",
        supports_multi_group=1,
    )


async def main() -> None:
    original_db_path = settings.db_path

    with TemporaryDirectory() as temp_dir:
        temp_db = Path(temp_dir) / "server-groups.db"
        await close_db()
        object.__setattr__(settings, "db_path", str(temp_db))

        try:
            await init_db()
            manual_server_id = await _seed_manual_server()
            fetched_server_id = await _seed_fetched_server()

            from admin.app import create_admin_app
            from admin.deps import require_admin
            import admin.routers.servers as servers_router

            app = create_admin_app()
            app.dependency_overrides[require_admin] = lambda: {"admin": True}

            with TestClient(app) as client:
                preview_response = client.post(
                    "/servers/preview-groups",
                    data={
                        "name": "Preview Server",
                        "base_url": "https://example.com",
                        "price_per_unit": "1000",
                        "quota_per_unit": "1000",
                        "api_type": "newapi",
                        "manual_groups": "vip, standard",
                    },
                )
                assert preview_response.status_code == 200
                preview_payload = preview_response.json()
                assert preview_payload["success"] is True
                preview_names = [group["name"] for group in preview_payload["data"]]
                assert preview_names == ["vip", "standard"]
                print("[OK] preview_groups returns manual groups without external fetch")

                api_response = client.get(f"/servers/{manual_server_id}/api/groups")
                assert api_response.status_code == 200
                api_payload = api_response.json()
                assert api_payload["success"] is True
                assert set(api_payload["data"]) == {"vip", "standard"}
                print("[OK] api_servers_groups returns manual group lookup payload")

                page_response = client.get(f"/servers/{manual_server_id}/groups")
                assert page_response.status_code == 200
                page_text = page_response.text
                assert "Manual Group Server" in page_text
                assert "vip" in page_text
                assert "standard" in page_text
                print("[OK] servers_groups renders manual groups in admin HTML")

                original_get_api_client = servers_router.get_api_client
                original_get_translator = servers_router.get_translator
                servers_router.get_api_client = lambda server: _FakeGroupClient()

                async def _fake_get_translator() -> _FakeTranslator:
                    return _FakeTranslator()

                servers_router.get_translator = _fake_get_translator
                try:
                    fetched_api_response = client.get(f"/servers/{fetched_server_id}/api/groups")
                    assert fetched_api_response.status_code == 200
                    fetched_api_payload = fetched_api_response.json()
                    assert fetched_api_payload["success"] is True
                    assert fetched_api_payload["data"]["premium"]["label_vi"] == "Cao cấp"
                    print("[OK] api_servers_groups keeps fetched/translated group shape")

                    fetched_page_response = client.get(f"/servers/{fetched_server_id}/groups")
                    assert fetched_page_response.status_code == 200
                    fetched_page_text = fetched_page_response.text
                    assert "Fetched Group Server" in fetched_page_text
                    assert "premium" in fetched_page_text
                    print("[OK] servers_groups renders fetched groups via fake client")
                finally:
                    servers_router.get_api_client = original_get_api_client
                    servers_router.get_translator = original_get_translator

            print("\n=== SERVER GROUP VERIFICATION PASSED ===")
        finally:
            await close_db()
            object.__setattr__(settings, "db_path", original_db_path)


asyncio.run(main())
