"""
bot/handlers/flow_accounts.py — Luồng bán Tài Khoản & Dịch vụ Nâng Cấp.

Flow account_stocked:
  Catalog → Chọn SP → Tạo order → Thanh toán → Auto-deliver từ kho
  (Xử lý bởi catalog.py._handle_standard_product + payment_poller._process_account_stocked)

Flow service_upgrade:
  Catalog → Chọn SP → FSM nhập thông tin (email/password) → Tạo order → Thanh toán
  → Admin xử lý thủ công (Live Chat)
"""
from __future__ import annotations
from bot.utils.time_utils import get_now_vn
from datetime import timedelta
import json

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.callback_data.factories import BackCB
from bot.keyboards.inline_kb import payment_method_kb, products_kb, back_only_kb
from bot.services.pricing_resolver import quote_non_api_product
from bot.utils.formatting import format_vnd
from bot.utils.order_code import generate_order_code

from db.queries.products import get_product_by_id, get_active_products_by_category
from db.queries.orders import create_order, update_order_status
from db.queries.wallets import get_balance
from db.queries.settings import get_setting_int

router = Router(name="flow_accounts")


# ── FSM States ──────────────────────────────────────────────────────────────

class UpgradeStates(StatesGroup):
    waiting_user_input = State()  # Nhập thông tin cho upgrade (email, password, etc.)


# ── Middleware: lọc product_type cho router này ─────────────────────────────

# Chỉ handle product types: service_upgrade
# account_stocked đã được catalog.py._handle_standard_product xử lý tự động.
# Cần intercept ở catalog.py trước khi tới đây.


# In catalog.py, select_product calls _handle_standard_product for non-key types.
# For service_upgrade, we need to redirect to the FSM input flow first.
# We'll register a handler for ProductSelectCB that checks product_type.

# NOTE: Vì cùng xử lý ProductSelectCB, router này phải TRƯỚC catalog router
# trong dp.include_routers() để filter đúng. Hoặc ta dùng 1 approach khác:
# Catalog._handle_standard_product sẽ gọi hàm ở đây khi detect service_upgrade.

# Approach: Export hàm handle_upgrade_product cho catalog.py import.


def _build_upgrade_prompt_lines(product: dict, input_prompt: str) -> list[str]:
    lines = [
        f"🔧 <b>{product['name']}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: <b>{format_vnd(product['price_vnd'])}</b>",
    ]
    if product.get("description"):
        lines.append(f"📝 {product['description']}")

    lines.extend([
        "",
        f"❓ <b>{input_prompt}</b>",
        "",
        "✏️ Nhập thông tin bên dưới:",
    ])
    return lines


def _build_upgrade_payment_lines(
    product_name: str,
    price_vnd: int,
    user_input: str,
    order_code: str,
    balance: int,
    *,
    show_qr: bool,
) -> list[str]:
    lines = [
        f"🔧 <b>{product_name}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: <b>{format_vnd(price_vnd)}</b>",
        f"📝 Thông tin của bạn: <code>{user_input}</code>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🔖 Mã đơn: <code>{order_code}</code>",
        "",
        "Chọn phương thức thanh toán:",
        f"👛 Số dư ví: <b>{format_vnd(balance)}</b>",
    ]
    if not show_qr:
        lines.append("⚠️ Dưới 1.000đ chỉ hỗ trợ thanh toán bằng ví.")
    return lines


async def _show_category_products(callback: CallbackQuery, cat_id: int) -> None:
    if not cat_id:
        await callback.message.edit_text(
            "🛒 Danh mục sản phẩm",
            reply_markup=back_only_kb("cat"),
        )
        return

    products = await get_active_products_by_category(cat_id)
    if not products:
        await callback.message.edit_text(
            "📦 Danh mục trống.",
            reply_markup=back_only_kb("cat"),
        )
        return

    per_page = await get_setting_int("pagination_size", 6)
    await callback.message.edit_text(
        "📦 <b>Chọn sản phẩm</b>",
        reply_markup=products_kb(
            products,
            cat_id=cat_id,
            srv_id=0,
            ptype="general",
            page=0,
            per_page=per_page,
        ),
        parse_mode="HTML",
    )


