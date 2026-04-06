import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from config import BOT_TOKEN, TASKS, FAQ, WELCOME_MESSAGE, FINAL_MESSAGE, PRIZE_HINT

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояние пользователей: {user_id: {"task": 0, "hint_index": 0, "solved": False}}
user_state: dict[int, dict] = {}


def get_state(user_id: int) -> dict:
    if user_id not in user_state:
        user_state[user_id] = {"task": 0, "hint_index": 0}
    return user_state[user_id]


def get_done_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Готово — следующая загадка", callback_data="next")],
    ])


def get_hint_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Подсказка", callback_data="hint")],
    ])


async def send_task(chat_id: int, context, user_id: int):
    state = get_state(user_id)
    idx = state["task"]
    state["hint_index"] = 0  # сброс подсказок для нового задания

    if idx >= len(TASKS):
        # Финал
        await context.bot.send_message(
            chat_id=chat_id,
            text=FINAL_MESSAGE.format(hint=PRIZE_HINT),
            parse_mode="Markdown"
        )
        return

    task = TASKS[idx]

    # Отправляем картинку
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=task["image_url"],
            caption=f"📍 *{task['title']}*",
            parse_mode="Markdown"
        )
    except Exception:
        pass  # если картинка не загрузилась — продолжаем без неё

    # Отправляем текст загадки
    text = (
        f"*{task['title']}*\n\n"
        f"{task['description']}\n\n"
        f"_Напиши ответ прямо в чат. Если не знаешь — нажми «Подсказка»._"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=get_hint_keyboard()
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = {"task": 0, "hint_index": 0}

    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")
    await send_task(update.effective_chat.id, context, user_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = get_state(user_id)

    if query.data == "hint":
        idx = state["task"]
        if idx >= len(TASKS):
            return
        task = TASKS[idx]
        hints = task["hints"]
        hint_idx = state["hint_index"]

        if hint_idx < len(hints):
            await query.message.reply_text(hints[hint_idx], parse_mode="Markdown")
            state["hint_index"] += 1
        else:
            await query.message.reply_text(
                "🤷 Подсказки закончились! Попробуй ещё раз или спроси кого-нибудь рядом 😄",
            )

    elif query.data == "next":
        state["task"] += 1
        state["hint_index"] = 0
        await send_task(query.message.chat_id, context, user_id)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text.lower().strip()
    idx = state["task"]

    # Если квест завершён
    if idx >= len(TASKS):
        await update.message.reply_text(
            "🎉 Ты уже прошла весь квест! Напиши /start чтобы начать заново."
        )
        return

    # Команда подсказка
    if "подсказка" in text or "hint" in text or "помощь" in text:
        task = TASKS[idx]
        hints = task["hints"]
        hint_idx = state["hint_index"]
        if hint_idx < len(hints):
            await update.message.reply_text(hints[hint_idx], parse_mode="Markdown")
            state["hint_index"] += 1
        else:
            await update.message.reply_text("🤷 Все подсказки уже выданы! Ты справишься 💪")
        return

    # Проверка FAQ
    for question, answer in FAQ.items():
        keywords = question.lower().split()
        if any(kw in text for kw in keywords):
            await update.message.reply_text(f"🤖 {answer}", parse_mode="Markdown")
            return

    # Проверка ответа на текущую загадку
    task = TASKS[idx]
    correct_answers = [a.lower() for a in task["answers"]]
    is_correct = any(ans in text for ans in correct_answers)

    if is_correct:
        await update.message.reply_text(
            task["success_text"],
            parse_mode="Markdown",
            reply_markup=get_done_keyboard()
        )
    else:
        wrong_phrases = [
            "Хм, не то... попробуй ещё раз! 🤔 Или нажми «Подсказка».",
            "Близко, но нет 😄 Подумай ещё!",
            "Не совсем... Напиши *подсказка* если нужна помощь 💡",
            "Продолжай искать — ты на верном пути! 🗺",
        ]
        await update.message.reply_text(
            random.choice(wrong_phrases),
            parse_mode="Markdown",
            reply_markup=get_hint_keyboard()
        )


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_state:
        await update.message.reply_text("Сначала запусти квест командой /start 🗺")
        return
    await send_task(update.effective_chat.id, context, user_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Команды:*\n"
        "/start — начать квест\n"
        "/task — показать текущую загадку\n"
        "/help — эта справка\n\n"
        "💡 Чтобы получить подсказку — напиши слово *подсказка* в любой момент.",
        parse_mode="Markdown"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Квест-бот запущен! 🗺")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()