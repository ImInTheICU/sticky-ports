# emulators/mysql.py
import time
import random
import asyncio
import struct
from .base import BaseEmulator
from src.logger import queue


def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]


def build_handshake(ver, cid):
    p = bytearray()
    p.append(0x0A)
    p.extend(ver.encode() + b"\x00")
    p.extend(struct.pack("<I", cid))
    p.extend(b"abcdefgh")
    p.append(0)
    p.extend(struct.pack("<H", 2))
    p.append(0x21)
    p.extend(struct.pack("<H", 2))
    p.extend(struct.pack("<H", 0))
    p.append(0)
    p.extend(b"\x00" * 10)
    p.extend(b"ijklmnopqrstuvwx")
    hdr = struct.pack("<I", len(p))[:3] + b"\x00"
    return hdr + p


def make_error(msg):
    payload = b"\xff" + struct.pack("<H", 1045) + b"#28000" + msg.encode()
    hdr = struct.pack("<I", len(payload))[:3] + b"\x02"
    return hdr + payload


class MySQLEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0
        ver = random.choice(["5.7.38", "8.0.29", "10.3.34-MariaDB"])
        cid = random.randint(1000, 9999)
        hs = build_handshake(ver, cid)

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            transcript.append((time.time(), "server", hs))
            await jitter()
            writer.write(hs)
            await writer.drain()
            data = await reader.read(4096)
            if data:
                ts = time.time()
                transcript.append((ts, "client", data))
                cmd_count += 1
                err = make_error(
                    "Access denied for user ''@'%' (using password: YES)"
                )  # TODO: Should return the username and host correctly to avoid detection.
                transcript.append((time.time(), "server", err))
                await jitter()
                writer.write(err)
                await writer.drain()
        except (ConnectionResetError, OSError):
            pass
        finally:
            if cmd_count:
                payload = {
                    "service": "mysql",
                    "ip": ip,
                    "port": self.bind_port,
                    "start_ts": start_ts,
                    "end_ts": time.time(),
                    "cmd_count": cmd_count,
                    "details": [
                        {"ts": ts, "direction": d, "data": data.hex()}
                        for ts, d, data in transcript
                    ],
                }
                await queue.put(payload)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
