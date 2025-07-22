# emulators/telnet.py
import time
import random
import asyncio
from .base import BaseEmulator
from logger import queue

def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]

class TelnetEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

        self.LOGIN_BANNERS = [
            b"Ubuntu 20.04 LTS tty1",
            b"Debian GNU/Linux 10 ttyS0",
            b"CentOS Linux 7 (Core) ttyS1",
        ]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0

        banner = random.choice(self.LOGIN_BANNERS) + b"\r\n"
        prompt_user = b"login: "
        prompt_pass = b"Password: "
        fail_msg = b"Login incorrect\r\n"

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            for chunk in (banner, prompt_user):
                transcript.append((time.time(), "server", chunk))
                writer.write(chunk)
                await writer.drain()
                await jitter()

            user = await reader.readline()
            if not user:
                return
            transcript.append((time.time(), "client", user))
            cmd_count += 1
            await jitter()

            transcript.append((time.time(), "server", prompt_pass))
            writer.write(prompt_pass)
            await writer.drain()
            await jitter()

            pwd = await reader.readline()
            if not pwd:
                return
            transcript.append((time.time(), "client", pwd))
            cmd_count += 1
            await jitter()

            transcript.append((time.time(), "server", fail_msg))
            writer.write(fail_msg)
            await writer.drain()

        except (ConnectionResetError, OSError):
            pass

        finally:
            if cmd_count:
                payload = {
                    "service": "telnet",
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
