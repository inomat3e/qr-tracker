# QR Tracker

A simple QR-code generator that creates a tracking link and shows whether/how many times people opened it.

## What it tracks
- Total scans
- Last scan time

It does NOT save IP addresses, names, device IDs, or other visitor information.

## Run it on your PC

1. Install Python 3.
2. Open a terminal in this folder.
3. Run:

```bash
pip install -r requirements.txt
python app.py
```

4. Open http://127.0.0.1:5000

Important: a QR code using `127.0.0.1`/localhost will only work on your own computer. To let other people scan it, deploy this app to a public host.

## Public deployment

Set the environment variable:

`BASE_URL=https://your-public-domain.example`

The app can run on most Python hosts that support Flask. Make sure the host uses persistent storage for `qr_tracker.db`, otherwise the scan database may reset when the app restarts/redeploys.

## How it works

QR -> /r/<random-id> -> count scan -> redirect to your destination

The stats page is:

`/stats/<random-id>`

Keep the stats URL private if you don't want other people to see the scan count.
