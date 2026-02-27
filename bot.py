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

app = Client("UltimateStorageBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

async def progress(current, total, message, start_msg):
    percent = current * 100 / total
    done = round(current / (1024 * 1024), 2)
    total_mb = round(total / (1024 * 1024), 2)

    try:
        await start_msg.edit_text(
            f"📤 Uploading...\n\n"
            f"📦 {done}MB / {total_mb}MB\n"
            f"📊 {round(percent,2)}%"
        )
    except:
        pass

# ================= START =================
@app.on_message(filters.command("start"))
async def start(client, message):
    args = message.text.split()

    if len(args) > 1:
        code = args[1]

        if not await is_joined(message.from_user.id):
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Join Group", url=f"https://t.me/{FORCE_USERNAME}")],
                [InlineKeyboardButton("✅ Sudah Join", url=f"https://t.me/{client.me.username}?start={code}")]
            ])
            return await message.reply("⚠️ Wajib join group dulu!", reply_markup=btn)

        cursor.execute("SELECT message_id FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if not data:
            return await message.reply("❌ File tidak ditemukan.")

        await client.copy_message(
            chat_id=message.chat.id,
            from_chat_id=STORAGE_GROUP,
            message_id=data[0]
        )

    else:
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 My Files", callback_data="myfiles_1")]
        ])
        await message.reply(
            "🚀 Ultimate File Storage Bot\n\n"
            "Kirim video/file untuk upload.\n"
            "Setelah upload klik Create Link.",
            reply_markup=btn
        )

# ================= HANDLE FILE =================
@app.on_message(filters.video | filters.document)
async def handle_file(client, message):

    if not await is_joined(message.from_user.id):
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 Join Group", url=f"https://t.me/{FORCE_USERNAME}")]
        ])
        return await message.reply("⚠️ Join group dulu!", reply_markup=btn)

    msg = await message.reply("⏳ Memulai upload...")

    sent = await message.copy(
        STORAGE_GROUP,
        progress=progress,
        progress_args=(message, msg)
    )

    code = generate_code()

    cursor.execute(
        "INSERT INTO files (code, message_id, file_name) VALUES (?, ?, ?)",
        (code, sent.id, message.document.file_name if message.document else "Video")
    )
    conn.commit()

    link = f"https://t.me/{client.me.username}?start={code}"

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Create Link", url=link)]
    ])

    await msg.edit_text(
        f"✅ Upload berhasil!\n\n"
        f"🆔 Code: `{code}`\n"
        f"Klik tombol di bawah untuk share.",
        reply_markup=btn
    )

# ================= PAGINATION =================
@app.on_callback_query(filters.regex("myfiles_"))
async def myfiles(client, callback_query):
    page = int(callback_query.data.split("_")[1])
    limit = 10
    offset = (page - 1) * limit

    cursor.execute("SELECT COUNT(*) FROM files")
    total = cursor.fetchone()[0]
    total_pages = math.ceil(total / limit)

    cursor.execute("SELECT code FROM files LIMIT ? OFFSET ?", (limit, offset))
    rows = cursor.fetchall()

    text = "📂 File List:\n\n"
    for r in rows:
        text += f"🔹 {r[0]}\n"

    buttons = []

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"myfiles_{page-1}"))

    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))

    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"myfiles_{page+1}"))

    buttons.append(nav)

    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

app.run()
