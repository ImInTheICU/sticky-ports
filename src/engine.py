# engine.py
import asyncio
import sys

from emulators.redis import RedisEmulator
from emulators.smtp import SMTPEmulator
from emulators.memcached import MemcachedEmulator
from emulators.ftp import FTPEmulator
from emulators.telnet import TelnetEmulator
from emulators.mysql import MySQLEmulator
from emulators.vnc import VNCEmulator
from emulators.rdp import RDPEmulator

from config import CONFIG
from logger import log_sink

async def main() -> None:
    asyncio.create_task(log_sink())

    servers = []

    emulator_classes = {
        "redis": RedisEmulator,
        "smtp": SMTPEmulator,
        "memcached": MemcachedEmulator,
        "ftp": FTPEmulator,
        "telnet": TelnetEmulator,
        "mysql": MySQLEmulator,
        "vnc": VNCEmulator,
        "rdp": RDPEmulator,
    }

    for name, emu_conf in CONFIG.get("emulators", {}).items():
        if not emu_conf.get("enabled", False):
            continue

        emu_cls = emulator_classes.get(name)
        if not emu_cls:
            continue

        emulator = emu_cls(
            bind_ip=emu_conf.get("bind_ip", "0.0.0.0"),
            bind_port=emu_conf.get("bind_port"),
            config=CONFIG,
        )

        try:
            server = await asyncio.start_server(
                emulator.handle, host=emulator.bind_ip, port=emulator.bind_port
            )
        except OSError as e:
            if e.errno == 98 or e.errno == 48:
                print(
                    f"[ERROR] Port {emulator.bind_port} already in use, cannot bind {name} emulator. \n\tYou can disable this emulator in the 'config.yaml' to prevent this message.",
                    file=sys.stderr,
                )
                continue
            else:
                raise

        print(
            f"[INFO] Emulator {name} listening on {emulator.bind_ip}:{emulator.bind_port}"
        )
        servers.append(server)

    await asyncio.gather(*(srv.serve_forever() for srv in servers))


if __name__ == "__main__":
    asyncio.run(main())
    