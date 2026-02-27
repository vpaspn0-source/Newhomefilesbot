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

CHANNEL_USERNAME = get_env("CHANNEL_USERNAME")  # hanya tombol saja

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
    file_msg_id INTEGER,
    code TEXT
)
""")
conn.commit()

# ================= UTIL =================
def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def join_button():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(
            "📢 Join Channel",
            url=f"https://t.me/{CHANNEL_USERNAME}"
        )]]
    )

# ================= START =================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Upload", callback_data="upload")],
        [InlineKeyboardButton("🔗 Create Link", callback_data="create")],
        [InlineKeyboardButton("📂 My Files", callback_data="myfiles_1")],
        [InlineKeyboardButton("👤 Account", callback_data="account")]
    ])

    await message.reply_text(
        "✨ Premium File Share Bot ✨\n\n"
        "Gunakan menu di bawah untuk mulai.",
        reply_markup=keyboard
    )

# ================= UPLOAD =================
@app.on_message(filters.private & (filters.video | filters.document))
async def upload_file(client, message):

    await client.send_message(STORAGE_CHANNEL, f"#UPLOAD User: {message.from_user.id}")
    stored = await message.copy(STORAGE_CHANNEL)

    code = generate_code()

    cursor.execute(
        "INSERT INTO files (file_msg_id, code) VALUES (?,?)",
        (stored.id, code)
    )
    conn.commit()

    link = f"https://t.me/{BOT_USERNAME}?start={code}"

    await message.reply_text(
        f"✅ File berhasil disimpan!\n\n"
        f"🔗 Link:\n{link}\n\n"
        f"🔑 Code:\n{code}",
        reply_markup=join_button()
    )

# ================= START WITH CODE =================
@app.on_message(filters.private & filters.regex("^/start "))
async def send_by_code(client, message):

    code = message.text.split(" ")[1]

    cursor.execute("SELECT file_msg_id FROM files WHERE code=?", (code,))
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
        "🔔 Notifikasi Bot\nTerima kasih sudah menggunakan bot kami.",
        reply_markup=join_button()
    )

# ================= PAGINATION =================
@app.on_callback_query(filters.regex("^myfiles_"))
async def my_files(client, callback):

    page = int(callback.data.split("_")[1])
    offset = (page - 1) * PAGE_LIMIT

    cursor.execute("SELECT id, code FROM files LIMIT ? OFFSET ?", (PAGE_LIMIT, offset))
    files = cursor.fetchall()

    if not files:
        return await callback.answer("Tidak ada file.", show_alert=True)

    text = "📂 File List\n\n"
    for f in files:
        text += f"ID: {f[0]} | Code: {f[1]}\n"

    buttons = []
    nav = []

    if page > 1:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"myfiles_{page-1}"))
    nav.append(InlineKeyboardButton("Next ➡", callback_data=f"myfiles_{page+1}"))

    buttons.append(nav)

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= ACCOUNT =================
@app.on_callback_query(filters.regex("account"))
async def account(client, callback):

    await callback.message.edit_text(
        f"👤 Account Info\n\n"
        f"User ID: {callback.from_user.id}\n"
        f"Username: @{callback.from_user.username}",
        reply_markup=join_button()
    )

# ================= RUN =================
app.run()
