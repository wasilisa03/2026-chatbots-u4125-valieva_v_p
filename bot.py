"""
Бот для сбора обратной связи + работа с CSV сотрудниками (2-я лабораторная)
"""

import os
import logging
import sqlite3
import csv
from io import StringIO
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==================== НАСТРОЙКИ ====================

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Создайте файл .env")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
FIO, IDEA = range(2)

# ==================== БАЗА ДАННЫХ (ОТЗЫВЫ) ====================

def init_db():
    conn = sqlite3.connect("feedback.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fio TEXT NOT NULL,
            idea TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

def save_feedback(fio: str, idea: str):
    conn = sqlite3.connect("feedback.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO feedback (fio, idea, created_at) VALUES (?, ?, ?)",
        (fio, idea, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_all_feedback():
    conn = sqlite3.connect("feedback.db")
    cursor = conn.cursor()
    cursor.execute("SELECT fio, idea, created_at FROM feedback ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==================== РАБОТА С CSV (СОТРУДНИКИ) ====================

CSV_PATH = "employees.csv"

def load_employees():
    """Загружает сотрудников из CSV"""
    employees = []
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                employees.append(row)
    except FileNotFoundError:
        logger.error("Файл employees.csv не найден")
        return []
    return employees

def search_employee_by_name(name: str):
    """Поиск сотрудника по имени (частичное совпадение)"""
    employees = load_employees()
    name_lower = name.lower()
    return [e for e in employees if name_lower in e['name'].lower()]

def filter_by_department(dept: str):
    """Фильтр сотрудников по отделу"""
    employees = load_employees()
    dept_lower = dept.lower()
    return [e for e in employees if e['department'].lower() == dept_lower]

# ==================== CSV КОМАНДЫ ====================

async def employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать всех сотрудников"""
    employees_list = load_employees()
    if not employees_list:
        await update.message.reply_text("❌ Файл employees.csv не найден или пуст.")
        return
    
    text = "📋 *Список сотрудников:*\n\n"
    for e in employees_list:
        text += f"👤 *{e['name']}*\n"
        text += f"   Отдел: {e['department']}\n"
        text += f"   Должность: {e['role']}\n"
        text += f"   Email: {e['email']}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def search_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск сотрудника по имени"""
    if not context.args:
        await update.message.reply_text("ℹ️ Укажите имя для поиска. Пример: /search Иван")
        return
    
    query = " ".join(context.args)
    results = search_employee_by_name(query)
    
    if not results:
        await update.message.reply_text(f"🔍 Сотрудник с именем «{query}» не найден.")
        return
    
    text = f"🔍 *Результаты поиска:*\n\n"
    for e in results:
        text += f"👤 *{e['name']}*\n"
        text += f"   Отдел: {e['department']}\n"
        text += f"   Должность: {e['role']}\n"
        text += f"   Email: {e['email']}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def department(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сотрудников по отделу"""
    if not context.args:
        await update.message.reply_text("ℹ️ Укажите отдел. Пример: /department IT")
        return
    
    dept = " ".join(context.args)
    results = filter_by_department(dept)
    
    if not results:
        await update.message.reply_text(f"🏢 Отдел «{dept}» не найден.")
        return
    
    text = f"🏢 *Отдел: {dept.upper()}*\n\n"
    for e in results:
        text += f"👤 *{e['name']}*\n"
        text += f"   Должность: {e['role']}\n"
        text += f"   Email: {e['email']}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ==================== ЭКСПОРТ ОТЗЫВОВ В CSV ====================

async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_feedback()
    if not rows:
        await update.message.reply_text("📋 Нет отзывов для экспорта.")
        return
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ФИО", "Идея", "Дата"])
    writer.writerows(rows)
    output.seek(0)
    
    await update.message.reply_document(
        document=output,
        filename=f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        caption="✅ Отзывы экспортированы в CSV"
    )

# ==================== КОМАНДЫ И КНОПКИ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Оставить отзыв", callback_data="leave_feedback")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📤 Экспорт CSV", callback_data="export_csv")],
        [InlineKeyboardButton("👥 Сотрудники", callback_data="employees_menu")],
    ]
    await update.message.reply_text(
        "👋 Привет! Я бот для сбора обратной связи и работы с данными.\n\n"
        "📝 Оставить отзыв — напишите свои идеи\n"
        "📊 Статистика — список имён и отзывов\n"
        "📤 Экспорт CSV — выгрузить все отзывы\n"
        "👥 Сотрудники — работа с CSV (показать, поиск, отдел)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rows = get_all_feedback()
    if not rows:
        await query.message.reply_text("📋 Список отзывов пуст.")
        return
    
    text = "📊 *Статистика отзывов:*\n\n"
    for i, (fio, idea, date) in enumerate(rows, 1):
        text += f"{i}. *{fio}*\n"
        text += f"   💡 {idea}\n"
        text += f"   📅 {date}\n\n"
        
        if len(text) > 3500:
            await query.message.reply_text(text, parse_mode="Markdown")
            text = ""
    
    if text:
        await query.message.reply_text(text, parse_mode="Markdown")

async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rows = get_all_feedback()
    if not rows:
        await query.message.reply_text("📋 Нет отзывов для экспорта.")
        return
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ФИО", "Идея", "Дата"])
    writer.writerows(rows)
    output.seek(0)
    
    await query.message.reply_document(
        document=output,
        filename=f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        caption="✅ Отзывы экспортированы в CSV"
    )

async def employees_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📋 Все сотрудники", callback_data="employees_all")],
        [InlineKeyboardButton("🔍 Поиск по имени", callback_data="employees_search")],
        [InlineKeyboardButton("🏢 Поиск по отделу", callback_data="employees_dept")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")],
    ]
    await query.message.edit_text(
        "👥 *Работа с сотрудниками*\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def employees_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    employees_list = load_employees()
    if not employees_list:
        await query.message.reply_text("❌ Файл employees.csv не найден или пуст.")
        return
    
    text = "📋 *Список сотрудников:*\n\n"
    for e in employees_list:
        text += f"👤 *{e['name']}*\n"
        text += f"   Отдел: {e['department']}\n"
        text += f"   Должность: {e['role']}\n"
        text += f"   Email: {e['email']}\n\n"
    
    await query.message.reply_text(text, parse_mode="Markdown")

async def employees_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔍 Введите имя для поиска (например: Иван)")
    context.user_data["awaiting_search"] = True

async def employees_dept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🏢 Введите название отдела (например: IT)")
    context.user_data["awaiting_dept"] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_search"):
        query = update.message.text
        results = search_employee_by_name(query)
        context.user_data.pop("awaiting_search", None)
        
        if not results:
            await update.message.reply_text(f"🔍 Сотрудник с именем «{query}» не найден.")
            return
        
        text = f"🔍 *Результаты поиска:*\n\n"
        for e in results:
            text += f"👤 *{e['name']}*\n"
            text += f"   Отдел: {e['department']}\n"
            text += f"   Должность: {e['role']}\n"
            text += f"   Email: {e['email']}\n\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")
    
    elif context.user_data.get("awaiting_dept"):
        query = update.message.text
        results = filter_by_department(query)
        context.user_data.pop("awaiting_dept", None)
        
        if not results:
            await update.message.reply_text(f"🏢 Отдел «{query}» не найден.")
            return
        
        text = f"🏢 *Отдел: {query.upper()}*\n\n"
        for e in results:
            text += f"👤 *{e['name']}*\n"
            text += f"   Должность: {e['role']}\n"
            text += f"   Email: {e['email']}\n\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Оставить отзыв", callback_data="leave_feedback")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("📤 Экспорт CSV", callback_data="export_csv")],
        [InlineKeyboardButton("👥 Сотрудники", callback_data="employees_menu")],
    ]
    await query.message.edit_text(
        "👋 Привет! Я бот для сбора обратной связи и работы с данными.\n\n"
        "📝 Оставить отзыв — напишите свои идеи\n"
        "📊 Статистика — список имён и отзывов\n"
        "📤 Экспорт CSV — выгрузить все отзывы\n"
        "👥 Сотрудники — работа с CSV (показать, поиск, отдел)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== ДИАЛОГ ОТЗЫВА ====================

async def leave_feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("👋 Напиши своё ФИО")
    return FIO

async def get_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["fio"] = update.message.text.strip()
    await update.message.reply_text("✅ Принято! Теперь напиши свои рекомендации для улучшения")
    return IDEA

async def get_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idea = update.message.text.strip()
    fio = context.user_data.get("fio", "Не указано")
    
    save_feedback(fio, idea)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить еще отзыв", callback_data="add_more")],
        [InlineKeyboardButton("🔚 Конец", callback_data="end")]
    ])
    
    await update.message.reply_text(
        "✅ Спасибо за отзыв! Что дальше?",
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("✅ Принято! Теперь напиши свои рекомендации для улучшения")
    return IDEA

async def end_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("👋 Диалог завершён. Нажми /start для продолжения")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Диалог отменён. Нажми /start")
    context.user_data.clear()
    return ConversationHandler.END

# ==================== ЗАПУСК ====================

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("export_csv", export_csv))
    application.add_handler(CommandHandler("employees", employees))
    application.add_handler(CommandHandler("search", search_employee))
    application.add_handler(CommandHandler("department", department))
    
    # Кнопки главного меню
    application.add_handler(CallbackQueryHandler(stats_callback, pattern="^stats$"))
    application.add_handler(CallbackQueryHandler(export_callback, pattern="^export_csv$"))
    application.add_handler(CallbackQueryHandler(employees_menu, pattern="^employees_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(employees_all, pattern="^employees_all$"))
    application.add_handler(CallbackQueryHandler(employees_search, pattern="^employees_search$"))
    application.add_handler(CallbackQueryHandler(employees_dept, pattern="^employees_dept$"))
    
    # Диалог
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(leave_feedback_start, pattern="^leave_feedback$"),
        ],
        states={
            FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio)],
            IDEA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_idea)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
    # Кнопки внутри диалога
    application.add_handler(CallbackQueryHandler(add_more, pattern="^add_more$"))
    application.add_handler(CallbackQueryHandler(end_dialog, pattern="^end$"))
    
    # Обработчик текстовых запросов для поиска
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Бот запущен")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()