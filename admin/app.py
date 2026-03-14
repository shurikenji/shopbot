"""
admin/app.py — FastAPI app setup với Jinja2 templates + static files.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from bot.config import settings
from admin.deps import require_admin

_BASE_DIR = Path(__file__).resolve().parent


def create_admin_app() -> FastAPI:
    """Tạo FastAPI app cho admin panel."""
    app = FastAPI(title="ShopBot Admin", docs_url=None, redoc_url=None)

    # Session middleware cho login
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.admin_secret_key,
    )

    # Mount static files
    static_dir = _BASE_DIR / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "css").mkdir(parents=True, exist_ok=True)
    (static_dir / "js").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include routers
    from admin.routers.auth import router as auth_router
    from admin.routers.dashboard import router as dashboard_router
    from admin.routers.servers import router as servers_router
    from admin.routers.categories import router as categories_router
    from admin.routers.products import router as products_router
    from admin.routers.settings import router as settings_router
    from admin.routers.orders import router as orders_router
    from admin.routers.users import router as users_router
    from admin.routers.account_stock import router as account_stock_router
    from admin.routers.logs import router as logs_router
    from admin.routers.broadcast import router as broadcast_router

    app.include_router(auth_router)

    @app.get("/health")
    async def health_check():
        from bot.utils.time_utils import get_now_vn
        return {"status": "ok", "timestamp": get_now_vn().isoformat()}
    
    # Kẹp vòng bảo vệ require_admin cho TẤT CẢ các chức năng quản trị
    admin_deps = [Depends(require_admin)]
    app.include_router(dashboard_router, dependencies=admin_deps)
    app.include_router(servers_router, dependencies=admin_deps)
    app.include_router(categories_router, dependencies=admin_deps)
    app.include_router(products_router, dependencies=admin_deps)
    app.include_router(settings_router, dependencies=admin_deps)
    app.include_router(orders_router, dependencies=admin_deps)
    app.include_router(users_router, dependencies=admin_deps)
    app.include_router(account_stock_router, dependencies=admin_deps)
    app.include_router(logs_router, dependencies=admin_deps)
    app.include_router(broadcast_router, dependencies=admin_deps)

    return app
