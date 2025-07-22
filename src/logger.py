# logger.py
import asyncio
import sqlite3
import json
import uuid
import aiohttp

from cachetools import TTLCache
from datetime import datetime, timezone

from src.config import CONFIG

queue = asyncio.Queue()

SERVICE_CAT_MAP = {
    "ssh": [22, 18],  # SSH abuse & brute-force
    "ftp": [5, 18],  # FTP brute-force & general brute-force
    "smtp": [11, 17],  # Email spam & spoofing
    "redis": [14, 19],  # Port scan & bad web bot
    "memcached": [4, 14],  # DDoS attack & port scan
    "mysql": [15, 16],  # Hacking & SQL injection attempts
    "telnet": [22, 18],  # SSH-style abuse & brute-force
    "vnc": [22, 23],  # SSH & IoT-targeted
    "rdp": [15, 18],  # Hacking + Brute-force
}

VERSION = CONFIG.get("version", "?")
SQLITE_CFG = CONFIG.get("logging", {}).get("sqlite", {})
ABUSE_CFG = CONFIG.get("logging", {}).get("abuseipdb", {})

if SQLITE_CFG.get("enabled", False):
    db_file = SQLITE_CFG.get("file_name", "logger.db")
    conn = sqlite3.connect(db_file, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        """
    CREATE TABLE IF NOT EXISTS logs (
        session_id   TEXT PRIMARY KEY,
        service      TEXT NOT NULL,
        ip           TEXT NOT NULL,
        port         INTEGER NOT NULL,
        start_ts     REAL NOT NULL,
        end_ts       REAL NOT NULL,
        cmd_count    INTEGER NOT NULL,
        details      JSON
    );
    """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_logs_ip      ON logs(ip)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_logs_service ON logs(service)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_logs_time    ON logs(start_ts)")
    conn.commit()

ABUSE_RECENTS = TTLCache(
    maxsize=ABUSE_CFG.get("ttl_size", 4500), ttl=ABUSE_CFG.get("ttl_time", 905) + 5
)
ABUSE_ENABLED = ABUSE_CFG.get("enabled", False)
ABUSE_API_KEY = ABUSE_CFG.get("api_key")
ABUSE_CATS = ABUSE_CFG.get("categories", [])
ABUSE_IDENTIFIER = ABUSE_CFG.get("identifier", "server")
REPORT_URL = "https://api.abuseipdb.com/api/v2/report"


async def report_to_abuseipdb(ip: str, categories: list, comment: str, timestamp: str):
    headers = {
        "Key": ABUSE_API_KEY,
        "Accept": "application/json",
        "User-Agent": f"StickyPorts/{VERSION} (L4 Honeypot; reporting abusive IPs)",
    }
    data = {
        "ip": ip,
        "categories": ",".join(str(c) for c in categories),
        "comment": comment,
        "timestamp": timestamp,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(REPORT_URL, data=data, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"[ERROR] Failed to report {ip}: {resp.status} {text}")


async def log_sink():
    while True:
        msg = await queue.get()
        if not isinstance(msg, dict):
            continue
        session_id = msg.get("session_id") or str(uuid.uuid4())
        service = msg["service"]
        ip = msg["ip"]
        port = msg["port"]
        start_ts = msg["start_ts"]
        end_ts = msg["end_ts"]
        cmd_count = msg["cmd_count"]
        details = msg.get("details")

        if SQLITE_CFG.get("enabled", False):
            try:
                details_json = json.dumps(details)
                c.execute(
                    """
                    INSERT OR REPLACE INTO logs
                    (session_id, service, ip, port, start_ts, end_ts, cmd_count, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        session_id,
                        service,
                        ip,
                        port,
                        start_ts,
                        end_ts,
                        cmd_count,
                        details_json,
                    ),
                )
                conn.commit()
            except Exception as e:
                print(f"[ERROR] SQLite error: {e}")

        if ABUSE_ENABLED and ABUSE_API_KEY and not ABUSE_RECENTS.get(ip):
            ABUSE_RECENTS[ip] = True

            cats = SERVICE_CAT_MAP.get(service, ABUSE_CATS)
            if not cats:
                cats = ABUSE_CATS

            if cmd_count <= 0 and 14 not in cats: # NOTE: If command count is below zero ( no commands executed ) we will flag for port scan.
                cats.append(14)

            comment = f"\nEmulator: {service} \nPort: {port} \nCommands: {cmd_count}\n\nCaught on {ABUSE_IDENTIFIER} using StickyPorts! \nhttps://github.com/ImInTheICU/sticky-ports"
            ts_str = datetime.fromtimestamp(start_ts, timezone.utc).isoformat()
            asyncio.create_task(report_to_abuseipdb(ip, cats, comment, ts_str))
