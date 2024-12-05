import asyncio
import logging
# import TCPOverICMP.tcp_over_icmp_tunnel as tcp_over_icmp_tunnel, tcp_server
from TCPOverICMP import tcp_server
from TCPOverICMP import tcp_over_icmp_tunnel
from TCPOverICMP.proto import ICMPTunnelPacket

log = logging.getLogger(__name__)


class ProxyClient(tcp_over_icmp_tunnel.TCPoverICMPTunnel):
    LOCALHOST = '127.0.0.1'

    def __init__(self, remote_endpoint, port, destination_host, destination_port):

        super(ProxyClient, self).__init__(ICMPTunnelPacket.Direction.PROXY_SERVER, remote_endpoint)
        log.info(f'proxy-server: {remote_endpoint}')
        log.info(f'forwarding to {destination_host}:{destination_port}')
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.incoming_tcp_connections = asyncio.Queue()
        self.tcp_server = tcp_server.Server(self.LOCALHOST, port, self.incoming_tcp_connections)
        #proxy client corutines to run 
        self.main_coroutines.append(self.tcp_server.server_loop())
        self.main_coroutines.append(self.wait_for_new_connection())

    async def wait_for_new_connection(self):
        """
        receive new connections from the server through incoming_tcp_connections queue.
        """
        while True:
            session_id, reader, writer = await self.incoming_tcp_connections.get()

            new_tunnel_packet = ICMPTunnelPacket(
                session_id=session_id,
                action=ICMPTunnelPacket.Action.START,
                direction=self.direction,
                destination_host=self.destination_host,
                port=self.destination_port,
            )
            # only add client if other endpoint acked.
            if await self.operations_handler.send_icmp_packet_wait_ack(new_tunnel_packet):
                self.client_manager.add_client(session_id, reader, writer)
            else:  # if the other endpoint didnt receive the START request, close the local client.
                writer.close()
                await writer.wait_closed()
