import os
import threading
from pathlib import Path

import telebot
from flask import Flask
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


app = Flask(__name__)


@app.get("/")
def home() -> str:
    return "Bot is running!"


@app.get("/api/")
@app.get("/api/healthz")
def health_check() -> str:
    return "Bot is running!"


def keep_alive() -> None:
    port = int(os.getenv("PORT", "8080"))
    server_thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
    )
    server_thread.start()


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing. Add it in Replit Secrets before starting the bot."
    )

bot = telebot.TeleBot(TOKEN)
PROJECT_DIR = Path(__file__).resolve().parent
NUMBERS = tuple(range(1, 11))
available_by_chat: dict[int, set[int]] = {}
state_lock = threading.Lock()


def get_keyboard(available: set[int]) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    row: list[InlineKeyboardButton] = []

    for number in NUMBERS:
        if number in available:
            row.append(
                InlineKeyboardButton(
                    str(number), callback_data=f"btn_{number}"
                )
            )
        else:
            row.append(
                InlineKeyboardButton("✅", callback_data="taken")
            )

        if len(row) == 5:
            markup.row(*row)
            row = []

    if row:
        markup.row(*row)
    return markup


def reset_game(chat_id: int) -> set[int]:
    with state_lock:
        available_by_chat[chat_id] = set(NUMBERS)
        return set(NUMBERS)


@bot.message_handler(commands=["start", "game"])
def send_game(message: telebot.types.Message) -> None:
    available = reset_game(message.chat.id)
    bot.send_message(
        message.chat.id,
        "🎉 مسابقة الأكاديمية!\nأسرع واحدة تختار رقم:",
        reply_markup=get_keyboard(available),
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_query(call: telebot.types.CallbackQuery) -> None:
    if not call.message:
        bot.answer_callback_query(call.id)
        return

    if call.data == "taken":
        bot.answer_callback_query(
            call.id,
            "هذا الرقم تم اختياره مسبقاً!",
            show_alert=True,
        )
        return

    if not call.data or not call.data.startswith("btn_"):
        bot.answer_callback_query(call.id)
        return

    try:
        number = int(call.data.removeprefix("btn_"))
    except ValueError:
        bot.answer_callback_query(call.id)
        return

    chat_id = call.message.chat.id
    with state_lock:
        available = available_by_chat.setdefault(chat_id, set(NUMBERS))
        if number not in available:
            bot.answer_callback_query(
                call.id,
                "هذا الرقم تم اختياره مسبقاً!",
                show_alert=True,
            )
            return
        available.remove(number)
        updated_keyboard = get_keyboard(available)

    bot.answer_callback_query(call.id, "تم اختيار الرقم!")
    bot.edit_message_reply_markup(
        chat_id,
        call.message.message_id,
        reply_markup=updated_keyboard,
    )

    user_name = call.from_user.first_name or "المشاركة"
    image_path = PROJECT_DIR / f"card_{number}.jpg"
    caption = f"البطاقة رقم {number} من نصيب {user_name}! ✨"

    if image_path.exists():
        with image_path.open("rb") as photo:
            bot.send_photo(chat_id, photo, caption=caption)
    else:
        bot.send_message(chat_id, caption)


if __name__ == "__main__":
    keep_alive()
    print("Telegram academy game bot is running.")
    bot.infinity_polling(skip_pending=True)
