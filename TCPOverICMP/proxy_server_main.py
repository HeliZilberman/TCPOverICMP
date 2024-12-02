import asyncio
import logging
import  proxy_server

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

async def main():
    await proxy_server.ProxyServer().run()


def start_asyncio_main():
    asyncio.run(main())


if __name__ == '__main__':
    start_asyncio_main()
