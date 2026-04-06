import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN, TASKS

logging.basicConfig(level=logging.INFO)

user_state = {}


def build_keyboard(options):
    keyboard = []
    for opt in options:
        keyboard.append([InlineKeyboardButton(opt, callback_data=opt)])
    keyboard.append([InlineKeyboardButton("💡 Подсказка", callback_data="hint")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = 0
    await send_task(update, context, user_id, True)


async def send_task(update, context, user_id, first=False):
    index = user_state[user_id]

    if index >= len(TASKS):
        return

    task = TASKS[index]

    text = f"*{task['title']}*\n\n{task['text']}\n\n({index+1}/{len(TASKS)})"

    if first:
        chat = update.message
    else:
        chat = update.callback_query.message

    await chat.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=build_keyboard(task["options"]),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    index = user_state[user_id]
    task = TASKS[index]

    if query.data == "hint":
        await query.message.reply_text(f"💡 {task.get('hint', 'Подумай ещё 😏')}")
        return

    if query.data == task["correct"]:
        await query.message.reply_text("✅ Правильно!")

        user_state[user_id] += 1
        await send_task(update, context, user_id)
    else:
        await query.message.reply_text("❌ Неа... попробуй ещё 😏")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))

    print("🔥 Deluxe Quest Bot запущен")
    app.run_polling()


if __name__ == "__main__":
    main()