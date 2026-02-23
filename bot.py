import os
import sqlite3
import random
import string
import json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

STORAGE_CHANNEL = int(os.getenv("STORAGE_CHANNEL"))
FORCE_CHANNEL = int(os.getenv("FORCE_CHANNEL"))

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= DATABASE =================
db = sqlite3.connect("database.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files(
    code TEXT PRIMARY KEY,
    message_ids TEXT,
    views INTEGER DEFAULT 0,
    owner INTEGER,
    total_size INTEGER
)
""")

# ================= BACKUP JSON =================
def backup_json():
    cursor.execute("SELECT * FROM files")
    rows = cursor.fetchall()
    data = []
    for r in rows:
        data.append({
            "code": r[0],
            "message_ids": r[1],
            "views": r[2],
            "owner": r[3],
            "total_size": r[4]
        })
    with open("backup.json", "w") as f:
        json.dump(data, f, indent=4)

# ================= MEMORY =================
user_temp = {}
user_size = {}

def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12))

def format_size(size):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

async def check_join(client, user_id):
    try:
        await client.get_chat_member(FORCE_CHANNEL, user_id)
        return True
    except:
        return False

# ================= START =================
@app.on_message(filters.private & filters.command("start"))
async def start(client, message):

    if len(message.command) == 2:
        code = message.command[1]

        if not await check_join(client, message.from_user.id):
            return await message.reply_text(
                "🚫 Kamu harus join channel dulu!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔔 Join Channel", url=f"https://t.me/c/{str(FORCE_CHANNEL)[4:]}")],
                    [InlineKeyboardButton("✅ Sudah Join", callback_data=f"check_{code}")]
                ])
            )

        await send_page(client, message.chat.id, code, 0)
        return

    await message.reply_text(
        "✨ PREMIUM FILE BOT\n\n"
        "📤 Kirim file/video\n"
        "🔗 Lalu ketik /create"
    )

# ================= UPLOAD =================
@app.on_message(filters.private & (filters.document | filters.video))
async def upload(client, message):

    user_id = message.from_user.id

    if user_id not in user_temp:
        user_temp[user_id] = []
        user_size[user_id] = 0

    forwarded = await message.forward(STORAGE_CHANNEL)

    size = 0
    if message.document:
        size = message.document.file_size
    if message.video:
        size = message.video.file_size

    user_temp[user_id].append(str(forwarded.id))
    user_size[user_id] += size

    await message.reply_text(
        f"📦 Total File: {len(user_temp[user_id])}\n"
        f"💾 Total Size: {format_size(user_size[user_id])}\n\n"
        f"Ketik /create untuk buat link."
    )

# ================= CREATE =================
@app.on_message(filters.private & filters.command("create"))
async def create(client, message):

    user_id = message.from_user.id

    if user_id not in user_temp or not user_temp[user_id]:
        return await message.reply_text("Belum ada file!")

    code = generate_code()
    msg_ids = ",".join(user_temp[user_id])
    total_size = user_size[user_id]

    cursor.execute(
        "INSERT INTO files(code, message_ids, owner, total_size) VALUES(?,?,?,?)",
        (code, msg_ids, user_id, total_size)
    )
    db.commit()
    backup_json()

    user_temp[user_id] = []
    user_size[user_id] = 0

    bot_username = (await client.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"

    await message.reply_text(
        f"🔐 CODE AMAN:\n{code}\n\n"
        f"🔗 LINK:\n{link}\n\n"
        f"Simpan CODE untuk restore jika bot ganti."
    )

# ================= CHECK JOIN BUTTON =================
@app.on_callback_query(filters.regex("^check_"))
async def recheck(client, callback):
    code = callback.data.split("_")[1]

    if await check_join(client, callback.from_user.id):
        await send_page(client, callback.message.chat.id, code, 0)
    else:
        await callback.answer("Belum join!", show_alert=True)

# ================= PAGINATION =================
async def send_page(client, chat_id, code, page):

    cursor.execute("SELECT * FROM files WHERE code=?", (code,))
    data = cursor.fetchone()

    if not data:
        return await client.send_message(chat_id, "❌ Link tidak ditemukan.")

    message_ids = data[1].split(",")
    total_pages = (len(message_ids)-1)//10 + 1

    start = page*10
    end = start+10
    current = message_ids[start:end]

    for msg_id in current:
        await client.copy_message(chat_id, STORAGE_CHANNEL, int(msg_id))

    cursor.execute("UPDATE files SET views = views + 1 WHERE code=?", (code,))
    db.commit()
    backup_json()

    buttons = []
    row = []

    for i in range(total_pages):
        if i == page:
            row.append(InlineKeyboardButton(f"•{i+1}•", callback_data="x"))
        else:
            row.append(InlineKeyboardButton(str(i+1), callback_data=f"page_{code}_{i}"))

        if len(row) == 5:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await client.send_message(
        chat_id,
        f"📄 Halaman {page+1}/{total_pages}\n"
        f"👁 Views: {data[2]+1}\n"
        f"📦 Total File: {len(message_ids)}\n"
        f"💾 Total Size: {format_size(data[4])}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@app.on_callback_query(filters.regex("^page_"))
async def page(client, callback):
    _, code, page = callback.data.split("_")
    await send_page(client, callback.message.chat.id, code, int(page))

app.run()
