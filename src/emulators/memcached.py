# emulators/memcached.py
import time
import random
import asyncio
from .base import BaseEmulator
from src.logger import queue


def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]


class MemcachedEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

        self.VERSIONS = ["1.5.22", "1.6.9", "1.6.17", "1.6.21"]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0
        version = random.choice(self.VERSIONS)

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                now = time.time()
                transcript.append((now, "client", data))
                cmd_count += 1
                await jitter()
                parts = data.strip().split()
                cmd = parts[0].upper() if parts else b""
                if cmd == b"STATS":
                    lines = [
                        f"STAT pid {random.randint(1000,5000)}",
                        f"STAT uptime {int(now-start_ts)}",
                        f"STAT version {version}",
                        f"STAT curr_items {random.randint(0,10)}",
                        f"STAT total_connections {random.randint(1,50)}",
                    ]
                    resp = b"".join((l + "\r\n").encode() for l in lines) + b"END\r\n"
                elif cmd == b"VERSION":
                    resp = f"VERSION {version}\r\n".encode()
                else:
                    resp = b"ERROR\r\n"
                transcript.append((time.time(), "server", resp))
                writer.write(resp)
                await writer.drain()

        except (ConnectionResetError, OSError):
            pass
        finally:
            if cmd_count:
                payload = {
                    "service": "memcached",
                    "ip": ip,
                    "port": self.bind_port,
                    "start_ts": start_ts,
                    "end_ts": time.time(),
                    "cmd_count": cmd_count,
                    "details": [
                        {
                            "ts": ts,
                            "direction": d,
                            "data": data.decode("latin-1", errors="ignore").rstrip(),
                        }
                        for ts, d, data in transcript
                    ],
                }
                await queue.put(payload)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
