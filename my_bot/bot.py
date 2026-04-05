import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import BOT_TOKEN, TASKS, FAQ

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Индекс текущего задания для каждого пользователя
user_task_index: dict[int, int] = {}


def get_main_keyboard():
    """Главная клавиатура с кнопкой Готово."""
    keyboard = [
        [InlineKeyboardButton("✅ Готово — следующее задание", callback_data="next_task")],
        [InlineKeyboardButton("🔄 Начать сначала", callback_data="restart")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    user = update.effective_user
    user_id = user.id
    user_task_index[user_id] = 0

    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я бот-тренажёр. Буду давать тебе задания одно за другим.\n"
        "Нажимай *«Готово»* когда выполнишь задание — получишь следующее.\n\n"
        "Также можешь задать мне вопрос — я отвечу, если знаю ответ 🤓\n\n"
        "Напиши /help чтобы увидеть список доступных команд.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(),
    )
    await send_task(update, context, user_id, from_start=True)


async def send_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    from_start: bool = False,
):
    """Отправляет текущее задание пользователю."""
    index = user_task_index.get(user_id, 0)

    if index >= len(TASKS):
        text = (
            "🎉 *Поздравляю! Ты выполнил все задания!*\n\n"
            "Нажми «Начать сначала», чтобы пройти снова."
        )
        msg = update.message if from_start else update.callback_query.message
        await msg.reply_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    task = TASKS[index]
    text = (
        f"📌 *Задание {index + 1} из {len(TASKS)}*\n\n"
        f"{task['title']}\n\n"
        f"{task['description']}"
    )

    if from_start:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=get_main_keyboard()
        )
    else:
        await update.callback_query.message.reply_text(
            text, parse_mode="Markdown", reply_markup=get_main_keyboard()
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline-кнопки."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "next_task":
        index = user_task_index.get(user_id, 0)
        user_task_index[user_id] = index + 1
        await send_task(update, context, user_id)

    elif query.data == "restart":
        user_task_index[user_id] = 0
        await query.message.reply_text(
            "🔄 Начинаем сначала!", reply_markup=get_main_keyboard()
        )
        await send_task(update, context, user_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help."""
    questions_list = "\n".join(f"• {q}" for q in FAQ.keys())
    await update.message.reply_text(
        "📖 *Доступные команды:*\n"
        "/start — начать / перезапустить бота\n"
        "/task — показать текущее задание\n"
        "/help — эта справка\n\n"
        "💬 *Вопросы, на которые я умею отвечать:*\n"
        f"{questions_list}\n\n"
        "Просто напиши вопрос своими словами — я постараюсь найти ответ.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(),
    )


async def current_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /task — показать текущее задание."""
    user_id = update.effective_user.id
    if user_id not in user_task_index:
        await update.message.reply_text("Сначала запусти бота командой /start.")
        return
    await send_task(update, context, user_id, from_start=True)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений — ищет ответ в FAQ."""
    user_text = update.message.text.lower().strip()

    # Поиск по ключевым словам в FAQ
    best_match = None
    best_score = 0

    for question, answer in FAQ.items():
        keywords = question.lower().split()
        score = sum(1 for kw in keywords if kw in user_text)
        if score > best_score:
            best_score = score
            best_match = answer

    if best_score >= 1 and best_match:
        await update.message.reply_text(
            f"🤖 {best_match}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(),
        )
    else:
        phrases = [
            "Хм, не знаю ответа на этот вопрос 🤔\nПопробуй переформулировать или напиши /help.",
            "На этот вопрос у меня пока нет ответа. Напиши /help чтобы увидеть что я знаю.",
            "Не могу найти ответ. Проверь список вопросов командой /help 📖",
        ]
        await update.message.reply_text(
            random.choice(phrases),
            reply_markup=get_main_keyboard(),
        )


def main():
    """Запуск бота."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("task", current_task_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()