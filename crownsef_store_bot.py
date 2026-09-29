# Crownsef Store Telegram Bot + Simple Admin Panel
# Install: pip install python-telegram-bot
# Run: python bot.py
#
# IMPORTANT:
# 1) Put your BotFather token in BOT_TOKEN.
# 2) Put YOUR Telegram numeric user ID in ADMIN_ID.
#    Do NOT share your bot token with anyone.

import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 123456789  # <-- replace with your Telegram numeric ID

DB = "store.db"


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            product_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            delivery TEXT DEFAULT ''
        )
    """)
    con.commit()
    con.close()


def is_admin(user_id):
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍 View Products", callback_data="products")],
        [InlineKeyboardButton("📦 My Orders", callback_data="orders")],
        [InlineKeyboardButton("🆘 Support", callback_data="support")],
    ]
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin")])

    await update.message.reply_text(
        "👑 Welcome to Crownsef Store!\n\n"
        "Premium digital services at affordable prices.\n"
        "Select a product below to place your order.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    rows = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    con.close()

    if not rows:
        text = "🛍 No products have been added yet."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    keyboard = []
    for p in rows:
        keyboard.append([
            InlineKeyboardButton(
                f"{p['name']} — ₹{p['price']}",
                callback_data=f"buy:{p['id']}"
            )
        ])

    text = "🛍 *Available Products*\n\nTap a product to view details."
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query
    con = db()
    p = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    con.close()

    if not p:
        await q.answer("Product not found.", show_alert=True)
        return

    keyboard = [[
        InlineKeyboardButton("🛒 Place Order", callback_data=f"order:{product_id}")
    ], [
        InlineKeyboardButton("⬅️ Back", callback_data="products")
    ]]

    await q.edit_message_text(
        f"🛍 *{p['name']}*\n\n"
        f"💰 Price: ₹{p['price']}\n\n"
        f"📝 {p['description']}\n\n"
        "Press *Place Order* to create an order.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def create_order(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query
    user = update.effective_user

    con = db()
    p = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()

    if not p:
        con.close()
        await q.answer("Product not found.", show_alert=True)
        return

    cur = con.execute(
        "INSERT INTO orders (user_id, username, product_id) VALUES (?, ?, ?)",
        (user.id, user.username or "", product_id)
    )
    order_id = cur.lastrowid
    con.commit()
    con.close()

    # Notify admin
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 *New Order #{order_id}*\n\n"
            f"👤 User: @{user.username or 'no_username'}\n"
            f"🆔 User ID: `{user.id}`\n"
            f"🛍 Product: {p['name']}\n"
            f"💰 Amount: ₹{p['price']}\n\n"
            f"Use `/deliver {order_id} YOUR_DELIVERY_TEXT` to deliver.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await q.edit_message_text(
        f"✅ *Order Created!*\n\n"
        f"Order ID: #{order_id}\n"
        f"Product: {p['name']}\n"
        f"Amount: ₹{p['price']}\n\n"
        "Payment/delivery can be handled by the admin.",
        parse_mode="Markdown"
    )


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    con = db()
    rows = con.execute("""
        SELECT orders.id, products.name, products.price,
               orders.status, orders.delivery
        FROM orders
        JOIN products ON products.id = orders.product_id
        WHERE orders.user_id=?
        ORDER BY orders.id DESC
    """, (user_id,)).fetchall()
    con.close()

    if not rows:
        text = "📦 You have no orders yet."
    else:
        parts = ["📦 *Your Orders*\n"]
        for o in rows:
            item = (
                f"#{o['id']} — {o['name']}\n"
                f"💰 ₹{o['price']} | Status: {o['status']}"
            )
            if o["delivery"]:
                item += f"\n📩 Delivery: {o['delivery']}"
            parts.append(item)
        text = "\n\n".join(parts)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin access only.")
        return

    await update.message.reply_text(
        "⚙️ *Admin Panel*\n\n"
        "➕ Add product:\n"
        "`/addproduct Product Name | 399 | Product description`\n\n"
        "🗑 Delete product:\n"
        "`/deleteproduct PRODUCT_ID`\n\n"
        "📋 Products:\n"
        "`/adminproducts`\n\n"
        "📦 Orders:\n"
        "`/adminorders`\n\n"
        "📩 Deliver order:\n"
        "`/deliver ORDER_ID Delivery text`\n\n"
        "💡 Example:\n"
        "`/addproduct Canva Owner Panel | 399 | Email and password provided`",
        parse_mode="Markdown"
    )


async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin access only.")
        return

    raw = update.message.text.partition(" ")[2].strip()
    parts = [x.strip() for x in raw.split("|", 2)]

    if len(parts) != 3:
        await update.message.reply_text(
            "Format:\n/addproduct Name | Price | Description\n\n"
            "Example:\n/addproduct Canva Owner Panel | 399 | Email and password provided"
        )
        return

    name, price_text, description = parts
    try:
        price = int(price_text)
    except ValueError:
        await update.message.reply_text("❌ Price must be a number.")
        return

    con = db()
    cur = con.execute(
        "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
        (name, price, description)
    )
    product_id = cur.lastrowid
    con.commit()
    con.close()

    await update.message.reply_text(
        f"✅ Product added!\n\n"
        f"ID: {product_id}\n"
        f"🛍 {name}\n"
        f"💰 ₹{price}\n"
        f"📝 {description}"
    )


async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin access only.")
        return

    con = db()
    rows = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    con.close()

    if not rows:
        await update.message.reply_text("No products.")
        return

    text = "📋 *Products*\n\n"
    for p in rows:
        text += f"ID {p['id']} — {p['name']} — ₹{p['price']}\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin access only.")
        return

    raw = update.message.text.partition(" ")[2].strip()
    try:
        product_id = int(raw)
    except ValueError:
        await update.message.reply_text("Usage: /deleteproduct PRODUCT_ID")
        return

    con = db()
    cur = con.execute("DELETE FROM products WHERE id=?", (product_id,))
    con.commit()
    con.close()

    if cur.rowcount:
        await update.message.reply_text("✅ Product deleted.")
    else:
        await update.message.reply_text("❌ Product ID not found.")


async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin access only.")
        return

    con = db()
    rows = con.execute("""
        SELECT orders.id, orders.user_id, orders.username,
               products.name, products.price, orders.status
        FROM orders
        JOIN products ON products.id = orders.product_id
        ORDER BY orders.id DESC
    """).fetchall()
    con.close()

    if not rows:
        await update.message.reply_text("📦 No orders yet.")
        return

    text = "📦 *Recent Orders*\n\n"
    for o in rows:
        text += (
            f"#{o['id']} — {o['name']} — ₹{o['price']}\n"
            f"User: @{o['username'] or 'none'} ({o['user_id']})\n"
            f"Status: {o['status']}\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


async def deliver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin access only.")
        return

    raw = update.message.text.partition(" ")[2].strip()
    parts = raw.split(" ", 1)

    if len(parts) != 2:
        await update.message.reply_text(
            "Usage:\n/deliver ORDER_ID Delivery text"
        )
        return

    try:
        order_id = int(parts[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid order ID.")
        return

    delivery_text = parts[1]

    con = db()
    order = con.execute(
        "SELECT * FROM orders WHERE id=?", (order_id,)
    ).fetchone()

    if not order:
        con.close()
        await update.message.reply_text("❌ Order not found.")
        return

    con.execute(
        "UPDATE orders SET status='Delivered', delivery=? WHERE id=?",
        (delivery_text, order_id)
    )
    con.commit()
    con.close()

    try:
        await context.bot.send_message(
            order["user_id"],
            f"✅ *Order #{order_id} Delivered!*\n\n"
            f"📩 {delivery_text}",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await update.message.reply_text("✅ Delivery sent to the customer.")


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🆘 Support\n\nContact the store admin for help."
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data

    if data == "products":
        await products(update, context)
    elif data == "orders":
        await my_orders(update, context)
    elif data == "support":
        await support(update, context)
    elif data == "admin":
        if not is_admin(q.from_user.id):
            await q.answer("Admin only.", show_alert=True)
            return
        await q.edit_message_text(
            "⚙️ Admin Panel\n\n"
            "Use these commands in the chat:\n\n"
            "/addproduct Name | Price | Description\n"
            "/adminproducts\n"
            "/adminorders\n"
            "/deleteproduct ID\n"
            "/deliver ORDER_ID Delivery text"
        )
    elif data.startswith("buy:"):
        await buy(update, context, int(data.split(":")[1]))
    elif data.startswith("order:"):
        await create_order(update, context, int(data.split(":")[1]))


def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Set BOT_TOKEN before running the bot.")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products))
    app.add_handler(CommandHandler("orders", my_orders))
    app.add_handler(CommandHandler("support", support))

    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addproduct", add_product))
    app.add_handler(CommandHandler("adminproducts", admin_products))
    app.add_handler(CommandHandler("adminorders", admin_orders))
    app.add_handler(CommandHandler("deleteproduct", delete_product))
    app.add_handler(CommandHandler("deliver", deliver))

    app.add_handler(CallbackQueryHandler(callback_router))

    print("Crownsef Store bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
