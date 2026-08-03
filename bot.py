import os
import asyncio
import threading
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import (init_db, get_budget, set_budget, add_expense, get_expenses, get_today_expenses,
                      get_monthly_expenses, get_summary, get_monthly_summary, get_expense_by_id,
                      update_expense, delete_expense, clear_all, get_daily_totals)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
RENDER_URL = os.getenv("RENDER_URL", "")

CATEGORIES = [["🍔 Khana", "🚗 Transport", "🛍️ Shopping"],
               ["💊 Health", "🎮 Entertainment", "📚 Education"],
               ["🏠 Rent", "💡 Bills", "➕ Other"]]

MAIN_MENU = ReplyKeyboardMarkup(
    [["➕ Add Expense", "📋 My Expenses"],
     ["📅 Aaj Ka", "📆 Is Mahine"],
     ["📊 Summary", "💰 Budget Status"],
     ["✏️ Edit Expense", "⚙️ Set Budget"],
     ["🗑️ Delete Last", "🔄 Clear All"]],
    resize_keyboard=True
)

CAT_MENU = ReplyKeyboardMarkup(CATEGORIES + [["❌ Cancel"]], resize_keyboard=True)

user_state = {}


def budget_bar(spent, budget):
    pct = min((spent / budget) * 100, 100) if budget > 0 else 0
    filled = int(pct / 10)
    return "🟥" * filled + "⬜" * (10 - filled), pct


