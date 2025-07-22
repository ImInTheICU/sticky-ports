# emulators/redis.py
import time
import random
import asyncio
import socket
import platform
from .base import BaseEmulator
from logger import queue

def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]

class RedisEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

        self.INFO_TEMPLATE = """# Server
redis_version:{version}
os:{os_name} {os_release} {arch}
arch_bits:{bits}
uptime_in_seconds:{uptime}"""

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0
        ver = random.choice(["6.0.10", "6.2.6", "7.0.5", "5.0.14"])
        osn, osr, arch = platform.system(), platform.release(), platform.machine()
        bits = "64" if platform.architecture()[0].startswith("64") else "32"

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            bnr = f"+OK {socket.getfqdn()} Redis {ver}\r\n".encode()
            transcript.append((time.time(), "server", bnr))
            await jitter()
            writer.write(bnr)
            await writer.drain()
            while True:
                data = await reader.readline()
                if not data:
                    break
                ts = time.time()
                transcript.append((ts, "client", data))
                cmd_count += 1
                await jitter()
                cmd = data.strip().split()[0].upper() if data.strip() else b""
                if cmd == b"PING":
                    resp = b"+PONG\r\n"
                elif cmd == b"ECHO" and len(data.split()) > 1:
                    arg = data.strip().split(b" ", 1)[1]
                    resp = b"$%d\r\n%s\r\n" % (len(arg), arg)
                elif cmd == b"INFO":
                    up = int(ts - start_ts)
                    info = self.INFO_TEMPLATE.format(
                        version=ver,
                        os_name=osn,
                        os_release=osr,
                        arch=arch,
                        bits=bits,
                        uptime=up,
                    ).encode()
                    resp = b"$%d\r\n%s\r\n" % (len(info), info)
                else:
                    nm = cmd.decode(errors="ignore")
                    resp = f"-ERR unknown command '{nm}'\r\n".encode()
                transcript.append((time.time(), "server", resp))
                writer.write(resp)
                await writer.drain()
        except (ConnectionResetError, OSError):
            pass
        finally:
            if cmd_count:
                payload = {
                    "service": "redis",
                    "ip": ip,
                    "port": self.bind_port,
                    "start_ts": start_ts,
                    "end_ts": time.time(),
                    "cmd_count": cmd_count,
                    "details": [
                        {
                            "ts": ts,
                            "direction": d,
                            "data": dta.decode("latin-1", errors="ignore"),
                        }
                        for ts, d, dta in transcript
                    ],
                }
                await queue.put(payload)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
