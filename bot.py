import os
import sqlite3
import string
import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ENV =================
def get_env(name):
    value = os.getenv(name)
    if not value:
        raise ValueError(f"ENV {name} belum diisi!")
    return value

API_ID = int(get_env("API_ID"))
API_HASH = get_env("API_HASH")
BOT_TOKEN = get_env("BOT_TOKEN")

STORAGE_CHANNEL = int(get_env("STORAGE_CHANNEL"))
BOT_USERNAME = get_env("BOT_USERNAME")

FORCE_CHANNEL_ID = int(get_env("FORCE_CHANNEL_ID"))
FORCE_CHANNEL_USERNAME = get_env("FORCE_CHANNEL_USERNAME")

PAGE_LIMIT = 10

# ================= BOT =================
app = Client(
    "multifilebot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT,
    code TEXT
)
""")
conn.commit()

# ================= UTIL =================
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

async def force_join(client, message):
    user_id = message.from_user.id
    try:
        member = await client.get_chat_member(FORCE_CHANNEL_ID, user_id)
        if member.status in ["left", "kicked"]:
            raise Exception("Not Joined")
        return True
    except:
        await message.reply_text(
            "🚫 Kamu harus join channel dulu!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "🔔 Join Channel",
                    url=f"https://t.me/{FORCE_CHANNEL_USERNAME}"
                )]]
            )
        )
        return False

# ================= START =================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):

    if not await force_join(client, message):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Upload", callback_data="upload")],
        [InlineKeyboardButton("🔗 Create Link", callback_data="create")],
        [InlineKeyboardButton("📂 My Files", callback_data="myfiles_1")],
        [InlineKeyboardButton("👤 Account", callback_data="account")]
    ])

    await message.reply_text(
        "✨ Welcome To Premium File Share Bot ✨\n\nPilih menu di bawah:",
        reply_markup=keyboard
    )

# ================= UPLOAD =================
@app.on_message(filters.private & (filters.video | filters.document))
async def upload_file(client, message):

    if not await force_join(client, message):
        return

    file_id = message.video.file_id if message.video else message.document.file_id

    await client.send_message(STORAGE_CHANNEL, f"#STORAGE\nUser: {message.from_user.id}")
    stored = await message.copy(STORAGE_CHANNEL)

    code = generate_code()

    cursor.execute("INSERT INTO files (file_id, code) VALUES (?,?)", (stored.id, code))
    conn.commit()

    link = f"https://t.me/{BOT_USERNAME}?start={code}"

    await message.reply_text(
        f"✅ File berhasil disimpan!\n\n"
        f"🔗 Link: {link}\n"
        f"🔑 Code: {code}"
    )

# ================= START WITH CODE =================
@app.on_message(filters.private & filters.regex("^/start "))
async def send_by_code(client, message):

    if not await force_join(client, message):
        return

    code = message.text.split(" ")[1]

    cursor.execute("SELECT file_id FROM files WHERE code=?", (code,))
    data = cursor.fetchone()

    if not data:
        return await message.reply_text("❌ Code tidak ditemukan.")

    file_msg_id = data[0]

    await client.copy_message(
        chat_id=message.chat.id,
        from_chat_id=STORAGE_CHANNEL,
        message_id=file_msg_id
    )

    await message.reply_text(
        "🔔 Jangan lupa join channel kami!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                "📢 Channel",
                url=f"https://t.me/{FORCE_CHANNEL_USERNAME}"
            )]]
        )
    )

# ================= PAGINATION =================
@app.on_callback_query(filters.regex("^myfiles_"))
async def my_files(client, callback):

    if not await force_join(client, callback.message):
        return

    page = int(callback.data.split("_")[1])
    offset = (page - 1) * PAGE_LIMIT

    cursor.execute("SELECT id, code FROM files LIMIT ? OFFSET ?", (PAGE_LIMIT, offset))
    files = cursor.fetchall()

    if not files:
        return await callback.answer("Tidak ada file.", show_alert=True)

    text = "📂 File List:\n\n"
    for f in files:
        text += f"ID: {f[0]} | Code: {f[1]}\n"

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"myfiles_{page-1}"))
    buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"myfiles_{page+1}"))

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([buttons])
    )

# ================= ACCOUNT =================
@app.on_callback_query(filters.regex("account"))
async def account(client, callback):

    if not await force_join(client, callback.message):
        return

    await callback.message.edit_text(
        f"👤 Account Info\n\n"
        f"User ID: {callback.from_user.id}\n"
        f"Username: @{callback.from_user.username}"
    )

# ================= RUN =================
app.run()
