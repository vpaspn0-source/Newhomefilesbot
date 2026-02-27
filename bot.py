import os
import math
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
FORCE_GROUP = int(os.getenv("FORCE_GROUP"))
FORCE_USERNAME = os.getenv("FORCE_USERNAME")
STORAGE_GROUP = int(os.getenv("STORAGE_GROUP"))

app = Client("UltimateBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    code TEXT,
    message_id INTEGER,
    file_name TEXT
)
""")
conn.commit()

# ================= HELPER =================
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

async def is_joined(user_id):
    try:
        member = await app.get_chat_member(FORCE_GROUP, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def progress(current, total, message, msg):
    percent = current * 100 / total
    done = round(current / (1024*1024), 2)
    total_mb = round(total / (1024*1024), 2)
    try:
        await msg.edit_text(
            f"📤 Uploading...\n\n"
            f"📦 {done}MB / {total_mb}MB\n"
            f"📊 {round(percent,2)}%"
        )
    except:
        pass

# ================= FORCE JOIN CHECK =================
async def force_join_handler(message, code=None):
    if not await is_joined(message.from_user.id):
        buttons = [
            [InlineKeyboardButton("🔔 Join Group", url=f"https://t.me/{FORCE_USERNAME}")]
        ]
        if code:
            buttons.append(
                [InlineKeyboardButton("✅ Sudah Join", callback_data=f"recheck_{code}")]
            )

        await message.reply(
            "⚠️ Kamu wajib join group dulu!",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return False
    return True

# ================= START =================
@app.on_message(filters.command("start"))
async def start(client, message):
    args = message.text.split()

    if len(args) > 1:
        code = args[1]

        if not await force_join_handler(message, code):
            return

        cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if not data:
            return await message.reply("❌ Link tidak ditemukan.")

        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_GROUP,
            message_id=data[0]
        )

    else:
        await message.reply(
            "🚀 Ultimate Storage Bot\n\n"
            "Gunakan command:\n"
            "/upload - Upload file\n"
            "/create - Buat link terakhir\n"
            "/account - Info akun\n"
            "/mylink - Link kamu"
        )

# ================= UPLOAD =================
@app.on_message(filters.command("upload"))
async def upload_info(client, message):
    await message.reply("📤 Silakan kirim video atau file.")

@app.on_message(filters.video | filters.document)
async def handle_upload(client, message):

    if not await force_join_handler(message):
        return

    msg = await message.reply("⏳ Memulai upload...")

    sent = await message.copy(
        STORAGE_GROUP,
        progress=progress,
        progress_args=(message, msg)
    )

    code = generate_code()

    file_name = message.document.file_name if message.document else "Video"

    cursor.execute(
        "INSERT INTO files (user_id, code, message_id, file_name) VALUES (?, ?, ?, ?)",
        (message.from_user.id, code, sent.id, file_name)
    )
    conn.commit()

    await msg.edit_text(
        f"✅ Upload berhasil!\n\n"
        f"🆔 Code: `{code}`\n\n"
        "Gunakan /create untuk ambil link."
    )

# ================= CREATE LINK =================
@app.on_message(filters.command("create"))
async def create_link(client, message):

    cursor.execute(
        "SELECT code FROM files WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (message.from_user.id,)
    )
    data = cursor.fetchone()

    if not data:
        return await message.reply("❌ Tidak ada file terakhir.")

    code = data[0]
    link = f"https://t.me/{client.me.username}?start={code}"

    await message.reply(
        f"🔗 Link kamu:\n{link}\n\n🆔 Code: `{code}`"
    )

# ================= ACCOUNT =================
@app.on_message(filters.command("account"))
async def account(client, message):

    cursor.execute(
        "SELECT COUNT(*) FROM files WHERE user_id=?",
        (message.from_user.id,)
    )
    total = cursor.fetchone()[0]

    await message.reply(
        f"👤 ID: `{message.from_user.id}`\n"
        f"📂 Total Upload: {total}"
    )

# ================= MYLINK PAGINATION =================
@app.on_message(filters.command("mylink"))
async def mylink(client, message):
    await show_links(message, 1)

async def show_links(message, page):

    limit = 10
    offset = (page-1)*limit

    cursor.execute(
        "SELECT COUNT(*) FROM files WHERE user_id=?",
        (message.from_user.id,)
    )
    total = cursor.fetchone()[0]
    total_pages = max(1, math.ceil(total/limit))

    cursor.execute(
        "SELECT code FROM files WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
        (message.from_user.id, limit, offset)
    )
    rows = cursor.fetchall()

    text = "🔗 Link Kamu:\n\n"
    for r in rows:
        text += f"🆔 {r[0]}\n"

    buttons = []
    nav = []

    if page > 1:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"))

    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}"))

    buttons.append(nav)

    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("page_"))
async def pagination(client, callback_query):
    page = int(callback_query.data.split("_")[1])
    await callback_query.message.delete()
    await show_links(callback_query.message, page)

# ================= RECHECK JOIN =================
@app.on_callback_query(filters.regex("recheck_"))
async def recheck(client, callback_query):

    code = callback_query.data.split("_")[1]

    if await is_joined(callback_query.from_user.id):

        cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if data:
            await client.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=STORAGE_GROUP,
                message_id=data[0]
            )

        await callback_query.message.delete()
    else:
        await callback_query.answer("Kamu belum join!", show_alert=True)

app.run()
