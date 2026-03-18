"""
bot/handlers/products.py — ⚠️ DEAD CODE / LEGACY FILE ⚠️

File này KHÔNG được đăng ký trong bot/handlers/__init__.py (setup_routers).
Toàn bộ logic đã được tách ra thành:
  - bot/handlers/catalog.py       (danh mục + sản phẩm chung)
  - bot/handlers/flow_api_key.py  (luồng mua/nạp API key)
  - bot/handlers/flow_accounts.py (luồng mua tài khoản)

Giữ lại file này chỉ để tham khảo. KHÔNG CHỈNH SỬA.
"""
from __future__ import annotations
from bot.utils.time_utils import get_now_vn

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.callback_data.factories import (
    CategoryPageCB, CategorySelectCB, KeyActionCB,
    ServerSelectCB, ProductPageCB, ProductSelectCB,
    PaymentMethodCB, OrderCancelCB, MyKeySelectCB, MyKeyInputCB,
    CustomAmountCB, BackCB,
)
from bot.keyboards.inline_kb import (
    categories_kb, key_action_kb, servers_kb,
    products_kb, payment_method_kb, my_keys_kb,
)
from bot.utils.formatting import format_vnd, mask_api_key, format_quota, format_dollar, quota_to_dollar
from bot.utils.order_code import generate_order_code
from bot.services.vietqr import build_qr_url, build_qr_caption
from bot.services.payment_poller import process_wallet_payment
from bot.services.newapi import search_token

logger = logging.getLogger(__name__)
from db.queries.categories import get_active_categories, get_category_by_id
from db.queries.products import get_active_products_by_category, get_product_by_id
from db.queries.servers import get_active_servers, get_server_by_id
from db.queries.orders import create_order, get_order_by_id
from db.queries.user_keys import get_user_keys, get_user_key_by_id
from db.queries.wallets import get_balance
from db.queries.settings import get_setting_int

router = Router(name="products")


# ── FSM States ──────────────────────────────────────────────────────────────

class ProductStates(StatesGroup):
    waiting_existing_key = State()  # Nhập key cũ khi topup
    waiting_custom_dollar = State()  # Nhập số $ tùy chọn


# ── 🛒 Sản phẩm → Danh mục ─────────────────────────────────────────────────

@router.message(F.text == "🛒 Sản phẩm")
async def show_categories(message: Message, state: FSMContext) -> None:
    """Hiện danh sách danh mục sản phẩm."""
    await state.clear()
    categories = await get_active_categories()

    if not categories:
        await message.answer("📦 Chưa có sản phẩm nào. Vui lòng quay lại sau!")
        return

    per_page = await get_setting_int("pagination_size", 6)
    await message.answer(
        "🛒 <b>Danh mục sản phẩm</b>\n\nChọn danh mục:",
        reply_markup=categories_kb(categories, page=0, per_page=per_page),
        parse_mode="HTML",
    )


# ── Phân trang danh mục ────────────────────────────────────────────────────

