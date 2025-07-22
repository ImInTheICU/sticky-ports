# emulators/rdp.py
import asyncio
import time
import random
from .base import BaseEmulator
from src.logger import queue


class RDPEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

        self.PROTOCOL_BANNERS = [
            b"\x03\x00\x00\x13\x0e\xe0\x00\x00\x00\x00\x00\x01\x00\x08\x00\x03\x00\x00\x00",
            b"\x03\x00\x00\x0b\x06\xe0\x00\x00\x00\x00",
            b"\x03\x00\x00\x0d\x02\xf0\x80\x68\x00\x01\x03\x00\x00",
        ]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = writer.get_extra_info("peername")[0]
        start_ts = time.time()
        transcript = []
        cmd_count = 0

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            banner = random.choice(self.PROTOCOL_BANNERS)
            writer.write(banner)
            await writer.drain()
            transcript.append((time.time(), "server", banner))
            await jitter()

            while True:
                data = await reader.read(1024)
                if not data:
                    break
                transcript.append((time.time(), "client", data))
                cmd_count += 1
                await jitter()

        except (asyncio.IncompleteReadError, ConnectionResetError, OSError):
            pass
        finally:
            payload = {
                "service": "rdp",
                "ip": ip,
                "port": self.bind_port,
                "start_ts": start_ts,
                "end_ts": time.time(),
                "cmd_count": cmd_count,
                "details": [
                    {
                        "ts": ts,
                        "direction": d,
                        "data": data.decode("latin-1", errors="ignore"),
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
