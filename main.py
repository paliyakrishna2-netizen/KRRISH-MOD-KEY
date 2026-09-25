import os
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("8986167849:AAHI9QZeWkJMQ-98EaJB3UZfM6ODA5DWCAI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5382801797"))

def init_db():
    conn = sqlite3.connect("bot_store.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        balance REAL DEFAULT 0.0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plan_type TEXT,
                        key_value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS prices (
                        plan_type TEXT PRIMARY KEY,
                        price REAL)''')
    plans = [("1_hour", 10), ("1_day", 50), ("7_days", 250), ("1_month", 800)]
    cursor.executemany("INSERT OR IGNORE INTO prices VALUES (?, ?)", plans)
    conn.commit()
    conn.close()

init_db()

def get_user_balance(user_id):
    conn = sqlite3.connect("bot_store.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, 0.0)", (user_id,))
        conn.commit()
        balance = 0.0
    else:
        balance = row[0]
    conn.close()
    return balance

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Item/Key", callback_data="buy_menu")],
        [InlineKeyboardButton("💳 My Balance", callback_data="check_balance")],
        [InlineKeyboardButton("📲 Deposit / Add Funds", callback_data="deposit")]
    ]
    await update.message.reply_text(
        f"👋 नमस्ते!\n\n🆔 ID: `{user_id}`\n💰 Balance: ₹{balance}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "check_balance":
        balance = get_user_balance(user_id)
        await query.edit_message_text(f"💰 आपका बैलेंस: ₹{balance}")
    elif data == "deposit":
        await query.edit_message_text(
            f"💳 **पेमेंट करने के बाद स्क्रीनशॉट और अपनी User ID (`{user_id}`) एडमिन को भेजें।**",
            parse_mode="Markdown"
        )
    elif data == "buy_menu":
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("SELECT plan_type, price FROM prices")
        prices = dict(cursor.fetchall())
        conn.close()
        keyboard = [
            [InlineKeyboardButton(f"1 Hour - ₹{prices.get('1_hour')}", callback_data="buy_1_hour")],
            [InlineKeyboardButton(f"1 Day - ₹{prices.get('1_day')}", callback_data="buy_1_day")],
            [InlineKeyboardButton(f"7 Days - ₹{prices.get('7_days')}", callback_data="buy_7_days")],
            [InlineKeyboardButton(f"1 Month - ₹{prices.get('1_month')}", callback_data="buy_1_month")]
        ]
        await query.edit_message_text("🛒 अपना प्लान चुनें:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("buy_"):
        plan = data.replace("buy_", "")
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM prices WHERE plan_type = ?", (plan,))
        price = cursor.fetchone()[0]
        balance = get_user_balance(user_id)

        if balance < price:
            await query.edit_message_text(f"❌ पर्याप्त बैलेंस नहीं है। कीमत: ₹{price}, बैलेंस: ₹{balance}")
            conn.close()
            return

        cursor.execute("SELECT id, key_value FROM keys WHERE plan_type = ? LIMIT 1", (plan,))
        key_data = cursor.fetchone()

        if not key_data:
            await query.edit_message_text("⚠️ यह प्लान अभी आउट ऑफ स्टॉक है।")
            conn.close()
            return

        key_id, key_value = key_data
        new_balance = balance - price
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cursor.execute("DELETE FROM keys WHERE id = ?", (key_id,))
        conn.commit()
        conn.close()

        await query.edit_message_text(f"✅ **खरीद सफल रही!**\n\n🔑 Key: `{key_value}`\n💰 शेष बैलेंस: ₹{new_balance}", parse_mode="Markdown")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_user, amount = int(context.args[0]), float(context.args[1])
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_user}` का बैलेंस ₹{amount} ऐड हुआ।")
    except Exception:
        await update.message.reply_text("उपयोग: `/addbalance <user_id> <amount>`")

async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        plan, key_val = context.args[0], context.args[1]
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO keys (plan_type, key_value) VALUES (?, ?)", (plan, key_val))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Key जोड़ दी गई: `{plan}`")
    except Exception:
        await update.message.reply_text("उपयोग: `/addkey <1_hour|1_day|7_days|1_month> <key_text>`")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("addkey", add_key))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