@router.callback_query(CategoryPageCB.filter())
async def categories_page(
    callback: CallbackQuery,
    callback_data: CategoryPageCB,
) -> None:
    """Chuyển trang danh mục."""
    categories = await get_active_categories()
    per_page = await get_setting_int("pagination_size", 6)
    await callback.message.edit_text(
        "🛒 <b>Danh mục sản phẩm</b>\n\nChọn danh mục:",
        reply_markup=categories_kb(categories, page=callback_data.page, per_page=per_page),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Chọn danh mục ──────────────────────────────────────────────────────────

@router.callback_query(CategorySelectCB.filter())
async def select_category(
    callback: CallbackQuery,
    callback_data: CategorySelectCB,
    state: FSMContext,
) -> None:
    """Xử lý chọn danh mục — phân luồng theo cat_type."""
    cat = await get_category_by_id(callback_data.id)
    if not cat:
        await callback.answer("❌ Danh mục không tồn tại.", show_alert=True)
        return

    # Lưu category vào FSM data cho back navigation
    await state.update_data(current_cat_id=cat["id"])

    if cat["cat_type"] == "key_api":
        # Hiện sub-menu: Mua key mới / Nạp key cũ
        await callback.message.edit_text(
            f"{cat.get('icon', '📦')} <b>{cat['name']}</b>\n\n"
            f"Chọn hành động:",
            reply_markup=key_action_kb(cat["id"]),
            parse_mode="HTML",
        )
    elif cat["cat_type"] == "chatgpt":
        # Hiện danh sách sản phẩm ChatGPT
        products = await get_active_products_by_category(cat["id"])
        if not products:
            await callback.message.edit_text(
                "📦 Chưa có sản phẩm ChatGPT. Vui lòng quay lại sau!",
            )
            await callback.answer()
            return

        per_page = await get_setting_int("pagination_size", 6)
        await callback.message.edit_text(
            f"{cat.get('icon', '📦')} <b>{cat['name']}</b>\n\nChọn sản phẩm:",
            reply_markup=products_kb(
                products, cat_id=cat["id"], srv_id=0,
                ptype="chatgpt", page=0, per_page=per_page,
            ),
            parse_mode="HTML",
        )
    else:
        # General: hiện sản phẩm trực tiếp
        products = await get_active_products_by_category(cat["id"])
        if not products:
            await callback.message.edit_text("📦 Danh mục trống.")
            await callback.answer()
            return

        per_page = await get_setting_int("pagination_size", 6)
        await callback.message.edit_text(
            f"{cat.get('icon', '📦')} <b>{cat['name']}</b>\n\nChọn sản phẩm:",
            reply_markup=products_kb(
                products, cat_id=cat["id"], srv_id=0,
                ptype="general", page=0, per_page=per_page,
            ),
            parse_mode="HTML",
        )
    await callback.answer()


# ── Key action: Mua mới / Nạp cũ → Chọn server ────────────────────────────

@router.callback_query(KeyActionCB.filter())
async def key_action(
    callback: CallbackQuery,
    callback_data: KeyActionCB,
    state: FSMContext,
) -> None:
    """Chọn action (new/topup) → hiện danh sách server."""
    action = callback_data.action  # 'new' | 'topup'
    await state.update_data(key_action=action, current_cat_id=callback_data.cat_id)

    servers = await get_active_servers()
    if not servers:
        await callback.message.edit_text("🖥 Chưa có server nào được cấu hình.")
        await callback.answer()
        return

    action_text = "🔑 Mua key mới" if action == "new" else "💳 Nạp key cũ"
    await callback.message.edit_text(
        f"{action_text}\n\nChọn server:",
        reply_markup=servers_kb(servers, action=action),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Chọn server ─────────────────────────────────────────────────────────────

@router.callback_query(ServerSelectCB.filter())
async def select_server(
    callback: CallbackQuery,
    callback_data: ServerSelectCB,
    state: FSMContext,
    db_user: dict,
) -> None:
    """Chọn server → hiện danh sách gói (key_new) hoặc chọn key (key_topup)."""
    action = callback_data.action
    server_id = callback_data.server_id

    server = await get_server_by_id(server_id)
    if not server:
        await callback.answer("❌ Server không tồn tại.", show_alert=True)
        return

    await state.update_data(current_server_id=server_id, key_action=action)
    fsm_data = await state.get_data()
    cat_id = fsm_data.get("current_cat_id", 0)

    if action == "topup":
        # Topup: hiện danh sách key hiện có + nút nhập mới
        keys = await get_user_keys(db_user["id"], server_id=server_id)
        await callback.message.edit_text(
            f"💳 <b>Nạp key cũ — {server['name']}</b>\n\n"
            f"Chọn key bạn muốn nạp thêm quota:",
            reply_markup=my_keys_kb(keys, server_id=server_id),
            parse_mode="HTML",
        )
    else:
        # New: hiện danh sách gói key_new
        ptype = "key_new"
        products = await get_active_products_by_category(
            cat_id, server_id=server_id, product_type=ptype
        )
        if not products:
            await callback.message.edit_text(
                f"📦 Chưa có gói cho server <b>{server['name']}</b>.",
                parse_mode="HTML",
            )
            await callback.answer()
            return

        per_page = await get_setting_int("pagination_size", 6)
        await callback.message.edit_text(
            f"🔑 <b>Mua key mới — {server['name']}</b>\n\nChọn gói:",
            reply_markup=products_kb(
                products, cat_id=cat_id, srv_id=server_id,
                ptype=ptype, page=0, per_page=per_page,
                action="new",
            ),
            parse_mode="HTML",
        )
    await callback.answer()


# ── Chọn key hiện có (topup) ───────────────────────────────────────────────

@router.callback_query(MyKeySelectCB.filter())
async def select_my_key(
    callback: CallbackQuery,
    callback_data: MyKeySelectCB,
    state: FSMContext,
    db_user: dict,
) -> None:
    """Chọn key hiện có → hiện danh sách gói topup."""
    key_row = await get_user_key_by_id(callback_data.key_id)
    if not key_row or key_row["user_id"] != db_user["id"]:
        await callback.answer("❌ Key không tồn tại.", show_alert=True)
        return

    await state.update_data(
        existing_key=key_row["api_key"],
        current_server_id=key_row["server_id"],
    )

    fsm_data = await state.get_data()
    cat_id = fsm_data.get("current_cat_id", 0)
    server_id = key_row["server_id"]

    # Hiện gói topup
    products = await get_active_products_by_category(
        cat_id, server_id=server_id, product_type="key_topup"
    )
    if not products:
        await callback.message.edit_text("📦 Chưa có gói nạp cho server này.")
        await callback.answer()
        return

    per_page = await get_setting_int("pagination_size", 6)
    await callback.message.edit_text(
        f"💳 <b>Nạp key</b>: <code>{mask_api_key(key_row['api_key'])}</code>\n\nChọn gói nạp:",
        reply_markup=products_kb(
            products, cat_id=cat_id, srv_id=server_id,
            ptype="key_topup", page=0, per_page=per_page,
            action="topup",
        ),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Nhập key mới (topup, FSM) ──────────────────────────────────────────────

@router.callback_query(MyKeyInputCB.filter())
async def input_key_prompt(
    callback: CallbackQuery,
    callback_data: MyKeyInputCB,
    state: FSMContext,
) -> None:
    """Yêu cầu nhập API key mới."""
    await state.update_data(current_server_id=callback_data.server_id)
    await callback.message.edit_text(
        "✏️ <b>Nhập API Key</b>\n\n"
        "Nhập API key bạn muốn nạp thêm quota:\n"
        "Ví dụ: <code>sk-abcdefghijklmn...</code>",
        parse_mode="HTML",
    )
    await state.set_state(ProductStates.waiting_existing_key)
    await callback.answer()


@router.message(ProductStates.waiting_existing_key)
async def input_key_received(
    message: Message,
    state: FSMContext,
    db_user: dict,
) -> None:
    """Nhận key từ user → kiểm tra key trên server → hiện gói topup."""
    api_key = message.text.strip()

    if len(api_key) < 30:
        await message.answer("❌ Key (mã token) quá ngắn. Vui lòng copy và dán đầy đủ key.")
        return

    fsm_data = await state.get_data()
    server_id = fsm_data.get("current_server_id", 0)
    cat_id = fsm_data.get("current_cat_id", 0)

    # Validate key tồn tại trên server
    server = await get_server_by_id(server_id)
    if not server:
        await message.answer("❌ Server không tồn tại.")
        await state.clear()
        return

    token_data = await search_token(server, api_key)
    if not token_data:
        await message.answer(
            "❌ <b>Key không tồn tại</b> trên server này.\n\n"
            "Vui lòng kiểm tra lại key và nhập lại.",
            parse_mode="HTML",
        )
        return  # Giữ FSM state để user nhập lại

    await state.update_data(existing_key=api_key)
    await state.set_state(None)

    # Hiện gói topup
    products = await get_active_products_by_category(
        cat_id, server_id=server_id, product_type="key_topup"
    )
    if not products:
        await message.answer("📦 Chưa có gói nạp cho server này.")
        return

    # Hiện số dư hiện tại của key
    current_quota = token_data.get("remain_quota", 0)
    mult = server.get("quota_multiple", 1.0) or 1.0
    current_dollar = quota_to_dollar(current_quota, mult)

    per_page = await get_setting_int("pagination_size", 6)
    await message.answer(
        f"💳 <b>Nạp key</b>: <code>{mask_api_key(api_key)}</code>\n"
        f"💵 Số dư hiện tại: <b>{current_dollar}</b>\n\nChọn gói nạp:",
        reply_markup=products_kb(
            products, cat_id=cat_id, srv_id=server_id,
            ptype="key_topup", page=0, per_page=per_page,
            action="topup",
        ),
        parse_mode="HTML",
    )


# ── Custom dollar amount ────────────────────────────────────────────────────

@router.callback_query(CustomAmountCB.filter())
async def custom_amount_prompt(
    callback: CallbackQuery,
    callback_data: CustomAmountCB,
    state: FSMContext,
) -> None:
    """Yêu cầu nhập số $ custom."""
    await state.update_data(
        key_action=callback_data.action,
        current_server_id=callback_data.server_id,
    )
    await callback.message.edit_text(
        "💵 <b>Nhập số dollar ($)</b>\n\n"
        "Nhập số $ bạn muốn nạp vào key:\n"
        "Ví dụ: <code>10</code> hoặc <code>25.5</code>",
        parse_mode="HTML",
    )
    await state.set_state(ProductStates.waiting_custom_dollar)
    await callback.answer()


@router.message(ProductStates.waiting_custom_dollar)
async def custom_dollar_received(
    message: Message,
    state: FSMContext,
    db_user: dict,
) -> None:
    """Nhận số $ → tính VNĐ → tạo order → hiện payment."""
    text = message.text.strip().replace(",", ".").replace("$", "")

    try:
        dollar_amount = float(text)
    except ValueError:
        await message.answer("❌ Vui lòng nhập số hợp lệ. Ví dụ: <code>10</code>", parse_mode="HTML")
        return

    if dollar_amount <= 0:
        await message.answer("❌ Số tiền phải lớn hơn 0.", parse_mode="HTML")
        return

    fsm_data = await state.get_data()
    server_id = fsm_data.get("current_server_id", 0)
    action = fsm_data.get("key_action", "new")
    existing_key = fsm_data.get("existing_key")

    server = await get_server_by_id(server_id)
    if not server:
        await message.answer("❌ Server không tồn tại.")
        await state.clear()
        return

    # Tính quota và VNĐ từ settings + server config
    multiple = server.get("quota_multiple", 1.0) or 1.0
    quota_per_unit = server.get("quota_per_unit", 500000)
    price_per_unit = server.get("price_per_unit", 31000)

    dollar_per_unit = server.get("dollar_per_unit", 10.0)
    if dollar_per_unit <= 0:
        dollar_per_unit = 10.0

    # Tỷ giá 1$ = giá 1 unit / số dollar 1 unit (VD: 31000 / 10 = 3100)
    price_per_dollar = price_per_unit / dollar_per_unit

    # Quota cho mỗi $ = quota 1 unit / dollar 1 unit
    quota_per_dollar_server = quota_per_unit / dollar_per_unit

    logger.info(
        "Custom dollar calc: $%.2f, price/unit=%d, $/unit=%.2f -> tỷ giá=%.2f",
        dollar_amount, price_per_unit, dollar_per_unit, price_per_dollar
    )

    # Quota chuyển vào API = $X * quota_per_dollar * multiple
    custom_quota = int(dollar_amount * quota_per_dollar_server * multiple)

    # VNĐ = Cứ thế nhân số dollar với tỷ giá
    vnd_amount = int(dollar_amount * price_per_dollar)

    # Tối thiểu 1,000₫ (giới hạn ngân hàng)
    if vnd_amount < 1000:
        vnd_amount = 1000

    logger.info(
        "Custom dollar result: quota=%d, vnd=%d",
        custom_quota, vnd_amount,
    )

    await state.set_state(None)

    # Tạo product type
    product_type = "key_new" if action == "new" else "key_topup"

    # Build detail text
    rate_vnd_per_dollar = int(price_per_dollar)
    lines = [
        f"💵 <b>Nạp ${dollar_amount:,.2f}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"💰 Cần thanh toán: <b>{format_vnd(vnd_amount)}</b>",
        f"📊 Tỷ giá: <b>{format_vnd(rate_vnd_per_dollar)}/$</b>",
        f"🖥 Server: <b>{server['name']}</b>",
    ]
    if existing_key:
        lines.append(f"🔑 Key nạp: <code>{mask_api_key(existing_key)}</code>")

    # Tạo order
    order_code = generate_order_code()
    expire_min = await get_setting_int("order_expire_min", 30)
    expired_at = (get_now_vn() + timedelta(minutes=expire_min)).isoformat()

    order_id = await create_order(
        order_code=order_code,
        user_id=db_user["id"],
        product_type=product_type,
        amount=vnd_amount,
        payment_method="qr",
        product_name=f"Custom ${dollar_amount:,.2f}",
        server_id=server_id,
        group_name=server.get("default_group") or None,
        existing_key=existing_key,
        custom_quota=custom_quota,
        expired_at=expired_at,
    )

    await state.update_data(current_order_id=order_id)

    # Hiện balance ví
    balance = await get_balance(db_user["id"])

    lines.extend([
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🔖 Mã đơn: <code>{order_code}</code>",
        f"\nChọn phương thức thanh toán:",
        f"👛 Số dư ví: <b>{format_vnd(balance)}</b>",
    ])

    # QR chỉ hiện khi mệnh giá VNĐ >= 1000₫ (Giới hạn của ngân hàng)
    show_qr = vnd_amount >= 1000

    if not show_qr:
        lines.append(f"⚠️ Dưới 1.000đ chỉ thanh toán bằng ví")

    await message.answer(
        "\n".join(lines),
        reply_markup=payment_method_kb(order_id, show_qr=show_qr),
        parse_mode="HTML",
    )


# ── Phân trang sản phẩm ────────────────────────────────────────────────────

@router.callback_query(ProductPageCB.filter())
async def products_page(
    callback: CallbackQuery,
    callback_data: ProductPageCB,
) -> None:
    """Chuyển trang danh sách sản phẩm."""
    cat_id = callback_data.cat_id
    srv_id = callback_data.srv_id
    ptype = callback_data.ptype

    products = await get_active_products_by_category(
        cat_id,
        server_id=srv_id if srv_id > 0 else None,
        product_type=ptype if ptype != "general" else None,
    )

    per_page = await get_setting_int("pagination_size", 6)
    await callback.message.edit_reply_markup(
        reply_markup=products_kb(
            products, cat_id=cat_id, srv_id=srv_id,
            ptype=ptype, page=callback_data.page, per_page=per_page,
        ),
    )
    await callback.answer()


# ── Chọn sản phẩm → Chi tiết + Thanh toán ──────────────────────────────────

@router.callback_query(ProductSelectCB.filter())
async def select_product(
    callback: CallbackQuery,
    callback_data: ProductSelectCB,
    state: FSMContext,
    db_user: dict,
) -> None:
    """Chọn sản phẩm → hiện chi tiết + nút thanh toán."""
    product = await get_product_by_id(callback_data.product_id)
    if not product:
        await callback.answer("❌ Sản phẩm không tồn tại.", show_alert=True)
        return

    # Kiểm tra stock
    if product["stock"] == 0:
        await callback.answer("❌ Sản phẩm đã hết hàng.", show_alert=True)
        return

    # Lấy thông tin server nếu có
    server_name = "N/A"
    if product.get("server_id"):
        server = await get_server_by_id(product["server_id"])
        if server:
            server_name = server["name"]

    # Lấy existing_key từ FSM nếu đang topup
    fsm_data = await state.get_data()
    existing_key = fsm_data.get("existing_key")

    # Build product detail text
    lines = [
        f"📦 <b>{product['name']}</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"💰 Giá: <b>{format_vnd(product['price_vnd'])}</b>",
    ]

    if product.get("description"):
        lines.append(f"📝 {product['description']}")
    if product.get("quota_amount") and product.get("server_id"):
        server_info = await get_server_by_id(product["server_id"])
        mult = server_info.get("quota_multiple", 1.0) if server_info else 1.0
        lines.append(f"💵 Số dư: <b>{quota_to_dollar(product['quota_amount'], mult)}</b>")
    elif product.get("quota_amount"):
        lines.append(f"💵 Số dư: <b>{quota_to_dollar(product['quota_amount'])}</b>")
    if product.get("dollar_amount"):
        lines.append(f"💵 Dollar: <b>{format_dollar(product['dollar_amount'])}</b>")
    if product.get("server_id"):
        lines.append(f"🖥 Server: <b>{server_name}</b>")
    if product.get("group_name"):
        lines.append(f"👥 Group: <b>{product['group_name']}</b>")
    if existing_key:
        lines.append(f"🔑 Key nạp: <code>{mask_api_key(existing_key)}</code>")

    stock_text = "Không giới hạn" if product["stock"] == -1 else str(product["stock"])
    lines.append(f"📦 Còn lại: <b>{stock_text}</b>")

    # Tạo order tạm (status=pending)
    order_code = generate_order_code()
    expire_min = await get_setting_int("order_expire_min", 30)
    expired_at = (get_now_vn() + timedelta(minutes=expire_min)).isoformat()

    order_id = await create_order(
        order_code=order_code,
        user_id=db_user["id"],
        product_id=product["id"],
        product_name=product["name"],
        product_type=product["product_type"],
        amount=product["price_vnd"],
        payment_method="qr",  # Default, sẽ update khi chọn
        server_id=product.get("server_id"),
        group_name=product.get("group_name"),
        existing_key=existing_key,
        expired_at=expired_at,
    )

    await state.update_data(current_order_id=order_id)

    lines.extend([
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🔖 Mã đơn: <code>{order_code}</code>",
        f"\nChọn phương thức thanh toán:",
    ])

    # Hiện balance ví
    balance = await get_balance(db_user["id"])
    lines.append(f"👛 Số dư ví: <b>{format_vnd(balance)}</b>")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=payment_method_kb(order_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Chọn thanh toán ─────────────────────────────────────────────────────────

@router.callback_query(PaymentMethodCB.filter(F.method == "qr"))
async def payment_qr(
    callback: CallbackQuery,
    callback_data: PaymentMethodCB,
    db_user: dict,
) -> None:
    """Thanh toán QR → tạo mã QR + chờ poller xử lý."""
    order = await get_order_by_id(callback_data.order_id)
    if not order or order["user_id"] != db_user["id"]:
        await callback.answer("❌ Đơn không tồn tại.", show_alert=True)
        return

    if order["status"] != "pending":
        await callback.answer("❌ Đơn đã được xử lý.", show_alert=True)
        return

    # Cập nhật payment_method
    from db.queries.orders import update_order_status
    await update_order_status(order["id"], "pending", payment_method="qr")

    expire_min = await get_setting_int("order_expire_min", 30)
    qr_url = await build_qr_url(order["amount"], order["order_code"])
    caption = await build_qr_caption(order["amount"], order["order_code"], expire_min)

    # Xóa inline message, gửi ảnh QR
    from bot.keyboards.inline_kb import order_cancel_kb
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=qr_url,
        caption=caption,
        parse_mode="HTML",
        reply_markup=order_cancel_kb(order["id"])
    )
    await callback.answer()


@router.callback_query(PaymentMethodCB.filter(F.method == "wallet"))
async def payment_wallet(
    callback: CallbackQuery,
    callback_data: PaymentMethodCB,
    db_user: dict,
) -> None:
    """Thanh toán bằng ví → xử lý ngay."""
    order = await get_order_by_id(callback_data.order_id)
    if not order or order["user_id"] != db_user["id"]:
        await callback.answer("❌ Đơn không tồn tại.", show_alert=True)
        return

    if order["status"] != "pending":
        await callback.answer("❌ Đơn đã được xử lý.", show_alert=True)
        return

    # Kiểm tra số dư
    balance = await get_balance(db_user["id"])
    if balance < order["amount"]:
        await callback.answer(
            f"❌ Số dư không đủ! Cần {format_vnd(order['amount'])}, "
            f"hiện có {format_vnd(balance)}.",
            show_alert=True,
        )
        return

    # Xử lý thanh toán ví ngay
    await callback.message.edit_text(
        f"⏳ Đang xử lý thanh toán đơn <b>{order['order_code']}</b>...",
        parse_mode="HTML",
    )

    bot = callback.bot
    success = await process_wallet_payment(bot, order["id"])

    if not success:
        show_qr = True
        if str(order.get("product_name") or "").startswith("Custom $"):
            show_qr = order["amount"] >= 1000
        await callback.message.edit_text(
            f"❌ Thanh toán đơn <b>{order['order_code']}</b> thất bại.\n"
            f"Vui lòng kiểm tra số dư ví hoặc chọn phương thức khác.",
            parse_mode="HTML",
            reply_markup=payment_method_kb(order["id"], show_qr=show_qr),
        )

    await callback.answer()


# ── Back navigation ─────────────────────────────────────────────────────────

@router.callback_query(BackCB.filter(F.target == "cat"))
async def back_to_categories(callback: CallbackQuery, state: FSMContext) -> None:
    """Quay lại danh mục."""
    await state.clear()
    categories = await get_active_categories()
    per_page = await get_setting_int("pagination_size", 6)
    await callback.message.edit_text(
        "🛒 <b>Danh mục sản phẩm</b>\n\nChọn danh mục:",
        reply_markup=categories_kb(categories, page=0, per_page=per_page),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(BackCB.filter(F.target == "srv"))
async def back_to_servers(callback: CallbackQuery, state: FSMContext) -> None:
    """Quay lại danh sách server."""
    fsm_data = await state.get_data()
    action = fsm_data.get("key_action", "new")

    servers = await get_active_servers()
    if not servers:
        await callback.message.edit_text("🖥 Chưa có server nào.")
        await callback.answer()
        return

    action_text = "🔑 Mua key mới" if action == "new" else "💳 Nạp key cũ"
    await callback.message.edit_text(
        f"{action_text}\n\nChọn server:",
        reply_markup=servers_kb(servers, action=action),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(BackCB.filter(F.target == "main"))
async def back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Quay về menu chính (xóa inline message)."""
    await state.clear()
    await callback.message.delete()
    await callback.answer()


# ── Noop callback (pagination indicator) ────────────────────────────────────

@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    """Bỏ qua callback 'noop' (nút hiển thị trang)."""
    await callback.answer()
