# emulators/vnc.py
import time
import random
import asyncio
import struct
from .base import BaseEmulator
from logger import queue

def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]

class VNCEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

        self.PROTO_VERSIONS = [
            b"RFB 003.003\n",
            b"RFB 003.007\n",
            b"RFB 003.008\n",
        ]

        self.SERVER_NAMES = [
            b"TightVNC",
            b"RealVNC",
            b"UltraVNC",
            b"Vino VNC",
            b"x11vnc",
            b"LibVNCServer",
            b"Turbovnc",
        ]

        self.RESOLUTIONS = [(800, 600), (1024, 768), (1280, 1024), (1920, 1080)]

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0

        proto = random.choice(self.PROTO_VERSIONS)
        width, height = random.choice(self.RESOLUTIONS)
        name = random.choice(self.SERVER_NAMES)
        sec_types = b"\x01\x01"

        server_init = (
            struct.pack(">HH", width, height)
            + b"\x20\x18"
            + b"\x00"
            + b"\x01"
            + struct.pack(">HHHHHH", 255, 255, 0, 255, 0, 255)
            + b"\x00\x00\x00"
            + struct.pack(">I", len(name))
            + name
        )

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            transcript.append((time.time(), "server", proto))
            writer.write(proto)
            await writer.drain()
            await jitter()

            client_proto = await reader.readexactly(len(proto))
            transcript.append((time.time(), "client", client_proto))
            cmd_count += 1
            await jitter()

            transcript.append((time.time(), "server", sec_types))
            writer.write(sec_types)
            await writer.drain()
            await jitter()

            choice = await reader.readexactly(1)
            transcript.append((time.time(), "client", choice))
            cmd_count += 1
            await jitter()
            sec_res = b"\x00\x00\x00\x00"
            transcript.append((time.time(), "server", sec_res))
            writer.write(sec_res)
            await writer.drain()
            await jitter()

            transcript.append((time.time(), "server", server_init))
            writer.write(server_init)
            await writer.drain()
            await jitter()

            while True:
                data = await reader.read(1024)
                if not data:
                    break
                transcript.append((time.time(), "client", data))
                cmd_count += 1

        except (asyncio.IncompleteReadError, ConnectionResetError, OSError):
            pass

        finally:
            if cmd_count:
                payload = {
                    "service": "vnc",
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
