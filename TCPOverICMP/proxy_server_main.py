import asyncio
import logging
import argparse
import  proxy_server

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('proxy_client_ip', help='IP address of the ProxyClient client')
    return parser.parse_args()


async def main():
    args = parse_args()
    # await proxy_server.ProxyServer(args.proxy_client_ip).run()
    await proxy_server.ProxyServer().run()


def start_asyncio_main():
    asyncio.run(main())


if __name__ == '__main__':
    start_asyncio_main()
