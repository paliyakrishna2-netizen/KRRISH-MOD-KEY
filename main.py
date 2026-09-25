import os
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
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
    
    # Naye plans aur unke prices
    plans = [
        ("5_hours", 20),
        ("1_day", 80),
        ("3_days", 150),
        ("7_days", 250),
        ("14_days", 350),
        ("30_days", 500)
    ]
    cursor.executemany("INSERT OR REPLACE INTO prices VALUES (?, ?)", plans)
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
        f"👋 Namaste!\n\n🆔 ID: `{user_id}`\n💰 Balance: ₹{balance}",
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
        await query.edit_message_text(f"💰 Aapka Balance: ₹{balance}")
    elif data == "deposit":
        await query.edit_message_text(
            f"💳 **To Add Funds / Balance:**\n\n"
            f"1. Payment karne ke baad screenshot Admin ko bheje.\n"
            f"2. Apni **User ID:** `{user_id}` bhi bheje.\n\n"
            f"📩 **Admin se contact karne ke liye yahan click kare:** @KRRISHSELLER1",
            parse_mode="Markdown"
        )
    elif data == "buy_menu":
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("SELECT plan_type, price FROM prices")
        prices = dict(cursor.fetchall())
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton(f"5 Hours - ₹{prices.get('5_hours', 20)}/Device", callback_data="buy_5_hours")],
            [InlineKeyboardButton(f"1 Day - ₹{prices.get('1_day', 80)}/Device", callback_data="buy_1_day")],
            [InlineKeyboardButton(f"3 Days - ₹{prices.get('3_days', 150)}/Device", callback_data="buy_3_days")],
            [InlineKeyboardButton(f"7 Days - ₹{prices.get('7_days', 250)}/Device", callback_data="buy_7_days")],
            [InlineKeyboardButton(f"14 Days - ₹{prices.get('14_days', 350)}/Device", callback_data="buy_14_days")],
            [InlineKeyboardButton(f"30 Days - ₹{prices.get('30_days', 500)}/Device", callback_data="buy_30_days")]
        ]
        await query.edit_message_text("🛒 Apna plan chune:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("buy_"):
        plan = data.replace("buy_", "")
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM prices WHERE plan_type = ?", (plan,))
        row = cursor.fetchone()
        
        if not row:
            await query.edit_message_text("❌ Ye plan available nahi hai.")
            conn.close()
            return
            
        price = row[0]
        balance = get_user_balance(user_id)

        if balance < price:
            await query.edit_message_text(f"❌ Paryaapt balance nahi hai. Keemat: ₹{price}, Balance: ₹{balance}")
            conn.close()
            return

        cursor.execute("SELECT id, key_value FROM keys WHERE plan_type = ? LIMIT 1", (plan,))
        key_data = cursor.fetchone()

        if not key_data:
            await query.edit_message_text("⚠️ Yeh plan abhi out of stock hai.")
            conn.close()
            return

        key_id, key_value = key_data
        new_balance = balance - price
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cursor.execute("DELETE FROM keys WHERE id = ?", (key_id,))
        conn.commit()
        conn.close()

        await query.edit_message_text(f"✅ **Khareed safal rahi!**\n\n🔑 Key: `{key_value}`\n💰 Shesh Balance: ₹{new_balance}", parse_mode="Markdown")

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        target_user, amount = int(context.args[0]), float(context.args[1])
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_user,))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (target_user, amount))
        else:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user))
            
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User `{target_user}` ka balance ₹{amount} add ho gaya.", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("Upyog: `/addbalance <user_id> <amount>`")

async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        plan, key_val = context.args[0], context.args[1]
        conn = sqlite3.connect("bot_store.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO keys (plan_type, key_value) VALUES (?, ?)", (plan, key_val))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Key jod di gayi: `{plan}`", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("Upyog: `/addkey <5_hours|1_day|3_days|7_days|14_days|30_days> <key_text>`")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("addkey", add_key))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
