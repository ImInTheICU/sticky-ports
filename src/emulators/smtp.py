# emulators/smtp.py
import time
import random
import asyncio
import socket
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from .base import BaseEmulator
from src.logger import queue


def _peer_ip(writer):
    return writer.get_extra_info("peername")[0]


TLS = SSLContext(PROTOCOL_TLS_SERVER)


class SMTPEmulator(BaseEmulator):
    def __init__(self, bind_ip=None, bind_port=None, config=None):
        super().__init__(bind_ip, bind_port, config)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        start_ts = time.time()
        transcript = []
        cmd_count = 0
        tls_started = False
        host = socket.getfqdn()
        version = random.choice(["Postfix (Ubuntu)", "Exim 4.94", "Sendmail 8.16"])

        async def jitter():
            await asyncio.sleep(random.uniform(0.05, 0.15))

        try:
            bnr = f"220 {host} ESMTP {version}\r\n".encode()
            transcript.append((time.time(), "server", bnr))
            writer.write(bnr)
            await writer.drain()
            while True:
                line = await reader.readline()
                if not line:
                    break
                ts = time.time()
                transcript.append((ts, "client", line))
                cmd_count += 1
                await jitter()
                cmd = line.decode(errors="ignore").strip().upper()
                if cmd.startswith("EHLO"):
                    resp = (
                        f"250-{host}\r\n250-PIPELINING\r\n250-SIZE 10485760\r\n"
                        f"250-8BITMIME\r\n250-AUTH LOGIN PLAIN\r\n250-STARTTLS\r\n250 HELP\r\n"
                    ).encode()
                elif cmd.startswith("HELO"):
                    resp = f"250 {host}\r\n".encode()
                elif cmd == "STARTTLS" and not tls_started:
                    resp = b"220 Ready to start TLS\r\n"
                elif cmd.startswith("MAIL FROM"):
                    resp = b"250 OK\r\n"
                elif cmd.startswith("RCPT TO"):
                    resp = b"250 Accepted\r\n"
                elif cmd == "DATA":
                    resp = b"354 End data with <CR><LF>.<CR><LF>\r\n"
                elif cmd == "QUIT":
                    resp = b"221 Bye\r\n"
                else:
                    resp = b"502 Command not implemented\r\n"
                transcript.append((time.time(), "server", resp))
                writer.write(resp)
                await writer.drain()
                if cmd == "STARTTLS" and not tls_started:
                    tr = writer.transport
                    pr = tr.get_protocol()
                    loop = asyncio.get_event_loop()
                    tls = await loop.start_tls(tr, pr, TLS, server_side=True)
                    reader.set_transport(tls)
                    writer.set_transport(tls)
                    tls_started = True
                if cmd == "DATA":
                    while True:
                        dl = await reader.readline()
                        ts2 = time.time()
                        transcript.append((ts2, "client", dl))
                        if dl == b".\r\n":
                            break
                    ack = b"250 Message accepted for delivery\r\n"
                    transcript.append((time.time(), "server", ack))
                    writer.write(ack)
                    await writer.drain()
                if cmd == "QUIT":
                    break
        except (ConnectionResetError, OSError):
            pass
        finally:
            if cmd_count:
                payload = {
                    "service": "smtp",
                    "ip": ip,
                    "port": self.bind_port,
                    "start_ts": start_ts,
                    "end_ts": time.time(),
                    "cmd_count": cmd_count,
                    "details": [
                        {
                            "ts": t,
                            "direction": d,
                            "data": b.decode("latin-1", errors="ignore").rstrip(),
                        }
                        for t, d, b in transcript
                    ],
                }
                await queue.put(payload)
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
