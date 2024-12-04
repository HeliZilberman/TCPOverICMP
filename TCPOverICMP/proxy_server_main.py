import asyncio
import logging
import  proxy_server

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

async def main():
    await proxy_server.ProxyServer().run()


if __name__ == '__main__':
    asyncio.run(main())
