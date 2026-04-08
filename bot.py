import logging
import random
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from config import BOT_TOKEN, TASKS, FAQ, WELCOME_MESSAGE, FINAL_MESSAGE, PRIZE_HINT

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

IMAGES_DIR = Path(__file__).parent / "images"

# {user_id: {"task": int, "waiting_answer": bool, "waiting_photo": bool, "hints_used": int}}
user_state: dict[int, dict] = {}


# ──────────────────────────────────────────────
#  КЛАВИАТУРЫ
# ──────────────────────────────────────────────

def kb_waiting(hints_used: int, max_hints: int) -> InlineKeyboardMarkup:
    buttons = []
    if hints_used < max_hints:
        buttons.append([InlineKeyboardButton(
            f"💡 Подсказка ({hints_used + 1}/{max_hints})",
            callback_data="hint"
        )])
    buttons.append([InlineKeyboardButton("✏️ Ввести ответ", callback_data="enter_answer")])
    return InlineKeyboardMarkup(buttons)


def kb_show_place() -> InlineKeyboardMarkup:
    """Кнопки после верного ответа — показать место или нет."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👀 Да, покажи место!", callback_data="show_place")],
        [InlineKeyboardButton("💪 Нет, я справлюсь сама", callback_data="no_show_place")],
    ])


def kb_photo_prompt(is_last_task: bool) -> InlineKeyboardMarkup:
    """Кнопка после фото — следующая загадка или финал."""
    if is_last_task:
        label = "📸 Сделала фото? Жми — За призом! 🎁"
        data = "photo_done_finale"
    else:
        label = "📸 Сделала фото? Жми — Следующая загадка! ➡️"
        data = "photo_done"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data)]])


def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗺 Начать квест!", callback_data="start_quest")]
    ])


# ──────────────────────────────────────────────
#  ОТПРАВКА ЗАДАНИЯ
# ──────────────────────────────────────────────

async def send_task(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    user_id: int, from_callback: bool = True):
    state = user_state[user_id]
    idx = state["task"]

    if idx >= len(TASKS):
        await send_finale(update, context, from_callback)
        return

    task = TASKS[idx]
    state["waiting_answer"] = True
    state["waiting_photo"] = False
    state["hints_used"] = 0
    max_hints = len(task.get("hints", []))

    text = (
        f"📍 Задание {idx + 1} из {len(TASKS)}\n\n"
        f"{task['title']}\n\n"
        f"{task['description']}"
    )

    kb = kb_waiting(0, max_hints)
    chat = update.callback_query.message if from_callback else update.message

    # 1. Картинка загадки
    image_file = task.get("image_file")
    if image_file:
        image_path = IMAGES_DIR / image_file
        if image_path.exists():
            with open(image_path, "rb") as f:
                await chat.reply_photo(photo=f)
        else:
            logger.warning(f"Картинка не найдена: {image_path}")

    # 2. Текст загадки с кнопками
    await chat.reply_text(text, reply_markup=kb)


async def send_finale(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      from_callback: bool = True):
    text = FINAL_MESSAGE.format(hint=PRIZE_HINT)
    chat = update.callback_query.message if from_callback else update.message

    finale_image = IMAGES_DIR / "finale.jpg"
    if finale_image.exists():
        with open(finale_image, "rb") as f:
            await chat.reply_photo(photo=f)

    await chat.reply_text(text)


# ──────────────────────────────────────────────
#  КОМАНДЫ
# ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = {
        "task": -1,
        "waiting_answer": False,
        "waiting_photo": False,
        "hints_used": 0
    }
    context.user_data.clear()
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=kb_start())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — начать квест заново\n"
        "/task — повторить текущую загадку\n"
        "/help — эта справка\n\n"
        "Во время квеста:\n"
        "• Нажми Подсказка если застряла\n"
        "• Нажми Ввести ответ чтобы проверить\n"
        "• После верного ответа — пришли фото с места\n"
        "• Или напиши слово подсказка 💡"
    )


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_state or user_state[user_id]["task"] < 0:
        await update.message.reply_text("Сначала запусти квест командой /start 🗺")
        return
    await send_task(update, context, user_id, from_callback=False)


# ──────────────────────────────────────────────
#  КНОПКИ
# ──────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_state:
        user_state[user_id] = {
            "task": -1,
            "waiting_answer": False,
            "waiting_photo": False,
            "hints_used": 0
        }

    state = user_state[user_id]

    if query.data == "start_quest":
        state["task"] = 0
        await send_task(update, context, user_id, from_callback=True)

    elif query.data == "show_place":
        # Показываем фото места и просим прислать своё фото
        idx = state["task"]
        task = TASKS[idx]
        is_last = (idx == len(TASKS) - 1)

        place_file = task.get("place_image_file")
        if place_file:
            place_path = IMAGES_DIR / place_file
            if place_path.exists():
                with open(place_path, "rb") as f:
                    await query.message.reply_photo(
                        photo=f,
                        caption="📍 Вот твоя цель — найди это место!"
                    )
            else:
                logger.warning(f"Фото места не найдено: {place_path}")
                await query.message.reply_text("📍 Фото места пока нет, но ты найдёшь!")
        else:
            await query.message.reply_text("📍 Фото места не добавлено, но ты справишься!")

        await query.message.reply_text(
            "А теперь сделай фото на этом месте и пришли сюда 📸\n"
            "Или нажми кнопку ниже если уже готова!",
            reply_markup=kb_photo_prompt(is_last)
        )
        state["waiting_photo"] = True

    elif query.data == "no_show_place":
        # Отказалась от подсказки
        idx = state["task"]
        is_last = (idx == len(TASKS) - 1)
        await query.message.reply_text(
            "Я знал что ты не ищешь лёгких путей.... удачи в поиске! 💪\n\n"
            "А теперь сделай фото на этом месте и пришли сюда 📸\n"
            "Или нажми кнопку ниже если уже готова!",
            reply_markup=kb_photo_prompt(is_last)
        )
        state["waiting_photo"] = True

    elif query.data == "photo_done":
        state["task"] += 1
        state["waiting_photo"] = False
        await send_task(update, context, user_id, from_callback=True)

    elif query.data == "photo_done_finale":
        state["waiting_photo"] = False
        await send_finale(update, context, from_callback=True)

    elif query.data == "hint":
        idx = state["task"]
        if idx >= len(TASKS):
            return
        task = TASKS[idx]
        hints = task.get("hints", [])
        used = state["hints_used"]
        max_hints = len(hints)
        if used < max_hints:
            state["hints_used"] += 1
            hint_text = f"💡 Подсказка {used + 1} из {max_hints}:\n\n{hints[used]}"
            await query.message.reply_text(
                hint_text,
                reply_markup=kb_waiting(state["hints_used"], max_hints)
            )
        else:
            await query.message.reply_text(
                "Подсказки закончились! Ты точно справишься 💪",
                reply_markup=kb_waiting(state["hints_used"], max_hints)
            )

    elif query.data == "enter_answer":
        context.user_data["awaiting_answer"] = True
        await query.message.reply_text("✏️ Напиши свой ответ — я проверю!")


# ──────────────────────────────────────────────
#  ОБРАБОТЧИК ФОТО
# ──────────────────────────────────────────────

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Фото получено от user_id={user_id} | state={user_state.get(user_id)}")

    if user_id not in user_state:
        await update.message.reply_text("Напиши /start чтобы начать квест 🗺")
        return

    state = user_state[user_id]

    if not state.get("waiting_photo"):
        await update.message.reply_text(
            "Красивое фото! Но сейчас мне нужен твой ответ на загадку 😄\n"
            "Нажми «Ввести ответ» чтобы продолжить."
        )
        return

    # Фото принято
    state["waiting_photo"] = False
    idx = state["task"]
    is_last = (idx == len(TASKS) - 1)

    reactions = [
        "Огонь фото! 🔥",
        "Красотка! 😍",
        "Зачёт! 📸✅",
        "Шикарно! Двигаемся дальше! 🚀",
        "Вот это кадр! 🌟",
    ]
    await update.message.reply_text(random.choice(reactions))

    if is_last:
        await send_finale(update, context, from_callback=False)
    else:
        state["task"] += 1
        await send_task(update, context, user_id, from_callback=False)


# ──────────────────────────────────────────────
#  ТЕКСТОВЫЕ СООБЩЕНИЯ
# ──────────────────────────────────────────────

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower().strip()

    if user_id not in user_state:
        await update.message.reply_text("Напиши /start чтобы начать квест 🗺")
        return

    state = user_state[user_id]

    # Ждём фото — напоминаем
    if state.get("waiting_photo"):
        idx = state["task"]
        is_last = (idx == len(TASKS) - 1)
        await update.message.reply_text(
            "📸 Сначала пришли фото с этого места!\nИли нажми кнопку ниже.",
            reply_markup=kb_photo_prompt(is_last)
        )
        return

    # Слово «подсказка»
    if "подсказка" in text and state.get("waiting_answer"):
        idx = state["task"]
        if idx < len(TASKS):
            task = TASKS[idx]
            hints = task.get("hints", [])
            used = state["hints_used"]
            max_hints = len(hints)
            if used < max_hints:
                state["hints_used"] += 1
                hint_text = f"💡 Подсказка {used + 1} из {max_hints}:\n\n{hints[used]}"
                await update.message.reply_text(
                    hint_text,
                    reply_markup=kb_waiting(state["hints_used"], max_hints)
                )
            else:
                await update.message.reply_text("Подсказки закончились, но ты справишься! 💪")
        return

    # Проверка ответа
    if context.user_data.get("awaiting_answer") and state.get("waiting_answer"):
        idx = state["task"]
        if idx < len(TASKS):
            task = TASKS[idx]
            correct_answers = [a.lower().strip() for a in task.get("answers", [])]
            matched = any(
                any(kw in text for kw in ans.split())
                for ans in correct_answers
            )
            if matched:
                context.user_data["awaiting_answer"] = False
                state["waiting_answer"] = False

                praise = random.choice([
                    "Верно! Отлично справилась! 🎉",
                    "Правильно! Ты умница! ✅",
                    "Именно! Браво! 🌟",
                    "В точку! Молодец! 💫"
                ])
                success = task.get("success_text", "")

                await update.message.reply_text(
                    f"{praise}\n\n{success}\n\n"
                    "Хочешь увидеть место которое тебе нужно найти?",
                    reply_markup=kb_show_place()
                )
            else:
                max_hints = len(task.get("hints", []))
                await update.message.reply_text(
                    random.choice([
                        "Не совсем... Попробуй ещё раз или возьми подсказку! 🤔",
                        "Пока не то. Может подсказка поможет? 💡",
                        "Почти! Но нет. Осмотрись внимательнее! 🔍"
                    ]),
                    reply_markup=kb_waiting(state["hints_used"], max_hints)
                )
        return

    # FAQ
    best_match = None
    best_score = 0
    for question, answer in FAQ.items():
        keywords = question.lower().split()
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_match = answer

    if best_score >= 1 and best_match:
        await update.message.reply_text(best_match)
    else:
        await update.message.reply_text("Не поняла 🤔 Напиши подсказка или /help")


# ──────────────────────────────────────────────
#  ЗАПУСК
# ──────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CallbackQueryHandler(button_handler))

    photo_filter = filters.PHOTO | filters.Document.IMAGE
    app.add_handler(MessageHandler(photo_filter, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Квест-бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()