import asyncio
import logging


# from TCPOverICMP import tunnel_endpoint, tcp_server
# from TCPOverICMP.proto import Packet
import tunnel_endpoint, tcp_server
from proto import Packet

log = logging.getLogger(__name__)


class ProxyClient(tunnel_endpoint.TunnelEndpoint):
    LOCALHOST = '127.0.0.1'

    def __init__(self, other_endpoint, port, destination_host, destination_port):
        super(ProxyClient, self).__init__(other_endpoint)
        log.info(f'forwarding to {destination_host}:{destination_port}')
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.incoming_tcp_connections = asyncio.Queue()
        self.tcp_server = tcp_server.Server(self.LOCALHOST, port, self.incoming_tcp_connections)
        self.coroutines_to_run.append(self.tcp_server.serve_forever())
        self.coroutines_to_run.append(self.wait_for_new_connection())

    @property
    def direction(self):
        return Packet.Direction.PROXY_SERVER

    async def handle_start_request(self, tunnel_packet: Packet):
        """
        not the right endpoint for this operation. therefore ignore this packet.
        """
        log.debug(f'invalid START command. ignoring...\n{tunnel_packet}')

    async def wait_for_new_connection(self):
        """
        receive new connections from the server through incoming_tcp_connections queue.
        """
        while True:
            client_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = Packet(
                client_id=client_id,
                operation=Packet.Operation.START,
                direction=self.direction,
                ip=self.destination_host,
                port=self.destination_port,
            )
            # only add client if other endpoint acked.
            if await self.send_icmp_packet_blocking(new_tunnel_packet):
                self.client_manager.add_client(client_id, reader, writer)
            else:  # if the other endpoint didnt receive the START request, close the local client.
                writer.close()
                await writer.wait_closed()
