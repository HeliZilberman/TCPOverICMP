import asyncio
import logging
import argparse
# from TCPOverICMP import proxy
import TCPOverICMP.proxy_server as proxy_server

import debugpy
debugpy.listen(("0.0.0.0", 5678))  # Listen on all interfaces
print("Waiting for debugger to attach...")
debugpy.wait_for_client()  # Pause execution until debugger attaches

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('proxy_client_ip', help='IP address of the forwarder client')
    return parser.parse_args()


async def main():
    args = parse_args()
    await proxy_server.Proxy(args.proxy_client_ip).run()


def start_asyncio_main():
    asyncio.run(main())


if __name__ == '__main__':
    start_asyncio_main()
