import sqlite3
from datetime import datetime

DB = "expenses.db"

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                amount REAL,
                note TEXT,
                date TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER PRIMARY KEY,
                budget REAL DEFAULT 10000
            )
        """)

def get_budget(user_id):
    with sqlite3.connect(DB) as con:
        row = con.execute("SELECT budget FROM budgets WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row else 10000.0

def set_budget(user_id, amount):
    with sqlite3.connect(DB) as con:
        con.execute("INSERT OR REPLACE INTO budgets (user_id, budget) VALUES (?,?)", (user_id, amount))

def add_expense(user_id, category, amount, note=""):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO expenses (user_id, category, amount, note, date) VALUES (?,?,?,?,?)",
            (user_id, category.title(), amount, note, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )

def get_expenses(user_id, limit=20):
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT id, category, amount, note, date FROM expenses WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()

def get_today_expenses(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT id, category, amount, note, date FROM expenses WHERE user_id=? AND date LIKE ? ORDER BY id DESC",
            (user_id, f"{today}%")
        ).fetchall()

def get_monthly_expenses(user_id):
    month = datetime.now().strftime("%Y-%m")
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT id, category, amount, note, date FROM expenses WHERE user_id=? AND date LIKE ? ORDER BY id DESC",
            (user_id, f"{month}%")
        ).fetchall()

def get_summary(user_id):
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT category, SUM(amount), COUNT(*) FROM expenses WHERE user_id=? GROUP BY category ORDER BY SUM(amount) DESC",
            (user_id,)
        ).fetchall()

def get_monthly_summary(user_id):
    month = datetime.now().strftime("%Y-%m")
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT category, SUM(amount), COUNT(*) FROM expenses WHERE user_id=? AND date LIKE ? GROUP BY category ORDER BY SUM(amount) DESC",
            (user_id, f"{month}%")
        ).fetchall()

def get_expense_by_id(user_id, expense_id):
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT id, category, amount, note, date FROM expenses WHERE id=? AND user_id=?",
            (expense_id, user_id)
        ).fetchone()

def update_expense(user_id, expense_id, amount, note):
    with sqlite3.connect(DB) as con:
        cur = con.execute(
            "UPDATE expenses SET amount=?, note=? WHERE id=? AND user_id=?",
            (amount, note, expense_id, user_id)
        )
        return cur.rowcount > 0

def delete_expense(user_id, expense_id):
    with sqlite3.connect(DB) as con:
        cur = con.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, user_id))
        return cur.rowcount > 0

def clear_all(user_id):
    with sqlite3.connect(DB) as con:
        con.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))

def get_daily_totals(user_id, days=7):
    with sqlite3.connect(DB) as con:
        return con.execute(
            """SELECT substr(date,1,10) as day, SUM(amount)
               FROM expenses WHERE user_id=?
               GROUP BY day ORDER BY day DESC LIMIT ?""",
            (user_id, days)
        ).fetchall()
