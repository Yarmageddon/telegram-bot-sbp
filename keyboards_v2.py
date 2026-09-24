"""
Расширенные клавиатуры для новых функций
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_v2_keyboard() -> InlineKeyboardMarkup:
    """Главное меню v2"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏗 Земляные работы", callback_data="menu_earthworks"),
            InlineKeyboardButton(text="💎 Подписка", callback_data="menu_subscription")
        ],
        [
            InlineKeyboardButton(text="🎁 Триал", callback_data="menu_trial"),
            InlineKeyboardButton(text="📄 Документы", callback_data="menu_documents")
        ],
        [
            InlineKeyboardButton(text="🔍 OCR", callback_data="menu_ocr"),
            InlineKeyboardButton(text="👤 Личный кабинет", callback_data="menu_account")
        ],
        [
            InlineKeyboardButton(text="⭐ Отзывы", callback_data="menu_reviews"),
            InlineKeyboardButton(text="👥 Рефералы", callback_data="go_to_referral")
        ],
        [
            InlineKeyboardButton(text="💬 Поддержка", callback_data="go_to_support"),
            InlineKeyboardButton(text="🤖 Вопрос-ответ НПА", callback_data="menu_npa_qa")
        ]
    ])
    return keyboard


def subscription_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню подписки с апгрейдом/даунгрейдом"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оформить подписку", callback_data="go_to_subscribe")],
        [InlineKeyboardButton(text="🔄 Сменить тариф", callback_data="change_plan")],
        [InlineKeyboardButton(text="📊 Проверить статус", callback_data="check_subscription")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def trial_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура триал-периода"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Активировать триал (7 дней)", callback_data="activate_trial")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def documents_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура работы с документами"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 PDF → Текст", callback_data="doc_pdf_to_txt")],
        [InlineKeyboardButton(text="📝 Текст → PDF", callback_data="doc_txt_to_pdf")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def ocr_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура OCR"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправьте фото для распознавания", callback_data="ocr_info")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def review_rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора рейтинга"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="rate_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="rate_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate_3"),
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate_5")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")]
    ])
    return keyboard


def review_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура категории отзыва"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Общее", callback_data="review_cat_general")],
        [InlineKeyboardButton(text="💳 Оплата", callback_data="review_cat_payment")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="review_cat_support")],
        [InlineKeyboardButton(text="✨ Возможности", callback_data="review_cat_feature")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")]
    ])
    return keyboard


def account_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура личного кабинета"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 История платежей", callback_data="account_payments")],
        [InlineKeyboardButton(text="📊 Подробная статистика", callback_data="account_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def ai_assistant_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура AI-ассистента"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Возможности сервиса", callback_data="ai_features")],
        [InlineKeyboardButton(text="🏆 Преимущества", callback_data="ai_advantages")],
        [InlineKeyboardButton(text="💎 Тарифы", callback_data="ai_tariffs")],
        [InlineKeyboardButton(text="❓ Задать свой вопрос", callback_data="ai_custom_question")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата в меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
    ])
    return keyboard


def admin_news_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админа для новостей"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📰 Создать новость", callback_data="admin_create_news")],
        [InlineKeyboardButton(text="🚨 Создать срочную", callback_data="admin_create_urgent")],
        [InlineKeyboardButton(text="📋 Список новостей", callback_data="admin_news_list")]
    ])
    return keyboard


# ============= КЛАВИАТУРЫ ДЛЯ ЗЕМЛЯНЫХ РАБОТ =============

def earthworks_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню земляных работ"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Ордер", callback_data="earthworks_order")],
        [InlineKeyboardButton(text="📢 Плановое уведомление МПГУ", callback_data="earthworks_mpgu_planned")],
        [InlineKeyboardButton(text="📡 Плановое уведомление ИАС УГД", callback_data="earthworks_iasugd_planned")],
        [InlineKeyboardButton(text="🚨 Аварийное уведомление", callback_data="earthworks_emergency")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def earthworks_goals_keyboard(work_type: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора цели для земляных работ"""
    from earthworks import get_goals_by_type
    
    goals = get_goals_by_type(work_type)
    
    keyboard_buttons = []
    for goal_key, goal_text in goals.items():
        # Обрезаем длинные тексты для кнопок
        display_text = goal_text[:50] + "..." if len(goal_text) > 50 else goal_text
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=display_text,
                callback_data=f"goal_{work_type}_{goal_key}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_earthworks")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def npa_qa_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ИИ-помощника по НПА"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Что такое ордер?", callback_data="npa_q_order")],
        [InlineKeyboardButton(text="⏱ Сроки оформления ордера", callback_data="npa_q_order_terms")],
        [InlineKeyboardButton(text="📢 Уведомление МПГУ", callback_data="npa_q_mpgu")],
        [InlineKeyboardButton(text="📡 Уведомление ИАС УГД", callback_data="npa_q_iasugd")],
        [InlineKeyboardButton(text="🚨 Аварийные работы", callback_data="npa_q_emergency")],
        [InlineKeyboardButton(text="🏗 Восстановление благоустройства", callback_data="npa_q_restoration")],
        [InlineKeyboardButton(text="💬 Задать вопрос ИИ", callback_data="npa_q_custom")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard
