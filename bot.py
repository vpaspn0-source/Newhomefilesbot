import os
import sqlite3
import random
import string
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

STORAGE_CHANNEL = int(os.getenv("STORAGE_CHANNEL"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")
PROMO_CHANNEL = os.getenv("PROMO_CHANNEL")

app = Client(
    "bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

db = sqlite3.connect("database.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files(
    code TEXT PRIMARY KEY,
    message_ids TEXT,
    views INTEGER DEFAULT 0,
    owner INTEGER
)
""")

user_temp = {}

def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    if len(message.command) == 2:
        code = message.command[1]

        cursor.execute("SELECT * FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if not data:
            return await message.reply_text("❌ Link tidak ditemukan.")

        try:
            await client.get_chat_member(FORCE_CHANNEL, message.from_user.id)
        except:
            return await message.reply_text(
                "🚫 Wajib join channel dulu!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{FORCE_CHANNEL}")]]
                )
            )

        message_ids = data[1].split(",")

        for msg_id in message_ids:
            await client.copy_message(
                message.chat.id,
                STORAGE_CHANNEL,
                int(msg_id)
            )

        cursor.execute("UPDATE files SET views = views + 1 WHERE code=?", (code,))
        db.commit()

        await message.reply_text(
            "📢 Jangan lupa join channel kami!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔔 Kunjungi Channel", url=PROMO_CHANNEL)]]
            )
        )

    else:
        await message.reply_text("Kirim file untuk mulai 😎")

@app.on_message(filters.private & (filters.document | filters.video))
async def collect(client, message):
    forwarded = await message.forward(STORAGE_CHANNEL)

    user_id = message.from_user.id

    if user_id not in user_temp:
        user_temp[user_id] = []

    user_temp[user_id].append(str(forwarded.id))

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Tambah File Lagi", callback_data="add")],
        [InlineKeyboardButton("🔗 Buat Link", callback_data="create")]
    ])

    await message.reply_text(
        f"✅ File ditambahkan!\nTotal: {len(user_temp[user_id])}",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex("create"))
async def create_link(client, callback):
    user_id = callback.from_user.id

    if user_id not in user_temp or not user_temp[user_id]:
        return await callback.answer("Tidak ada file!", show_alert=True)

    code = generate_code()
    msg_ids = ",".join(user_temp[user_id])

    cursor.execute(
        "INSERT INTO files(code, message_ids, owner) VALUES(?,?,?)",
        (code, msg_ids, user_id)
    )
    db.commit()

    user_temp[user_id] = []

    bot_username = (await client.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"

    await callback.message.reply_text(f"🔗 Link berhasil dibuat!\n\n{link}")

app.run()
