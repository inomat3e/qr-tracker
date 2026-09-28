from flask import Flask, request, redirect, render_template_string, abort, send_file
import sqlite3, secrets, io, os
import qrcode

app = Flask(__name__)
DB = os.environ.get("QR_DB", "qr_tracker.db")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id TEXT PRIMARY KEY,
            destination TEXT NOT NULL,
            scans INTEGER NOT NULL DEFAULT 0,
            last_scan TEXT
        )
    """)
    con.commit()
    con.close()

init_db()

HOME = """
<!doctype html>
<title>QR Tracker</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 18px;background:#f6f7f9}
.card{background:white;padding:24px;border-radius:16px;box-shadow:0 4px 20px #0001;margin-bottom:18px}
input{width:100%;box-sizing:border-box;padding:13px;margin:7px 0 12px;border:1px solid #ccc;border-radius:9px}
button{padding:12px 18px;border:0;border-radius:9px;background:#111;color:white;cursor:pointer}
.small{color:#666;font-size:14px}.url{word-break:break-all}
</style>
<div class="card">
<h1>QR Code Generator + Visit Counter</h1>
<p class="small">Create a QR code that counts how many times its tracking link is opened.</p>
<form method="post" action="/create">
<label>Destination URL</label>
<input name="destination" placeholder="https://example.com" required>
<button>Create QR Code</button>
</form>
</div>
"""

RESULT = """
<!doctype html>
<title>Your QR Code</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial,sans-serif;max-width:700px;margin:40px auto;padding:0 18px;text-align:center}
img{max-width:360px;width:90%;border:1px solid #ddd;border-radius:12px}
.box{background:#f5f5f5;padding:15px;border-radius:10px;word-break:break-all}
a{color:#06c}
</style>
<h1>Your QR Code</h1>
<img src="/qr/{{ id }}" alt="QR code">
<p><b>Tracked link:</b></p>
<div class="box">{{ tracked }}</div>
<p><a href="/stats/{{ id }}">View scan stats</a></p>
<p><a href="/">Create another</a></p>
"""

STATS = """
<!doctype html>
<title>QR Stats</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial,sans-serif;max-width:700px;margin:40px auto;padding:0 18px}
.card{background:#f5f5f5;padding:20px;border-radius:14px;margin:12px 0}
.big{font-size:54px;font-weight:bold}
.url{word-break:break-all}
</style>
<h1>QR Scan Stats</h1>
<div class="card"><div class="big">{{ scans }}</div><div>Total scans</div></div>
<div class="card"><b>Last scan:</b><br>{{ last_scan or "Nobody has scanned it yet." }}</div>
<div class="card"><b>Destination:</b><br><span class="url">{{ destination }}</span></div>
<p><a href="/">Create another QR</a></p>
"""

@app.get("/")
def home():
    return HOME

@app.post("/create")
def create():
    destination = request.form.get("destination", "").strip()
    if not (destination.startswith("http://") or destination.startswith("https://")):
        return "Please enter a full http:// or https:// URL.", 400

    link_id = secrets.token_urlsafe(8)
    con = db()
    con.execute("INSERT INTO links(id,destination) VALUES(?,?)", (link_id, destination))
    con.commit()
    con.close()

    tracked = f"{BASE_URL}/r/{link_id}" if BASE_URL else f"{request.host_url.rstrip('/')}/r/{link_id}"
    return render_template_string(RESULT, id=link_id, tracked=tracked)

@app.get("/qr/<link_id>")
def qr(link_id):
    con = db()
    row = con.execute("SELECT id FROM links WHERE id=?", (link_id,)).fetchone()
    con.close()
    if not row:
        abort(404)

    tracked = f"{BASE_URL}/r/{link_id}" if BASE_URL else f"{request.host_url.rstrip('/')}/r/{link_id}"
    img = qrcode.make(tracked)
    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return send_file(out, mimetype="image/png")

@app.get("/r/<link_id>")
def track(link_id):
    con = db()
    row = con.execute("SELECT destination FROM links WHERE id=?", (link_id,)).fetchone()
    if not row:
        con.close()
        abort(404)

    # Only store a count and timestamp; no IP/device information is saved.
    con.execute("""
        UPDATE links
        SET scans=scans+1, last_scan=datetime('now')
        WHERE id=?
    """, (link_id,))
    con.commit()
    con.close()
    return redirect(row["destination"], code=302)

@app.get("/stats/<link_id>")
def stats(link_id):
    con = db()
    row = con.execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone()
    con.close()
    if not row:
        abort(404)
    return render_template_string(
        STATS,
        scans=row["scans"],
        last_scan=row["last_scan"],
        destination=row["destination"]
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
