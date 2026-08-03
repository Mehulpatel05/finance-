import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import init_db, add_expense, get_expenses, get_summary, delete_expense, clear_all

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
BUDGET = float(os.getenv("BUDGET", 10000))

CATEGORIES = [["🍔 Khana", "🚗 Transport", "🛍️ Shopping"],
               ["💊 Health", "🎮 Entertainment", "📚 Education"],
               ["🏠 Rent", "💡 Bills", "➕ Other"]]

MAIN_MENU = ReplyKeyboardMarkup(
    [["➕ Add Expense", "📋 My Expenses"],
     ["📊 Summary", "💰 Budget Status"],
     ["🗑️ Delete Last", "🔄 Clear All"]],
    resize_keyboard=True
)

CAT_MENU = ReplyKeyboardMarkup(CATEGORIES + [["❌ Cancel"]], resize_keyboard=True)

user_state = {}  # {user_id: {"step": ..., "category": ..., "amount": ...}}


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"💎 *Aadaab {name}!*\n\n"
        f"Main tumhara *Personal Finance Bot* hoon 🤖\n"
        f"Tumhara budget: *₹{BUDGET:,.0f}*\n\n"
        f"Apne kharche track karo aur budget manage karo! 💸",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = user_state.get(user_id, {})

    # --- ADD EXPENSE FLOW ---
    if text == "➕ Add Expense":
        user_state[user_id] = {"step": "category"}
        await update.message.reply_text("📂 *Category chunein:*", parse_mode="Markdown", reply_markup=CAT_MENU)
        return

    if state.get("step") == "category":
        if text == "❌ Cancel":
            user_state.pop(user_id, None)
            await update.message.reply_text("❌ Cancel ho gaya.", reply_markup=MAIN_MENU)
            return
        cat_name = text.split(" ", 1)[-1] if " " in text else text
        user_state[user_id] = {"step": "amount", "category": cat_name}
        await update.message.reply_text(
            f"💵 *{cat_name}* ke liye amount likhein:\n_(sirf number, jaise: 250)_",
            parse_mode="Markdown"
        )
        return

    if state.get("step") == "amount":
        try:
            amount = float(text.replace(",", ""))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Sahi amount likhein! Jaise: *250*", parse_mode="Markdown")
            return
        user_state[user_id] = {**state, "step": "note", "amount": amount}
        await update.message.reply_text(
            "📝 Note likhein _(optional, skip ke liye '-' likhein)_:",
            parse_mode="Markdown"
        )
        return

    if state.get("step") == "note":
        note = "" if text.strip() == "-" else text.strip()
        cat = state["category"]
        amount = state["amount"]
        add_expense(user_id, cat, amount, note)
        user_state.pop(user_id, None)

        total_spent = sum(r[2] for r in get_expenses(user_id))
        remaining = BUDGET - total_spent
        status = "🔴 Budget khatam!" if remaining < 0 else ("🟡 Kam bacha!" if remaining < BUDGET * 0.2 else "🟢 Theek hai")

        await update.message.reply_text(
            f"✅ *Expense add ho gaya!*\n\n"
            f"📂 Category: *{cat}*\n"
            f"💵 Amount: *₹{amount:,.0f}*\n"
            f"📝 Note: {note or 'N/A'}\n\n"
            f"💰 Total Kharch: *₹{total_spent:,.0f}*\n"
            f"💳 Bacha: *₹{remaining:,.0f}* {status}",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )
        return

    # --- MY EXPENSES ---
    if text == "📋 My Expenses":
        rows = get_expenses(user_id)
        if not rows:
            await update.message.reply_text("📭 Koi expense nahi mila!", reply_markup=MAIN_MENU)
            return
        lines = ["📋 *Tumhare Saare Kharche:*\n"]
        for r in rows[:20]:  # last 20
            note_str = f" _{r[3]}_" if r[3] else ""
            lines.append(f"`#{r[0]}` *{r[1]}* — ₹{r[2]:,.0f}{note_str}\n    📅 {r[4]}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_MENU)
        return

    # --- SUMMARY ---
    if text == "📊 Summary":
        rows = get_summary(user_id)
        if not rows:
            await update.message.reply_text("📭 Koi data nahi!", reply_markup=MAIN_MENU)
            return
        total = sum(r[1] for r in rows)
        lines = ["📊 *Category-wise Summary:*\n"]
        for cat, amt in rows:
            pct = (amt / total) * 100
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            lines.append(f"*{cat}*\n`{bar}` {pct:.1f}%\n₹{amt:,.0f}\n")
        lines.append(f"━━━━━━━━━━━━\n💸 *Total: ₹{total:,.0f}*")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_MENU)
        return

    # --- BUDGET STATUS ---
    if text == "💰 Budget Status":
        rows = get_expenses(user_id)
        total_spent = sum(r[2] for r in rows)
        remaining = BUDGET - total_spent
        used_pct = min((total_spent / BUDGET) * 100, 100)
        filled = int(used_pct / 10)
        bar = "🟥" * filled + "⬜" * (10 - filled)

        if remaining < 0:
            status_msg = f"🔴 *Budget ₹{abs(remaining):,.0f} se zyada kharch ho gaya!*"
        elif remaining < BUDGET * 0.2:
            status_msg = f"🟡 *Sirf ₹{remaining:,.0f} bacha hai — sambhal ke!*"
        else:
            status_msg = f"🟢 *Budget theek hai! ₹{remaining:,.0f} bacha hai.*"

        await update.message.reply_text(
            f"💰 *Budget Report*\n\n"
            f"🎯 Total Budget: *₹{BUDGET:,.0f}*\n"
            f"💸 Kharch: *₹{total_spent:,.0f}* ({used_pct:.1f}%)\n"
            f"💳 Bacha: *₹{remaining:,.0f}*\n\n"
            f"{bar}\n\n{status_msg}",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )
        return

    # --- DELETE LAST ---
    if text == "🗑️ Delete Last":
        rows = get_expenses(user_id)
        if not rows:
            await update.message.reply_text("📭 Koi expense nahi!", reply_markup=MAIN_MENU)
            return
        last = rows[0]
        delete_expense(user_id, last[0])
        await update.message.reply_text(
            f"🗑️ *Delete ho gaya!*\n\n"
            f"Category: *{last[1]}* — ₹{last[2]:,.0f}",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )
        return

    # --- CLEAR ALL ---
    if text == "🔄 Clear All":
        user_state[user_id] = {"step": "confirm_clear"}
        await update.message.reply_text(
            "⚠️ *Sab kuch delete karna chahte ho?*\n\nConfirm ke liye *HAAN* likhein:",
            parse_mode="Markdown"
        )
        return

    if state.get("step") == "confirm_clear":
        user_state.pop(user_id, None)
        if text.upper() == "HAAN":
            clear_all(user_id)
            await update.message.reply_text("✅ Sab expenses delete ho gaye!", reply_markup=MAIN_MENU)
        else:
            await update.message.reply_text("❌ Cancel ho gaya.", reply_markup=MAIN_MENU)
        return

    await update.message.reply_text("Menu se option chunein 👇", reply_markup=MAIN_MENU)


import asyncio


async def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot chal raha hai...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
