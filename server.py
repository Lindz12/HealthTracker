"""Tiny local server for index.html that stores your logs in a SQLite database.

Run:   python server.py            (then open http://127.0.0.1:8000)
Data:  health.db next to this file (open it with DB Browser for SQLite, DBeaver,
       VS Code SQLite extensions, or `sqlite3 health.db`).

Only the Python standard library is used. The server listens on 127.0.0.1 only,
so nothing is reachable from other computers.
"""
import json
import math
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "health.db")
PAGE = os.path.join(HERE, "index.html")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BODY = 5 * 1024 * 1024

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_log (
    log_date   TEXT PRIMARY KEY,          -- YYYY-MM-DD
    calories   REAL,                      -- kcal
    protein_g  REAL,                      -- grams
    steps      REAL,
    weight_kg  REAL
);
CREATE TABLE IF NOT EXISTS weekly_targets (
    week_start TEXT PRIMARY KEY,          -- Sunday, YYYY-MM-DD; applies from this week on
    calories   REAL,
    protein_g  REAL,
    steps      REAL
);
CREATE TABLE IF NOT EXISTS profile (
    key   TEXT PRIMARY KEY,
    value TEXT                            -- JSON-encoded value
);
-- Weeks run Sunday to Saturday.
CREATE VIEW IF NOT EXISTS weekly_summary AS
SELECT date(log_date, '-' || strftime('%w', log_date) || ' days') AS week_start,
       COUNT(*)                         AS days_logged,
       ROUND(AVG(calories), 0)          AS avg_calories,
       ROUND(AVG(protein_g), 1)         AS avg_protein_g,
       ROUND(AVG(steps), 0)             AS avg_steps,
       ROUND(AVG(weight_kg), 2)         AS avg_weight_kg
FROM daily_log
GROUP BY week_start
ORDER BY week_start;
"""


def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if math.isfinite(v) else None


def clean(x):
    """Whole numbers come back as ints so the page shows 2100, not 2100.0."""
    return None if x is None else (int(x) if float(x).is_integer() else x)


def read_all(conn):
    days, targets, profile = {}, {}, {}
    for d, c, p, s, w in conn.execute(
            "SELECT log_date, calories, protein_g, steps, weight_kg FROM daily_log"):
        rec = {k: clean(v) for k, v in (("cal", c), ("pro", p), ("steps", s), ("wt", w)) if v is not None}
        if rec:
            days[d] = rec
    for ws, c, p, s in conn.execute(
            "SELECT week_start, calories, protein_g, steps FROM weekly_targets"):
        rec = {k: clean(v) for k, v in (("cal", c), ("pro", p), ("steps", s)) if v is not None}
        if rec:
            targets[ws] = rec
    for k, v in conn.execute("SELECT key, value FROM profile"):
        try:
            profile[k] = json.loads(v)
        except ValueError:
            pass
    return {"profile": profile, "days": days, "targets": targets}


def write_all(conn, data):
    """Replace the stored data with what the page sends (one transaction)."""
    days = data.get("days") if isinstance(data.get("days"), dict) else {}
    targets = data.get("targets") if isinstance(data.get("targets"), dict) else {}
    profile = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    with conn:
        conn.execute("DELETE FROM daily_log")
        conn.execute("DELETE FROM weekly_targets")
        conn.execute("DELETE FROM profile")
        for d, r in days.items():
            if not (isinstance(d, str) and DATE_RE.match(d) and isinstance(r, dict)):
                continue
            vals = (num(r.get("cal")), num(r.get("pro")), num(r.get("steps")), num(r.get("wt")))
            if any(v is not None for v in vals):
                conn.execute("INSERT INTO daily_log VALUES (?,?,?,?,?)", (d,) + vals)
        for ws, r in targets.items():
            if not (isinstance(ws, str) and DATE_RE.match(ws) and isinstance(r, dict)):
                continue
            vals = (num(r.get("cal")), num(r.get("pro")), num(r.get("steps")))
            if any(v is not None for v in vals):
                conn.execute("INSERT INTO weekly_targets VALUES (?,?,?,?)", (ws,) + vals)
        for k, v in profile.items():
            if isinstance(k, str):
                conn.execute("INSERT INTO profile VALUES (?,?)", (k, json.dumps(v)))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif path == "/api/data":
            conn = connect()
            try:
                body = json.dumps(read_all(conn)).encode()
            finally:
                conn.close()
            self._send(200, body, "application/json")
        else:
            self._send(404, b"Not found", "text/plain")

    def do_PUT(self):
        if self.path.split("?", 1)[0] != "/api/data":
            return self._send(404, b"Not found", "text/plain")
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self._send(400, b"Bad size", "text/plain")
        try:
            data = json.loads(self.rfile.read(n))
            if not isinstance(data, dict):
                raise ValueError
        except ValueError:
            return self._send(400, b"Bad JSON", "text/plain")
        conn = connect()
        try:
            write_all(conn, data)
        finally:
            conn.close()
        self._send(200, b'{"ok":true}', "application/json")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    connect().close()
    print("Tracker running at http://127.0.0.1:%d" % port)
    print("Database file: " + DB_PATH)
    print("Press Ctrl+C to stop.")
    try:
        ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
