import os
import sqlite3
import random
import string
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================== ENV CONFIG ==================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

STORAGE_CHANNEL = int(os.getenv("STORAGE_CHANNEL"))
FORCE_CHANNEL = os.getenv("FORCE_CHANNEL")  # tanpa @
PROMO_CHANNEL = f"https://t.me/{FORCE_CHANNEL}"

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

# =================================================

app = Client(
    "bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token,
    in_memory=True
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

# ================== UTIL ==================

def generate_code():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))


async def check_join(client, user_id):
    try:
        member = await client.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# ================== START ==================

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):

    if len(message.command) == 2:
        code = message.command[1]

        cursor.execute("SELECT * FROM files WHERE code=?", (code,))
        data = cursor.fetchone()

        if not data:
            return await message.reply_text("❌ Link tidak ditemukan.")

        joined = await check_join(client, message.from_user.id)
        if not joined:
            return await message.reply_text(
                "🚫 Wajib join channel dulu!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Join Channel", url=PROMO_CHANNEL)]]
                )
            )

        message_ids = data[1].split(",")

        progress = await message.reply_text("📦 Mengirim file...\nProgress: 0%")

        total = len(message_ids)

        for i, msg_id in enumerate(message_ids):
            await client.copy_message(
                message.chat.id,
                STORAGE_CHANNEL,
                int(msg_id)
            )

            percent = int((i + 1) / total * 100)

            await progress.edit_text(
                f"📦 Mengirim file...\nProgress: {percent}%"
            )

        cursor.execute("UPDATE files SET views = views + 1 WHERE code=?", (code,))
        db.commit()

        await progress.edit_text("✅ Semua file berhasil dikirim!")

        await message.reply_text(
            "📢 Jangan lupa join channel kami!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔔 Kunjungi Channel", url=PROMO_CHANNEL)]]
            )
        )

    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Link Saya", callback_data="my_links")]
        ])

        await message.reply_text(
            "╭━━━『 FILE SHARING BOT 』━━━╮\n"
            "┃ Kirim file untuk mulai 😎\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━╯",
            reply_markup=keyboard
        )


# ================== COLLECT FILE ==================

@app.on_message(filters.private & (filters.document | filters.video))
async def collect(client, message):

    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("❌ Hanya admin yang bisa upload!")

    forwarded = await message.forward(STORAGE_CHANNEL)

    user_id = message.from_user.id

    if user_id not in user_temp:
        user_temp[user_id] = []

    user_temp[user_id].append(str(forwarded.id))

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Tambah File", callback_data="add")],
        [InlineKeyboardButton("🗑 Reset", callback_data="reset")],
        [InlineKeyboardButton("🚀 Buat Link", callback_data="create")]
    ])

    await message.reply_text(
        f"""╭━━━『 UPLOAD PANEL 』━━━╮
┃ 📦 Total File : {len(user_temp[user_id])}
╰━━━━━━━━━━━━━━━━━━━━━━╯""",
        reply_markup=keyboard
    )


# ================== RESET ==================

@app.on_callback_query(filters.regex("^reset$"))
async def reset(client, callback):

    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Bukan admin!", show_alert=True)

    user_temp[callback.from_user.id] = []
    await callback.message.edit_text("🗑 Session berhasil direset.")


# ================== CREATE LINK ==================

@app.on_callback_query(filters.regex("^create$"))
async def create_link(client, callback):

    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Bukan admin!", show_alert=True)

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

    total_files = len(user_temp[user_id])

    user_temp[user_id] = []

    bot_username = (await client.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"

    await callback.message.reply_text(
        f"""╭━━━『 LINK BERHASIL DIBUAT 』━━━╮
┃ 📦 Total File : {total_files}
┃ 👁 View : 0
╰━━━━━━━━━━━━━━━━━━━━━━━━━━━━╯

🔗 {link}
"""
    )


# ================== MY LINKS ==================

@app.on_callback_query(filters.regex("^my_links$"))
async def my_links(client, callback):

    user_id = callback.from_user.id

    cursor.execute("SELECT code, views FROM files WHERE owner=?", (user_id,))
    data = cursor.fetchall()

    if not data:
        return await callback.message.reply_text("❌ Kamu belum punya link.")

    text = "📂 Link Kamu:\n\n"

    for code, views in data:
        text += f"🔗 {code} | 👁 {views}\n"

    await callback.message.reply_text(text)


# ================== RUN ==================

print("🔥 BOT RUNNING...")
app.run()
