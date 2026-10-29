"""Launch uvicorn on a DUAL-STACK socket so both IPv4 (127.0.0.1) and IPv6 (::1)
work. On Windows a plain `--host ::` is IPv6-only and `--host 0.0.0.0` is IPv4-only,
which breaks whichever one the browser happens to resolve `localhost` to. Binding an
AF_INET6 socket with IPV6_V6ONLY=0 accepts both."""
import os
import socket
import asyncio
import uvicorn
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.environ.get("PORT", "8000"))


def make_dual_stack_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)  # accept IPv4 too
    except (AttributeError, OSError):
        pass
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("::", port))
    sock.listen()
    sock.set_inheritable(True)
    return sock


if __name__ == "__main__":
    sock = make_dual_stack_socket(PORT)
    config = uvicorn.Config("app.main:app", log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve(sockets=[sock]))
