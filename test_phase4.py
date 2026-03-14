"""Quick verification script for Phase 4."""
import asyncio
from db.models import init_db
from db.database import close_db


async def main():
    await init_db()

    # Test admin app creation
    from admin.app import create_admin_app
    app = create_admin_app()
    routes = [r.path for r in app.routes]
    print(f"[OK] admin app — {len(routes)} routes registered")

    # Test individual router imports
    from admin.routers.auth import router as r1
    print(f"[OK] auth router")
    from admin.routers.dashboard import router as r2
    print(f"[OK] dashboard router")
    from admin.routers.servers import router as r3
    print(f"[OK] servers router")
    from admin.routers.categories import router as r4
    print(f"[OK] categories router")
    from admin.routers.products import router as r5
    print(f"[OK] products router")
    from admin.routers.settings import router as r6
    print(f"[OK] settings router")
    from admin.routers.orders import router as r7
    print(f"[OK] orders router")
    from admin.routers.users import router as r8
    print(f"[OK] users router")
    from admin.routers.chatgpt_stock import router as r9
    print(f"[OK] chatgpt_stock router")
    from admin.routers.logs import router as r10
    print(f"[OK] logs router")
    from admin.routers.broadcast import router as r11
    print(f"[OK] broadcast router")

    # Test deps
    from admin.deps import get_templates, require_admin
    templates = get_templates()
    print(f"[OK] templates instance created")

    # Test templates exist
    import os
    tmpl_dir = os.path.join(os.path.dirname(__file__), "admin", "templates")
    tmpl_files = os.listdir(tmpl_dir)
    print(f"[OK] {len(tmpl_files)} template files found")

    # Test static files exist
    css_path = os.path.join(os.path.dirname(__file__), "admin", "static", "css", "style.css")
    js_path = os.path.join(os.path.dirname(__file__), "admin", "static", "js", "app.js")
    assert os.path.exists(css_path), "CSS missing"
    assert os.path.exists(js_path), "JS missing"
    print(f"[OK] static files: CSS + JS")

    await close_db()
    print("\n=== ALL PHASE 4 TESTS PASSED ===")


asyncio.run(main())
