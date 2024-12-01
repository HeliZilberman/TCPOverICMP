import asyncio
import logging
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
        #proxy client corutines to run 
        self.coroutines_client.append(self.tcp_server.serve_forever())
        self.coroutines_client.append(self.wait_for_new_connection())

    @property
    def direction(self):
        return Packet.Direction.PROXY_SERVER

    async def handle_start_request(self, tunnel_packet: Packet):
        """
        only finctions in the proxy server endpoint
        """
        log.debug(f'invalid START command. ignoring...\n{tunnel_packet}')

    async def wait_for_new_connection(self):
        """
        receive new connections from the server through incoming_tcp_connections queue.
        """
        while True:
            session_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = Packet(
                session_id=session_id,
                operation=Packet.Operation.START,
                direction=self.direction,
                destination_host=self.destination_host,
                port=self.destination_port,
            )
            # only add client if other endpoint acked.
            if await self.send_icmp_packet_wait_ack(new_tunnel_packet):
                self.client_manager.add_client(session_id, reader, writer)
            else:  # if the other endpoint didnt receive the START request, close the local client.
                writer.close()
                await writer.wait_closed()
