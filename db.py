"""
db.py
-----
Real, persistent storage using SQLite - Python's built-in database engine
(no installation needed, it's part of the standard library).

THE CORE IDEA: instead of keeping customers/invoices in a Python list that
lives only in RAM (and vanishes the moment you restart the app), we store
them as ROWS in TABLES inside a single file: promise_chaser.db. Think of
a table like one tab in a spreadsheet - fixed columns, any number of rows.

THREE TABLES:
  customers    - one row per company (name, contact, payment history)
  invoices     - one row per invoice (amount, dates, escalation stage)
  actions_log  - one row per action taken (the audit trail)

WHY history IS STORED AS TEXT: SQLite doesn't have a native "list" column
type. So we convert a Python list like [True, False, True] into the text
"1,0,1" before saving, and convert it back to a list when reading. This
conversion happens in the two small helper functions below
(_history_to_text / _text_to_history) - everywhere else in the app still
just works with normal Python lists, so nothing else needs to know this
detail.

ON FIRST RUN: if promise_chaser.db doesn't exist yet, this file creates it
and fills it with the same starter data that used to live in seed_data.py.
On every run AFTER that, it just reuses whatever is already saved - so
data now genuinely persists across restarts.
"""

import sqlite3
import json
from datetime import date, timedelta
from contextlib import contextmanager

DB_PATH = "promise_chaser.db"


@contextmanager
def get_connection():
    """
    A 'context manager' - the `with get_connection() as conn:` pattern you'll
    see everywhere below. It automatically opens the connection, and
    guarantees it gets closed afterward even if an error happens in
    between. Same idea as opening a file with `with open(...) as f:`.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["amount"]
    try:
        yield conn
        conn.commit()  # save changes to disk
    finally:
        conn.close()


def _history_to_text(history_list):
    """[True, False, True] -> '1,0,1' (for storing in a TEXT column)"""
    return ",".join("1" if h else "0" for h in history_list)


def _text_to_history(text):
    """'1,0,1' -> [True, False, True] (for reading back out)"""
    if not text:
        return []
    return [c == "1" for c in text.split(",")]


def init_db():
    """Creates the tables if they don't exist yet, and seeds starter data
    on a completely fresh database only."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                industry TEXT,
                gst_no TEXT,
                payment_terms TEXT,
                history TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                invoice_no TEXT,
                description TEXT,
                amount INTEGER NOT NULL,
                due_date TEXT,
                promise_date TEXT,
                status TEXT,
                escalation_stage INTEGER DEFAULT 0,
                broken_promises_on_this_invoice INTEGER DEFAULT 0,
                last_action_at TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER,
                customer_name TEXT,
                action TEXT,
                explanation TEXT,
                delivery_detail TEXT,
                triggered_by TEXT,
                timestamp TEXT
            )
        """)

        # Only seed starter data if the customers table is completely empty -
        # this check is what makes it safe to restart the app repeatedly
        # without wiping your data or re-adding duplicates every time.
        existing = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()
        if existing["c"] == 0:
            _seed_starter_data(conn)


def _seed_starter_data(conn):
    """Same starter companies/invoices that used to live in seed_data.py,
    now inserted as real database rows on first run only."""

    def days_ago(n):
        return (date.today() - timedelta(days=n)).isoformat()

    def days_from_now(n):
        return (date.today() + timedelta(days=n)).isoformat()

    customers = [
        (1, "Aarav Textiles Pvt Ltd", "aarav.textiles@example.com", "Textiles Exporter", "27AACPT1234K1Z5", "Net 30", [True, True, True, True, True, True]),
        (2, "Nova Digital Solutions", "billing@novadigital.example.com", "IT Consulting", "29AACCN5678L1Z2", "Net 15", [True, False, True, True, False, True]),
        (3, "Bright Future Traders", "accounts@brightfuture.example.com", "Wholesale Trading", "07AABCB4321M1Z8", "Net 45", [False, False, True, False, False]),
        (4, "Kalpana Interiors", "kalpana.interiors@example.com", "Interior Design", "19AAECK8765N1Z3", "Net 30", [True, True, False, True, True, True, True]),
        (5, "Zenith Logistics", "finance@zenithlogistics.example.com", "Freight & Logistics", "24AACCZ2468P1Z6", "Net 60", [False, False, False, False, True, False]),
        (6, "Meera Handicrafts", "meera.handicrafts@example.com", "Handicrafts Retail", "08AABFM1357Q1Z9", "Net 15", [True, True, True]),
        (7, "Orbit Tech Consulting", "orbit.consulting@example.com", "IT Consulting", "33AABCO9753R1Z1", "Net 30", [False, True, False, True, False]),
        (8, "Sunrise Hospitality Group", "ap@sunrisehospitality.example.com", "Hospitality (seasonal cash flow)", "36AABCS8642S1Z4", "Net 45", [True, False, False, False, False, False]),
    ]
    for c in customers:
        conn.execute(
            "INSERT INTO customers (id, name, contact, industry, gst_no, payment_terms, history) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c[0], c[1], c[2], c[3], c[4], c[5], _history_to_text(c[6])),
        )

    invoices = [
        (101, 3, "INV/24-25/0847", "Bulk stationery & office supplies order", 84000, days_ago(20), days_ago(6), "broken", 1, 1),
        (102, 5, "INV/24-25/0612", "Freight & warehousing services, Q2", 152000, days_ago(35), days_ago(15), "broken", 3, 3),
        (103, 1, "INV/24-25/1023", "Bulk cotton fabric export order", 45000, days_ago(3), days_from_now(2), "promised", 0, 0),
        (104, 7, "INV/24-25/0755", "Cloud infra consulting, monthly retainer", 63000, days_ago(12), days_ago(2), "broken", 1, 1),
        (105, 8, "INV/24-25/0399", "Banquet & event catering services", 210000, days_ago(40), days_ago(20), "broken", 4, 3),
        (106, 2, "INV/24-25/0921", "6-month SaaS subscription renewal", 38000, days_ago(8), days_ago(1), "broken", 1, 1),
        (107, 4, "INV/24-25/1104", "Office interior fit-out, phase 2", 27500, days_ago(1), days_from_now(4), "promised", 0, 0),
        (108, 6, "INV/24-25/0888", "Festive season handicraft supply order", 19000, days_ago(5), days_ago(0), "broken", 1, 1),
    ]
    for inv in invoices:
        conn.execute(
            """INSERT INTO invoices
               (id, customer_id, invoice_no, description, amount, due_date, promise_date, status, escalation_stage, broken_promises_on_this_invoice)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            inv,
        )


