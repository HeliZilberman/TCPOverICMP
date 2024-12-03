import asyncio
import logging
# from TCPOverICMP import tunnel_endpoint
# from TCPOverICMP.proto import Packet
# import TCPOverICMP.tcp_over_icmp_tunnel as tcp_over_icmp_tunnel
import tcp_over_icmp_tunnel
from proto import Packet

log = logging.getLogger(__name__)


class ProxyServer(tcp_over_icmp_tunnel.TunnelEndpoint):
    @property
    def direction(self):
        return Packet.Direction.PROXY_CLIENT

    async def operate_start_operation(self, tunnel_packet: Packet):
        try:
            reader, writer = await asyncio.open_connection(tunnel_packet.destination_host, tunnel_packet.port)
        except ConnectionRefusedError:
            log.debug(f'{tunnel_packet.destination_host}:{tunnel_packet.port} refused connection. tunnel not started.')
            return

        self.client_manager.add_client(
            session_id=tunnel_packet.session_id,
            reader=reader,
            writer=writer,
        )
        self.send_ack(tunnel_packet)
