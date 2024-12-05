import asyncio
import logging
from TCPOverICMP import  proxy_server

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

async def main():
    await proxy_server.ProxyServer().run()

def run_async_loop():
    asyncio.run(main())

if __name__ == '__main__':
    run_async_loop()
