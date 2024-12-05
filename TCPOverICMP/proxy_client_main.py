import asyncio
import logging
import argparse
from TCPOverICMP import proxy_client


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('proxy_ip', help='IP address of the proxy server')
    parser.add_argument('listening_port', type=int, help='Port on which the ProxyClient will listen')
    parser.add_argument('destination_ip', help='IP address to transmit to')
    parser.add_argument('destination_port', type=int, help='port to transmit to')
    return parser.parse_args()


async def main():
    args = parse_args()
    await proxy_client.ProxyClient(args.proxy_ip, args.listening_port, args.destination_ip, args.destination_port).run()


def run_async_loop():
    asyncio.run(main())


if __name__ == '__main__':
    run_async_loop()
