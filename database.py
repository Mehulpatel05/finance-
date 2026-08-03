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

def add_expense(user_id, category, amount, note=""):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO expenses (user_id, category, amount, note, date) VALUES (?,?,?,?,?)",
            (user_id, category.title(), amount, note, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )

def get_expenses(user_id):
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT id, category, amount, note, date FROM expenses WHERE user_id=? ORDER BY id DESC",
            (user_id,)
        ).fetchall()

def get_summary(user_id):
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category ORDER BY SUM(amount) DESC",
            (user_id,)
        ).fetchall()

def delete_expense(user_id, expense_id):
    with sqlite3.connect(DB) as con:
        cur = con.execute(
            "DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, user_id)
        )
        return cur.rowcount > 0

def clear_all(user_id):
    with sqlite3.connect(DB) as con:
        con.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
