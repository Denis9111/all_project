import logging
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from config import BOT_TOKEN, TASKS, FAQ

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# state per user: {user_id: {"task": int, "waiting_answer": bool, "hints_used": int}}
user_state: dict[int, dict] = {}


def get_keyboard(waiting_answer: bool, hints_used: int, max_hints: int):
    task = user_state
    if waiting_answer:
        buttons = []
        if hints_used < max_hints:
            buttons.append([InlineKeyboardButton(f"💡 Подсказка ({hints_used}/{max_hints})", callback_data="hint")])
        buttons.append([InlineKeyboardButton("✏️ Ввести ответ", callback_data="enter_answer")])
        return InlineKeyboardMarkup(buttons)
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Следующее задание", callback_data="next_task")]
        ])


def get_start_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗺 Начать квест!", callback_data="start_quest")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = {"task": -1, "waiting_answer": False, "hints_used": 0}

    await update.message.reply_text(
        TASKS["intro"],
        parse_mode="Markdown",
        reply_markup=get_start_keyboard()
    )


async def send_task(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, from_callback=True):
    state = user_state[user_id]
    idx = state["task"]
    tasks = TASKS["quests"]

    if idx >= len(tasks):
        await send_finale(update, context, from_callback)
        return

    task = tasks[idx]
    state["waiting_answer"] = True
    state["hints_used"] = 0
    max_hints = len(task.get("hints", []))

    text = (
        f"📍 *Задание {idx + 1} из {len(tasks)}*\n\n"
        f"{task['emoji']}  *{task['title']}*\n\n"
        f"{task['riddle']}\n\n"
        f"_{task['instruction']}_"
    )

    kb = get_keyboard(True, 0, max_hints)

    if from_callback:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        if task.get("image_url"):
            await update.callback_query.message.reply_photo(
                photo=task["image_url"],
                caption=f"📸 {task.get('image_caption', '')}"
            )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        if task.get("image_url"):
            await update.message.reply_photo(
                photo=task["image_url"],
                caption=f"📸 {task.get('image_caption', '')}"
            )


async def send_finale(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=True):
    text = TASKS["finale"]
    if from_callback:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown")
        if TASKS.get("finale_image"):
            await update.callback_query.message.reply_photo(
                photo=TASKS["finale_image"],
                caption="🎁 Твой приз ждёт тебя!"
            )
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_state:
        user_state[user_id] = {"task": -1, "waiting_answer": False, "hints_used": 0}

    state = user_state[user_id]

    if query.data == "start_quest":
        state["task"] = 0
        await send_task(update, context, user_id)

    elif query.data == "next_task":
        state["task"] += 1
        await send_task(update, context, user_id)

    elif query.data == "hint":
        idx = state["task"]
        tasks = TASKS["quests"]
        if idx >= len(tasks):
            return
        task = tasks[idx]
        hints = task.get("hints", [])
        used = state["hints_used"]
        if used < len(hints):
            hint_text = f"💡 *Подсказка {used + 1}:*\n\n{hints[used]}"
            state["hints_used"] += 1
            max_hints = len(hints)
            kb = get_keyboard(True, state["hints_used"], max_hints)
            await query.message.reply_text(hint_text, parse_mode="Markdown", reply_markup=kb)
        else:
            await query.message.reply_text("Подсказки закончились! Ты справишься 💪")

    elif query.data == "enter_answer":
        context.user_data["awaiting_answer"] = True
        await query.message.reply_text(
            "✏️ Напиши свой ответ — я проверю!",
            parse_mode="Markdown"
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower().strip()

    if user_id not in user_state:
        await update.message.reply_text("Напиши /start чтобы начать квест 🗺")
        return

    state = user_state[user_id]

    # Check if waiting for answer
    if context.user_data.get("awaiting_answer") and state.get("waiting_answer"):
        idx = state["task"]
        tasks = TASKS["quests"]
        if idx < len(tasks):
            task = tasks[idx]
            correct_answers = [a.lower().strip() for a in task.get("answers", [])]
            # Fuzzy: check if any keyword from correct answers is in user text
            matched = any(
                any(kw in text for kw in ans.split())
                for ans in correct_answers
            )
            if matched:
                context.user_data["awaiting_answer"] = False
                state["waiting_answer"] = False
                praise = random.choice([
                    "🎉 Верно! Отлично справилась!",
                    "✅ Правильно! Ты умница!",
                    "🌟 Именно! Браво!",
                    "💫 В точку! Молодец!"
                ])
                max_hints = len(task.get("hints", []))
                kb = get_keyboard(False, 0, max_hints)
                await update.message.reply_text(
                    f"{praise}\n\n{task.get('correct_text', '')}",
                    parse_mode="Markdown",
                    reply_markup=kb
                )
            else:
                await update.message.reply_text(
                    random.choice([
                        "🤔 Не совсем... Попробуй ещё раз или возьми подсказку!",
                        "❌ Пока не то. Может подсказка поможет? 💡",
                        "🔍 Почти! Но нет. Осмотрись внимательнее!"
                    ]),
                    reply_markup=get_keyboard(True, state["hints_used"], len(task.get("hints", [])))
                )
        return

    # FAQ search
    best_match = None
    best_score = 0
    for question, answer in FAQ.items():
        keywords = question.lower().split()
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_match = answer

    if best_score >= 1 and best_match:
        await update.message.reply_text(f"🤖 {best_match}", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "Не поняла вопрос 🤔 Напиши /help или просто продолжай квест!"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Команды:*\n"
        "/start — начать квест заново\n"
        "/task — повторить текущее задание\n"
        "/help — эта справка\n\n"
        "Во время квеста:\n"
        "• Нажми *«💡 Подсказка»* если застряла\n"
        "• Нажми *«✏️ Ввести ответ»* чтобы проверить\n"
        "• Нажми *«➡️ Следующее»* после верного ответа",
        parse_mode="Markdown"
    )


async def current_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_state or user_state[user_id]["task"] < 0:
        await update.message.reply_text("Сначала запусти квест командой /start 🗺")
        return
    await send_task(update, context, user_id, from_callback=False)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("task", current_task_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    logger.info("Квест-бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()