# --- Customer queries --------------------------------------------------

def get_all_customers():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM customers").fetchall()
        return [_customer_row_to_dict(r) for r in rows]


def get_customer(customer_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return _customer_row_to_dict(row) if row else None


def add_customer(name, contact, industry, gst_no, payment_terms, history):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, contact, industry, gst_no, payment_terms, history) VALUES (?, ?, ?, ?, ?, ?)",
            (name, contact, industry, gst_no, payment_terms, _history_to_text(history)),
        )
        return cur.lastrowid


def _customer_row_to_dict(row):
    d = dict(row)
    d["history"] = _text_to_history(d["history"])
    return d


# --- Invoice queries -----------------------------------------------------

def get_all_invoices():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM invoices").fetchall()
        return [dict(r) for r in rows]


def get_invoice(invoice_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return dict(row) if row else None


def add_invoice(customer_id, invoice_no, description, amount, due_date, promise_date, status):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO invoices
               (customer_id, invoice_no, description, amount, due_date, promise_date, status, escalation_stage, broken_promises_on_this_invoice)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)""",
            (customer_id, invoice_no, description, amount, due_date, promise_date, status),
        )
        return cur.lastrowid


def update_invoice(invoice_id, **fields):
    """
    Flexible update - pass any column names as keyword arguments, e.g.
    update_invoice(101, status="paid") or
    update_invoice(101, escalation_stage=2, last_action_at="2026-01-01T10:00:00").
    Builds the SQL "SET column = ?, column2 = ?" part dynamically from
    whatever fields you pass in.
    """
    if not fields:
        return
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [invoice_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE invoices SET {set_clause} WHERE id = ?", values)


# --- Audit log queries -----------------------------------------------------

def add_log_entry(invoice_id, customer_name, action, explanation, delivery_detail, triggered_by, timestamp):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO actions_log
               (invoice_id, customer_name, action, explanation, delivery_detail, triggered_by, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (invoice_id, customer_name, action, explanation, delivery_detail, triggered_by, timestamp),
        )


def get_all_logs():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM actions_log ORDER BY log_id DESC").fetchall()
        return [dict(r) for r in rows]


def get_logs_for_invoice(invoice_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM actions_log WHERE invoice_id = ? ORDER BY log_id DESC", (invoice_id,)
        ).fetchall()
        return [dict(r) for r in rows]
