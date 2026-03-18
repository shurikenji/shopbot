"""
admin/routers/settings.py — Cài đặt MB/VietQR/Bot/AI (tất cả key-value editable).
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from admin.deps import get_templates
from bot.config import settings
from bot.services.ai_translator import get_translator
from db.queries.settings import get_settings_dict, set_setting

router = APIRouter(prefix="/settings", tags=["settings"])

_EDITABLE_KEYS = [
    "mb_api_url", "mb_api_key", "mb_username", "mb_password",
    "mb_account_no", "mb_account_name", "mb_bank_id",
    "poll_interval", "order_expire_min", "vietqr_template",
    "bot_name", "bot_description", "welcome_message", "support_url", "support_text",
    "pagination_size", "admin_telegram_ids", "admin_password",
    # AI settings
    "ai_provider", "ai_api_key", "ai_model", "ai_base_url", "ai_enabled",
]


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    all_settings = await get_settings_dict()
    templates = get_templates()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "all_settings": all_settings,
            "ai_providers": [
                {"value": "openai", "label": "OpenAI"},
                {"value": "openai_compatible", "label": "OpenAI Compatible (Ollama, LM Studio, etc.)"},
                {"value": "anthropic", "label": "Anthropic"},
                {"value": "gemini", "label": "Google Gemini"},
            ],
            "ai_models": {
                "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                "openai_compatible": ["llama3", "mistral", "qwen", "phi3", "gemma"],
                "anthropic": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-sonnet-20241022"],
                "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
            },
        },
    )


@router.post("/save")
async def settings_save(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse(settings.admin_login_path, status_code=303)

    form = await request.form()
    for key in _EDITABLE_KEYS:
        value = form.get(key)
        if value is not None:
            await set_setting(key, value)

    return RedirectResponse("/settings?saved=1", status_code=303)


@router.post("/ai/test")
async def test_ai_connection(request: Request):
    """Test AI connection."""
    if not request.session.get("admin"):
        return JSONResponse({"success": False, "message": "Unauthorized"})
    
    form = await request.form()
    api_key = form.get("api_key", "")
    provider = form.get("provider", "openai")
    model = form.get("model", "gpt-4o-mini")
    base_url = form.get("base_url", "")
    
    # Create temporary translator for testing
    from bot.services.ai_translator import AITranslator
    translator = AITranslator()
    translator.api_key = api_key
    translator.provider = provider
    translator.model = model
    translator.base_url = base_url
    translator.enabled = True
    
    success, message = await translator.test_connection()
    return JSONResponse({"success": success, "message": message})