def format_expense_list(rows, title):
    if not rows:
        return f"📭 {title} mein koi expense nahi!"
    total = sum(r[2] for r in rows)
    lines = [f"*{title}*\n"]
    for r in rows:
        note_str = f" _({r[3]})_" if r[3] else ""
        lines.append(f"`#{r[0]}` *{r[1]}* — ₹{r[2]:,.0f}{note_str}\n    📅 {r[4]}")
    lines.append(f"\n━━━━━━━━━━━━\n💸 *Total: ₹{total:,.0f}*")
    return "\n".join(lines)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    budget = get_budget(user_id)
    await update.message.reply_text(
        f"💎 *Aadaab {name}!*\n\n"
        f"Main tumhara *Personal Finance Bot* hoon 🤖\n"
        f"Tumhara budget: *₹{budget:,.0f}*\n\n"
        f"📌 *Commands:*\n"
        f"➕ Expense add karo\n"
        f"📅 Aaj ka kharch dekho\n"
        f"📆 Is mahine ka report\n"
        f"✏️ Koi entry edit karo\n"
        f"⚙️ Budget change karo\n"
        f"📊 Category summary dekho",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = user_state.get(user_id, {})
    budget = get_budget(user_id)

    # ── ADD EXPENSE ──────────────────────────────────────────
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
            f"💵 *{cat_name}* — amount likhein:\n_(jaise: 250)_",
            parse_mode="Markdown"
        )
        return

    if state.get("step") == "amount":
        try:
            amount = float(text.replace(",", ""))
            if amount <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Sahi amount likhein! Jaise: *250*", parse_mode="Markdown")
            return
        user_state[user_id] = {**state, "step": "note", "amount": amount}
        await update.message.reply_text("📝 Note likhein _(skip: '-')_:", parse_mode="Markdown")
        return

    if state.get("step") == "note":
        note = "" if text.strip() == "-" else text.strip()
        cat, amount = state["category"], state["amount"]
        add_expense(user_id, cat, amount, note)
        user_state.pop(user_id, None)

        all_exp = get_expenses(user_id, limit=9999)
        total_spent = sum(r[2] for r in all_exp)
        remaining = budget - total_spent
        bar, pct = budget_bar(total_spent, budget)

        today_exp = get_today_expenses(user_id)
        today_total = sum(r[2] for r in today_exp)

        if remaining < 0:
            status = "🔴 Budget khatam!"
        elif remaining < budget * 0.2:
            status = "🟡 Kam bacha!"
        else:
            status = "🟢 Theek hai"

        await update.message.reply_text(
            f"✅ *Expense add ho gaya!*\n\n"
            f"📂 *{cat}* — ₹{amount:,.0f}\n"
            f"📝 Note: {note or 'N/A'}\n\n"
            f"📅 Aaj ka total: *₹{today_total:,.0f}*\n"
            f"💸 Kul kharch: *₹{total_spent:,.0f}* ({pct:.1f}%)\n"
            f"💳 Bacha: *₹{remaining:,.0f}* {status}\n"
            f"{bar}",
            parse_mode="Markdown",
            reply_markup=MAIN_MENU
        )
        return

    # ── AAJ KA ───────────────────────────────────────────────
    if text == "📅 Aaj Ka":
        rows = get_today_expenses(user_id)
        await update.message.reply_text(
            format_expense_list(rows, "📅 Aaj Ke Kharche"),
            parse_mode="Markdown", reply_markup=MAIN_MENU
        )
        return

    # ── IS MAHINE ────────────────────────────────────────────
    if text == "📆 Is Mahine":
        rows = get_monthly_expenses(user_id)
        summary = get_monthly_summary(user_id)
        if not rows:
            await update.message.reply_text("📭 Is mahine koi expense nahi!", reply_markup=MAIN_MENU)
            return
        total = sum(r[2] for r in rows)
        bar, pct = budget_bar(total, budget)
        lines = [f"📆 *Is Mahine Ka Report*\n"]
        for cat, amt, cnt in summary:
            lines.append(f"• *{cat}* — ₹{amt:,.0f} ({cnt} baar)")
        lines.append(f"\n{bar} {pct:.1f}%")
        lines.append(f"💸 *Total: ₹{total:,.0f}* / ₹{budget:,.0f}")
        lines.append(f"💳 *Bacha: ₹{budget - total:,.0f}*")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_MENU)
        return

    # ── MY EXPENSES ──────────────────────────────────────────
    if text == "📋 My Expenses":
        rows = get_expenses(user_id)
        await update.message.reply_text(
            format_expense_list(rows, "📋 Last 20 Kharche"),
            parse_mode="Markdown", reply_markup=MAIN_MENU
        )
        return

    # ── SUMMARY ──────────────────────────────────────────────
    if text == "📊 Summary":
        rows = get_summary(user_id)
        if not rows:
            await update.message.reply_text("📭 Koi data nahi!", reply_markup=MAIN_MENU)
            return
        total = sum(r[1] for r in rows)
        daily = get_daily_totals(user_id, 7)
        lines = ["📊 *Category-wise Summary:*\n"]
        for cat, amt, cnt in rows:
            pct = (amt / total) * 100
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            lines.append(f"*{cat}* ({cnt}x)\n`{bar}` {pct:.1f}% — ₹{amt:,.0f}\n")
        lines.append(f"━━━━━━━━━━━━\n💸 *Total: ₹{total:,.0f}*\n")
        if daily:
            lines.append("📈 *Last 7 Din:*")
            for day, amt in daily:
                lines.append(f"  `{day}` — ₹{amt:,.0f}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_MENU)
        return

    # ── BUDGET STATUS ────────────────────────────────────────
    if text == "💰 Budget Status":
        all_exp = get_expenses(user_id, limit=9999)
        total_spent = sum(r[2] for r in all_exp)
        remaining = budget - total_spent
        bar, pct = budget_bar(total_spent, budget)
        month_rows = get_monthly_expenses(user_id)
        month_total = sum(r[2] for r in month_rows)

        if remaining < 0:
            status_msg = f"🔴 *Budget ₹{abs(remaining):,.0f} se zyada kharch!*"
        elif remaining < budget * 0.2:
            status_msg = f"🟡 *Sirf ₹{remaining:,.0f} bacha — sambhal ke!*"
        else:
            status_msg = f"🟢 *Budget safe hai!*"

        await update.message.reply_text(
            f"💰 *Budget Report*\n\n"
            f"🎯 Budget: *₹{budget:,.0f}*\n"
            f"💸 Kul Kharch: *₹{total_spent:,.0f}* ({pct:.1f}%)\n"
            f"📆 Is Mahine: *₹{month_total:,.0f}*\n"
            f"💳 Bacha: *₹{remaining:,.0f}*\n\n"
            f"{bar}\n\n{status_msg}",
            parse_mode="Markdown", reply_markup=MAIN_MENU
        )
        return

    # ── EDIT EXPENSE ─────────────────────────────────────────
    if text == "✏️ Edit Expense":
        user_state[user_id] = {"step": "edit_id"}
        rows = get_expenses(user_id, limit=5)
        lines = ["✏️ *Konsa edit karna hai? ID likhein:*\n"]
        for r in rows:
            lines.append(f"`#{r[0]}` *{r[1]}* — ₹{r[2]:,.0f} ({r[4]})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    if state.get("step") == "edit_id":
        try:
            exp_id = int(text.strip())
            row = get_expense_by_id(user_id, exp_id)
            if not row:
                await update.message.reply_text("⚠️ ID nahi mili! Sahi ID likhein.")
                return
            user_state[user_id] = {"step": "edit_amount", "edit_id": exp_id, "edit_row": row}
            await update.message.reply_text(
                f"✏️ *#{exp_id} — {row[1]}*\n"
                f"Purana amount: ₹{row[2]:,.0f}\n\n"
                f"Naya amount likhein:",
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("⚠️ Sirf number likhein!")
        return

    if state.get("step") == "edit_amount":
        try:
            new_amount = float(text.replace(",", ""))
            if new_amount <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Sahi amount likhein!")
            return
        user_state[user_id] = {**state, "step": "edit_note", "new_amount": new_amount}
        await update.message.reply_text(
            f"📝 Naya note likhein _(skip: '-')_\nPurana: _{state['edit_row'][3] or 'N/A'}_",
            parse_mode="Markdown"
        )
        return

    if state.get("step") == "edit_note":
        new_note = "" if text.strip() == "-" else text.strip()
        exp_id = state["edit_id"]
        new_amount = state["new_amount"]
        update_expense(user_id, exp_id, new_amount, new_note)
        user_state.pop(user_id, None)
        await update.message.reply_text(
            f"✅ *#{exp_id} update ho gaya!*\n\n"
            f"💵 Amount: ₹{new_amount:,.0f}\n"
            f"📝 Note: {new_note or 'N/A'}",
            parse_mode="Markdown", reply_markup=MAIN_MENU
        )
        return

    # ── SET BUDGET ───────────────────────────────────────────
    if text == "⚙️ Set Budget":
        user_state[user_id] = {"step": "set_budget"}
        await update.message.reply_text(
            f"⚙️ *Budget Set Karo*\n\nAbhi ka budget: *₹{budget:,.0f}*\n\nNaya budget likhein:",
            parse_mode="Markdown"
        )
        return

    if state.get("step") == "set_budget":
        try:
            new_budget = float(text.replace(",", ""))
            if new_budget <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Sahi amount likhein!")
            return
        set_budget(user_id, new_budget)
        user_state.pop(user_id, None)
        await update.message.reply_text(
            f"✅ *Budget set ho gaya!*\n\n🎯 Naya Budget: *₹{new_budget:,.0f}*",
            parse_mode="Markdown", reply_markup=MAIN_MENU
        )
        return

    # ── DELETE LAST ──────────────────────────────────────────
    if text == "🗑️ Delete Last":
        rows = get_expenses(user_id, limit=1)
        if not rows:
            await update.message.reply_text("📭 Koi expense nahi!", reply_markup=MAIN_MENU)
            return
        last = rows[0]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Haan Delete", callback_data=f"del_{last[0]}"),
            InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")
        ]])
        await update.message.reply_text(
            f"🗑️ *Ye delete karna hai?*\n\n`#{last[0]}` *{last[1]}* — ₹{last[2]:,.0f}\n📅 {last[4]}",
            parse_mode="Markdown", reply_markup=keyboard
        )
        return

    # ── CLEAR ALL ────────────────────────────────────────────
    if text == "🔄 Clear All":
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Haan, Sab Delete", callback_data="clear_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="del_cancel")
        ]])
        await update.message.reply_text(
            "⚠️ *Sab expenses delete ho jayenge!*\nConfirm karo:",
            parse_mode="Markdown", reply_markup=keyboard
        )
        return

    await update.message.reply_text("Menu se option chunein 👇", reply_markup=MAIN_MENU)


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data.startswith("del_") and query.data != "del_cancel":
        exp_id = int(query.data.split("_")[1])
        row = get_expense_by_id(user_id, exp_id)
        if row and delete_expense(user_id, exp_id):
            await query.edit_message_text(f"🗑️ *Delete ho gaya!*\n`#{row[0]}` *{row[1]}* — ₹{row[2]:,.0f}", parse_mode="Markdown")
        else:
            await query.edit_message_text("⚠️ Delete nahi hua!")

    elif query.data == "clear_yes":
        clear_all(user_id)
        await query.edit_message_text("✅ *Sab expenses delete ho gaye!*", parse_mode="Markdown")

    elif query.data == "del_cancel":
        await query.edit_message_text("❌ Cancel ho gaya.")


# ── SERVER & BOT RUN ─────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, *args):
        pass


def self_ping():
    import time
    while True:
        time.sleep(600)
        try:
            if RENDER_URL:
                urllib.request.urlopen(RENDER_URL, timeout=10)
        except Exception:
            pass


def run_bot():
    async def _run():
        init_db()
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        print("🤖 Bot chal raha hai...")
        async with app:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()
    asyncio.run(_run())


if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    print(f"🌐 Health server on port {PORT}")
    HTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()
