"""
Все клавиатуры бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Подписка", callback_data="menu_sub"),
            InlineKeyboardButton(text="🎁 Триал 7 дней", callback_data="menu_trial"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI-Ассистент", callback_data="menu_ai"),
            InlineKeyboardButton(text="📄 Документы", callback_data="menu_docs"),
        ],
        [
            InlineKeyboardButton(text="👤 Кабинет", callback_data="menu_account"),
            InlineKeyboardButton(text="👥 Рефералы", callback_data="menu_referral"),
        ],
        [
            InlineKeyboardButton(text="⭐ Отзыв", callback_data="menu_review"),
            InlineKeyboardButton(text="💬 Поддержка", callback_data="menu_support"),
        ],
    ])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_main")]
    ])


def subscription_plans() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Базовый — 299₽/мес", callback_data="plan_basic")],
        [InlineKeyboardButton(text="🔵 Про — 799₽/мес", callback_data="plan_pro")],
        [InlineKeyboardButton(text="🟣 Бизнес — 1999₽/мес", callback_data="plan_business")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def payment_confirm(plan: str, amount: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{plan}_{amount}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")],
    ])


def trial_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Активировать триал", callback_data="activate_trial")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def docs_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF → Текст", callback_data="doc_pdf2txt")],
        [InlineKeyboardButton(text="📝 Текст → PDF", callback_data="doc_txt2pdf")],
        [InlineKeyboardButton(text="🔍 OCR (фото → текст)", callback_data="doc_ocr")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Задать вопрос", callback_data="ai_ask")],
        [InlineKeyboardButton(text="📋 Шаблоны запросов", callback_data="ai_templates")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def ai_templates_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Написать email", callback_data="tpl_email")],
        [InlineKeyboardButton(text="📊 Бизнес-план", callback_data="tpl_bizplan")],
        [InlineKeyboardButton(text="📣 Рекламный текст", callback_data="tpl_ad")],
        [InlineKeyboardButton(text="📝 Резюме", callback_data="tpl_cv")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_ai")],
    ])


def account_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 История платежей", callback_data="acc_payments")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="acc_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def referral_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}&text=Попробуй+этот+бот!")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


def review_rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="rate_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="rate_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate_3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate_5"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")],
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Написать в поддержку", callback_data="support_write")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])


# ---- Админ ----
def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="adm_confirm_pay")],
        [InlineKeyboardButton(text="🎫 Тикеты поддержки", callback_data="adm_tickets")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])
