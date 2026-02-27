import os
import math
import sqlite3
import random
import string
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= SAFE ENV =================

def get_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"ENV {name} belum diisi di Railway!")
    return value

API_ID = int(get_env("API_ID"))
API_HASH = get_env("API_HASH")
BOT_TOKEN = get_env("BOT_TOKEN")

STORAGE_CHANNEL = int(get_env("STORAGE_CHANNEL"))
BOT_USERNAME = get_env("BOT_USERNAME")

FORCE_CHANNEL_ID = int(get_env("FORCE_CHANNEL_ID"))
FORCE_CHANNEL_USERNAME = get_env("FORCE_CHANNEL_USERNAME")

PAGE_LIMIT = 10

# ================= INIT =================

app = Client(
    "MultiShareBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

db = sqlite3.connect("database.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    code TEXT,
    created DATE
)
""")
db.commit()

# ================= FUNCTION =================

def generate_code(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def is_joined(user_id):
    try:
        member = await app.get_chat_member(FORCE_CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def join_buttons(code=None):
    buttons = [
        [InlineKeyboardButton("📢 Join Channel",
         url=f"https://t.me/{FORCE_CHANNEL_USERNAME}")]
    ]

    if code:
        buttons.append([
            InlineKeyboardButton("✅ Sudah Join",
             callback_data=f"recheck_{code}")
        ])

    return InlineKeyboardMarkup(buttons)

def pagination_buttons(page, total_pages):
    nav = []

    if page > 1:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"))

    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="ignore"))

    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}"))

    return InlineKeyboardMarkup([nav])

# ================= START =================

@app.on_message(filters.command("start"))
async def start(client, message):

    # START WITH CODE
    if len(message.command) > 1:
        code = message.command[1]

        cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if not data:
            return await message.reply("❌ Code tidak valid.")

        if not await is_joined(message.from_user.id):
            return await message.reply(
                "⚠️ Kamu harus join channel terlebih dahulu!",
                reply_markup=join_buttons(code)
            )

        return await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_CHANNEL,
            message_id=data[0]
        )

    # NORMAL START
    if not await is_joined(message.from_user.id):
        return await message.reply(
            "⚠️ Kamu harus join channel untuk menggunakan bot!",
            reply_markup=join_buttons()
        )

    await message.reply(
        "🔥 Selamat datang di Multi Share Bot\n\n"
        "Kirim video/file untuk upload.\n"
        "Kirim /list untuk melihat semua file."
    )

# ================= UPLOAD =================

@app.on_message(filters.video | filters.document)
async def upload_file(client, message):

    if not await is_joined(message.from_user.id):
        return await message.reply(
            "⚠️ Join channel dulu sebelum upload!",
            reply_markup=join_buttons()
        )

    sent = await message.copy(STORAGE_CHANNEL)
    code = generate_code()

    cursor.execute("""
    INSERT INTO files (message_id, code, created)
    VALUES (?, ?, ?)
    """, (sent.id, code, datetime.now()))
    db.commit()

    link = f"https://t.me/{BOT_USERNAME}?start={code}"

    await message.reply(
        f"✅ File berhasil disimpan!\n\n"
        f"🔑 Code: `{code}`\n"
        f"🔗 Link: {link}",
        disable_web_page_preview=True
    )

# ================= DIRECT CODE =================

@app.on_message(filters.text & ~filters.command)
async def direct_code(client, message):

    code = message.text.strip()

    cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
    data = cursor.fetchone()

    if not data:
        return

    if not await is_joined(message.from_user.id):
        return await message.reply(
            "⚠️ Join channel dulu!",
            reply_markup=join_buttons(code)
        )

    await client.copy_message(
        chat_id=message.chat.id,
        from_chat_id=STORAGE_CHANNEL,
        message_id=data[0]
    )

# ================= RECHECK =================

@app.on_callback_query(filters.regex("recheck_"))
async def recheck_handler(client, callback_query):

    code = callback_query.data.split("_")[1]

    if not await is_joined(callback_query.from_user.id):
        return await callback_query.answer(
            "❌ Kamu belum join channel!",
            show_alert=True
        )

    cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
    data = cursor.fetchone()

    if not data:
        return await callback_query.answer("File tidak ditemukan", show_alert=True)

    await client.copy_message(
        chat_id=callback_query.message.chat.id,
        from_chat_id=STORAGE_CHANNEL,
        message_id=data[0]
    )

    await callback_query.message.delete()
    await callback_query.answer("✅ Verifikasi berhasil")

# ================= LIST FILE =================

async def send_page(chat_id, page, user_id):

    if not await is_joined(user_id):
        return await app.send_message(
            chat_id,
            "⚠️ Join channel dulu!",
            reply_markup=join_buttons()
        )

    cursor.execute("SELECT COUNT(*) FROM files")
    total_files = cursor.fetchone()[0]

    total_pages = math.ceil(total_files / PAGE_LIMIT)
    if total_pages == 0:
        return await app.send_message(chat_id, "Belum ada file.")

    if page < 1 or page > total_pages:
        return

    offset = (page - 1) * PAGE_LIMIT

    cursor.execute("""
    SELECT message_id FROM files
    ORDER BY id DESC
    LIMIT ? OFFSET ?
    """, (PAGE_LIMIT, offset))

    files = cursor.fetchall()

    for f in files:
        await app.copy_message(
            chat_id=chat_id,
            from_chat_id=STORAGE_CHANNEL,
            message_id=f[0]
        )

    await app.send_message(
        chat_id,
        f"📂 Halaman {page}/{total_pages}",
        reply_markup=pagination_buttons(page, total_pages)
    )

@app.on_message(filters.command("list"))
async def list_files(client, message):
    await send_page(message.chat.id, 1, message.from_user.id)

@app.on_callback_query(filters.regex("page_"))
async def page_handler(client, callback_query):
    page = int(callback_query.data.split("_")[1])
    await callback_query.message.delete()
    await send_page(callback_query.message.chat.id, page, callback_query.from_user.id)
    await callback_query.answer()

# ================= RUN =================

print("🚀 Multi Share Bot REAL FORCE JOIN Running...")
app.run()
