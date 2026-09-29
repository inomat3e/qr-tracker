import os, io, secrets
from functools import wraps
from flask import Flask, request, redirect, render_template_string, abort, send_file, session
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row
    def connect():
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    def init_db():
        with connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id TEXT PRIMARY KEY,
                    destination TEXT NOT NULL,
                    scans INTEGER NOT NULL DEFAULT 0,
                    last_scan TIMESTAMP
                )
            """)
else:
    import sqlite3
    DB = "qr_tracker.db"
    def connect():
        con = sqlite3.connect(DB)
        con.row_factory = sqlite3.Row
        return con
    def init_db():
        with connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id TEXT PRIMARY KEY,
                    destination TEXT NOT NULL,
                    scans INTEGER NOT NULL DEFAULT 0,
                    last_scan TEXT
                )
            """)

init_db()

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapped

def base_url():
    return os.environ.get("BASE_URL", request.host_url.rstrip("/"))

def tracked_url(link_id):
    return f"{base_url()}/r/{link_id}"

LOGIN = """
<!doctype html><title>QR Tracker Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial;max-width:420px;margin:80px auto;padding:20px;background:#f6f7f9}
.card{background:white;padding:25px;border-radius:16px;box-shadow:0 3px 18px #0001}
input{width:100%;box-sizing:border-box;padding:13px;margin:8px 0 15px;border:1px solid #ccc;border-radius:9px}
button{padding:12px 18px;border:0;border-radius:9px;background:#111;color:white;width:100%}
.err{color:#c00}
</style>
<div class="card">
<h1>🔒 QR Tracker</h1>
<p>Admin login</p>
{% if error %}<p class="err">Incorrect password.</p>{% endif %}
<form method="post">
<input type="password" name="password" placeholder="Password" autofocus required>
<button>Log in</button>
</form>
</div>
"""

HOME = """
<!doctype html><title>QR Tracker</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial,sans-serif;max-width:900px;margin:35px auto;padding:0 18px;background:#f6f7f9}
.card{background:#fff;padding:22px;border-radius:16px;box-shadow:0 3px 18px #0001;margin-bottom:18px}
input{width:100%;box-sizing:border-box;padding:13px;margin:7px 0 12px;border:1px solid #ccc;border-radius:9px}
button,.btn{display:inline-block;padding:11px 16px;border:0;border-radius:9px;background:#111;color:#fff;text-decoration:none;cursor:pointer}
.logout{float:right;background:#777}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:12px;border-bottom:1px solid #eee}
.url{word-break:break-all}.muted{color:#666;font-size:14px}
</style>
<div class="card">
<a class="btn logout" href="/logout">Log out</a>
<h1>QR Tracker</h1>
<p class="muted">Private QR dashboard.</p>
<form method="post" action="/create">
<label>Destination URL</label>
<input name="destination" placeholder="https://example.com" required>
<button>Create QR Code</button>
</form>
</div>
<div class="card">
<h2>Your QR Codes</h2>
{% if rows %}
<table><tr><th>Destination</th><th>Scans</th><th>Last scan</th><th></th></tr>
{% for r in rows %}
<tr><td class="url">{{ r.destination }}</td><td>{{ r.scans }}</td><td>{{ r.last_scan or "—" }}</td>
<td><a class="btn" href="/qr/{{ r.id }}">View QR</a></td></tr>
{% endfor %}
</table>
{% else %}<p>No QR codes yet.</p>{% endif %}
</div>
"""

RESULT = """
<!doctype html><title>QR Created</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial;max-width:700px;margin:40px auto;padding:0 18px;text-align:center}
img{max-width:360px;width:90%;border:1px solid #ddd;border-radius:12px}
.box{background:#f5f5f5;padding:15px;border-radius:10px;word-break:break-all}
</style>
<h1>QR Code Created 🎉</h1><img src="/qr/{{ id }}" alt="QR code">
<p><b>Tracking link:</b></p><div class="box">{{ tracked }}</div>
<p><a href="/stats/{{ id }}">View scan stats</a> · <a href="/">Dashboard</a></p>
"""

STATS = """
<!doctype html><title>QR Stats</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial;max-width:700px;margin:40px auto;padding:0 18px}
.card{background:#f5f5f5;padding:20px;border-radius:14px;margin:12px 0}
.big{font-size:54px;font-weight:bold}.url{word-break:break-all}
</style>
<h1>QR Scan Stats</h1>
<div class="card"><div class="big">{{ scans }}</div><div>Total scans</div></div>
<div class="card"><b>Last scan:</b><br>{{ last_scan or "Nobody has scanned it yet." }}</div>
<div class="card"><b>Destination:</b><br><span class="url">{{ destination }}</span></div>
<p><a href="/qr/{{ id }}">View QR</a> · <a href="/">Dashboard</a></p>
"""

@app.get("/login")
def login_get():
    if not ADMIN_PASSWORD:
        return "ADMIN_PASSWORD is not configured on the server.", 500
    return render_template_string(LOGIN, error=False)

@app.post("/login")
def login_post():
    if not ADMIN_PASSWORD:
        return "ADMIN_PASSWORD is not configured on the server.", 500
    if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
        session["admin"] = True
        return redirect("/")
    return render_template_string(LOGIN, error=True), 401

@app.get("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.get("/")
@admin_required
def home():
    with connect() as con:
        rows = con.execute("SELECT * FROM links ORDER BY id DESC").fetchall()
    return render_template_string(HOME, rows=rows)

@app.post("/create")
@admin_required
def create():
    destination = request.form.get("destination", "").strip()
    if not (destination.startswith("http://") or destination.startswith("https://")):
        return "Please enter a full http:// or https:// URL.", 400
    link_id = secrets.token_urlsafe(8)
    sql = "INSERT INTO links(id,destination) VALUES(%s,%s)" if DATABASE_URL else "INSERT INTO links(id,destination) VALUES(?,?)"
    with connect() as con:
        con.execute(sql, (link_id, destination))
    return render_template_string(RESULT, id=link_id, tracked=tracked_url(link_id))

# QR images and redirect URLs stay public so scanners never need to log in.
@app.get("/qr/<link_id>")
def qr(link_id):
    sql = "SELECT id FROM links WHERE id=%s" if DATABASE_URL else "SELECT id FROM links WHERE id=?"
    with connect() as con:
        row = con.execute(sql, (link_id,)).fetchone()
    if not row: abort(404)
    img = qrcode.make(tracked_url(link_id))
    out = io.BytesIO(); img.save(out, format="PNG"); out.seek(0)
    return send_file(out, mimetype="image/png", download_name=f"qr-{link_id}.png")

@app.get("/r/<link_id>")
def track(link_id):
    sel = "SELECT destination FROM links WHERE id=%s" if DATABASE_URL else "SELECT destination FROM links WHERE id=?"
    upd = "UPDATE links SET scans=scans+1,last_scan=NOW() WHERE id=%s" if DATABASE_URL else "UPDATE links SET scans=scans+1,last_scan=datetime('now') WHERE id=?"
    with connect() as con:
        row = con.execute(sel, (link_id,)).fetchone()
        if not row: abort(404)
        con.execute(upd, (link_id,))
    return redirect(row["destination"], code=302)

@app.get("/stats/<link_id>")
@admin_required
def stats(link_id):
    sel = "SELECT * FROM links WHERE id=%s" if DATABASE_URL else "SELECT * FROM links WHERE id=?"
    with connect() as con:
        row = con.execute(sel, (link_id,)).fetchone()
    if not row: abort(404)
    return render_template_string(STATS, id=link_id, scans=row["scans"],
                                  last_scan=row["last_scan"], destination=row["destination"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
