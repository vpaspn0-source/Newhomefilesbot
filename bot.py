import os
import sqlite3
import string
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
FORCE_GROUP = os.getenv("FORCE_GROUP")
GROUP_USERNAME = os.getenv("GROUP_USERNAME")
STORAGE_CHANNEL = int(os.getenv("STORAGE_CHANNEL"))

app = Client("storagebot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    code TEXT PRIMARY KEY,
    message_id INTEGER
)
""")

conn.commit()

# ================= HELPER =================
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

async def is_joined(user_id):
    try:
        member = await app.get_chat_member(int(FORCE_GROUP), user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ================= START =================
@app.on_message(filters.command("start"))
async def start(client, message):
    args = message.text.split()

    if len(args) > 1:
        code = args[1]

        if not await is_joined(message.from_user.id):
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Join Group", url=f"https://t.me/{GROUP_USERNAME}")],
                [InlineKeyboardButton("✅ Sudah Join", url=f"https://t.me/{client.me.username}?start={code}")]
            ])
            return await message.reply(
                "⚠️ Kamu harus join group terlebih dahulu!",
                reply_markup=buttons
            )

        cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if not data:
            return await message.reply("❌ File tidak ditemukan.")

        msg_id = data[0]

        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_CHANNEL,
            message_id=msg_id
        )

    else:
        await message.reply(
            "🎬 Kirim video ke bot untuk mendapatkan link share.\n\n"
            "📂 Semua video akan disimpan otomatis."
        )

# ================= HANDLE VIDEO =================
@app.on_message(filters.video)
async def handle_video(client, message):

    if not await is_joined(message.from_user.id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 Join Group", url=f"https://t.me/{GROUP_USERNAME}")]
        ])
        return await message.reply(
            "⚠️ Join group dulu sebelum upload!",
            reply_markup=buttons
        )

    # Kirim ke channel storage
    sent = await message.copy(STORAGE_CHANNEL)

    code = generate_code()

    cursor.execute("INSERT INTO files VALUES (?, ?)", (code, sent.id))
    conn.commit()

    link = f"https://t.me/{client.me.username}?start={code}"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Buka Video", url=link)],
        [InlineKeyboardButton("📢 Share", url=f"https://t.me/share/url?url={link}")]
    ])

    await message.reply(
        "✅ Video berhasil disimpan!\n\n"
        f"🔗 Link kamu:\n{link}",
        reply_markup=buttons
    )

app.run()
