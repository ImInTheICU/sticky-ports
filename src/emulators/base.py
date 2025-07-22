# emulators/base.py
import asyncio


class BaseEmulator:
    def __init__(self, bind_ip="0.0.0.0", bind_port=None, config=None):
        self.bind_ip = bind_ip
        self.bind_port = bind_port or self.port
        self.config = config or {}

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        raise NotImplementedError
