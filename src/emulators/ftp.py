# emulators/ftp.py
import time
import random
import asyncio
from .base import BaseEmulator
from logger import queue

def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]

class FTPEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

        self.BANNERS = [
            "220 (vsFTPd 3.0.3)",
            "220 ProFTPD 1.3.5 Server ready",
            "220 (Pure-FTPd 1.0.49)",
        ]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0
        logged_in = False
        banner = random.choice(self.BANNERS).encode() + b"\r\n"

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            transcript.append((time.time(), "server", banner))
            writer.write(banner)
            await writer.drain()

            while True:
                line = await reader.readline()
                if not line:
                    break
                now = time.time()
                transcript.append((now, "client", line))
                cmd_count += 1
                await jitter()

                cmd, *args = line.decode(errors="ignore").strip().split(" ", 1)
                cmd = cmd.upper()
                resp = b"502 Command not implemented.\r\n"
                if cmd == "USER":
                    resp = (
                        b"331 Password required for %s\r\n" % args[0].encode()
                        if args
                        else b"331 Password required\r\n"
                    )
                elif cmd == "PASS":
                    resp = b"230 User logged in, proceed.\r\n"
                    logged_in = True
                elif cmd == "SYST" and logged_in:
                    resp = b"215 UNIX Type: L8\r\n"
                elif cmd == "PWD" and logged_in:
                    resp = b'257 "/" is current directory\r\n'
                elif cmd == "TYPE" and logged_in and args:
                    resp = b"200 Type set to %s\r\n" % args[0].encode()
                elif cmd == "QUIT":
                    resp = b"221 Goodbye.\r\n"

                transcript.append((time.time(), "server", resp))
                writer.write(resp)
                await writer.drain()
                if cmd == "QUIT":
                    break

        except (ConnectionResetError, OSError):
            pass

        finally:
            if cmd_count:
                payload = {
                    "service": "ftp",
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
