"""Items (reagents, consumables) with lots, locations, quantities, expiry dates and a usage log."""
import csv
import datetime
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, catalog_no TEXT, supplier TEXT, cas TEXT,
    lot TEXT, location TEXT, unit TEXT NOT NULL DEFAULT 'unit',
    quantity REAL NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    min_quantity REAL NOT NULL DEFAULT 0,
    expiry TEXT, opened TEXT, hazard TEXT, notes TEXT DEFAULT '',
    added TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    item_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
    date TEXT NOT NULL, amount REAL NOT NULL, user TEXT, purpose TEXT
);
"""
FIELDS = ("name", "catalog_no", "supplier", "cas", "lot", "location", "unit", "quantity", "min_quantity", "expiry",
          "opened", "hazard", "notes")


class Inventory:
    def __init__(self, path=None, today=None):
        self.db = sqlite3.connect(path or os.environ.get("LAB_INVENTORY_DB", "inventory.sqlite"))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self._today = today

    def today(self):
        return self._today or datetime.date.today()

    def close(self):
        self.db.close()

    def add(self, name, quantity=0, unit="unit", **fields):
        unknown = set(fields) - set(FIELDS)
        if unknown:
            raise ValueError("unknown field(s): %s" % ", ".join(sorted(unknown)))
        if fields.get("expiry"):
            datetime.date.fromisoformat(fields["expiry"])
        cols = ["name", "quantity", "unit", "added"] + list(fields)
        vals = [name, float(quantity), unit, self.today().isoformat()] + list(fields.values())
        with self.db:
            cur = self.db.execute("INSERT INTO items (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" * len(cols))), vals)
        return cur.lastrowid

    def get(self, item_id):
        r = self.db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if r is None:
            raise KeyError(item_id)
        return dict(r)

    def use(self, item_id, amount, user="", purpose=""):
        """Withdraw an amount; refuses to go below zero. Returns remaining quantity."""
        item = self.get(item_id)
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > item["quantity"]:
            raise ValueError("only %g %s of %s left" % (item["quantity"], item["unit"], item["name"]))
        with self.db:
            self.db.execute("UPDATE items SET quantity = quantity - ?, opened = COALESCE(opened, ?) WHERE id = ?",
                            (amount, self.today().isoformat(), item_id))
            self.db.execute("INSERT INTO usage VALUES (?, ?, ?, ?, ?)", (item_id, self.today().isoformat(), amount, user, purpose))
        return item["quantity"] - amount

    def restock(self, item_id, amount, lot=None, expiry=None):
        self.get(item_id)
        with self.db:
            self.db.execute("UPDATE items SET quantity = quantity + ? WHERE id = ?", (amount, item_id))
            if lot:
                self.db.execute("UPDATE items SET lot = ? WHERE id = ?", (lot, item_id))
            if expiry:
                self.db.execute("UPDATE items SET expiry = ? WHERE id = ?", (expiry, item_id))

    def search(self, text="", location=None):
        sql = "SELECT * FROM items WHERE (name LIKE ? OR catalog_no LIKE ? OR cas LIKE ? OR notes LIKE ?)"
        args = ["%" + text + "%"] * 4
        if location:
            sql += " AND location LIKE ?"
            args.append(location + "%")
        return [dict(r) for r in self.db.execute(sql + " ORDER BY name, expiry", args)]

    def alerts(self, days=30):
        """Expired items, items expiring within `days`, and items at or below their minimum stock."""
        today = self.today()
        soon = (today + datetime.timedelta(days=days)).isoformat()
        rows = [dict(r) for r in self.db.execute("SELECT * FROM items ORDER BY expiry")]
        expired = [r for r in rows if r["expiry"] and r["expiry"] < today.isoformat() and r["quantity"] > 0]
        expiring = [r for r in rows if r["expiry"] and today.isoformat() <= r["expiry"] <= soon and r["quantity"] > 0]
        low = [r for r in rows if r["min_quantity"] and r["quantity"] <= r["min_quantity"]]
        return {"expired": expired, "expiring": expiring, "low_stock": low}

    def usage_summary(self, since_days=90):
        since = (self.today() - datetime.timedelta(days=since_days)).isoformat()
        q = ("SELECT i.name, i.unit, SUM(u.amount) total, COUNT(*) n FROM usage u JOIN items i ON i.id = u.item_id "
             "WHERE u.date >= ? GROUP BY u.item_id ORDER BY total DESC")
        return [dict(r) for r in self.db.execute(q, (since,))]

    def import_csv(self, path):
        n = 0
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                fields = {k: v for k, v in row.items() if k in FIELDS and v not in (None, "") and k not in ("name", "quantity", "unit")}
                self.add(row["name"], float(row.get("quantity") or 0), row.get("unit") or "unit", **fields)
                n += 1
        return n

    def export_csv(self, path):
        rows = [dict(r) for r in self.db.execute("SELECT * FROM items ORDER BY id")]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id"] + list(FIELDS) + ["added"])
            w.writeheader()
            w.writerows(rows)
        return len(rows)