async def handle_upgrade_product(
    callback: CallbackQuery,
    product: dict,
    state: FSMContext,
    _db_user: dict,
) -> None:
    """
    Xử lý sản phẩm dạng service_upgrade.
    Hỏi user nhập thông tin (email, OTP, etc.) trước khi tạo order.
    """
    input_prompt = product.get("input_prompt") or "Vui lòng nhập thông tin cần thiết:"
    await state.update_data(upgrade_product_id=product["id"])

    await callback.message.edit_text(
        "\n".join(_build_upgrade_prompt_lines(product, input_prompt)),
        reply_markup=back_only_kb("upgrade_back"),
        parse_mode="HTML",
    )
    await state.set_state(UpgradeStates.waiting_user_input)
    await callback.answer()


@router.message(UpgradeStates.waiting_user_input)
async def upgrade_user_input_received(
    message: Message,
    state: FSMContext,
    db_user: dict,
) -> None:
    """Nhận thông tin từ user → tạo order → hiện payment methods."""
    user_input = message.text.strip()

    if len(user_input) < 3:
        await message.answer(
            "❌ Thông tin quá ngắn. Vui lòng nhập đầy đủ.",
            reply_markup=back_only_kb("upgrade_back"),
        )
        return

    fsm_data = await state.get_data()
    product_id = fsm_data.get("upgrade_product_id")

    product = await get_product_by_id(product_id) if product_id else None
    if not product:
        await message.answer(
            "❌ Sản phẩm không tồn tại.",
            reply_markup=back_only_kb("cat"),
        )
        await state.clear()
        return

    await state.set_state(None)
    product_name = product.get("name") or "Dịch vụ"
    product_type = product.get("product_type") or "service_upgrade"
    quote = await quote_non_api_product(product, user_id=db_user["id"])
    price_vnd = quote.payable_amount

    # Tạo order
    order_code = generate_order_code()
    expire_min = await get_setting_int("order_expire_min", 30)
    expired_at = (get_now_vn() + timedelta(minutes=expire_min)).isoformat()

    order_id = await create_order(
        order_code=order_code,
        user_id=db_user["id"],
        product_id=product["id"],
        product_name=product_name,
        product_type=product_type,
        amount=price_vnd,
        payment_method="qr",
        expired_at=expired_at,
        base_amount=quote.base_amount,
        discount_amount=quote.discount_amount,
        cashback_amount=quote.cashback_amount,
        spend_credit_amount=quote.spend_credit_amount,
        pricing_snapshot=json.dumps(quote.pricing_snapshot, ensure_ascii=True),
        promotion_snapshot=(
            json.dumps(quote.promotion_snapshot, ensure_ascii=True)
            if quote.promotion_snapshot
            else None
        ),
    )

    # Lưu user_input vào order
    await update_order_status(
        order_id, "pending",
        user_input_data=user_input,
    )

    await state.update_data(current_order_id=order_id)

    # Hiện balance ví
    balance = await get_balance(db_user["id"])
    show_qr = price_vnd >= 1000

    await message.answer(
        "\n".join(
            _build_upgrade_payment_lines(
                product_name,
                price_vnd,
                user_input,
                order_code,
                balance,
                show_qr=show_qr,
            )
        ),
        reply_markup=payment_method_kb(order_id, show_qr=show_qr),
        parse_mode="HTML",
    )


@router.callback_query(BackCB.filter(F.target == "upgrade_back"))
async def back_from_upgrade_prompt(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Quay từ màn nhập thông tin dịch vụ về danh sách sản phẩm của danh mục."""
    fsm_data = await state.get_data()
    cat_id = fsm_data.get("current_cat_id", 0)

    await state.set_state(None)
    await _show_category_products(callback, cat_id)
    await callback.answer()
