import asyncio
import logging
# from TCPOverICMP import tunnel_endpoint
from TCPOverICMP.proto import ICMPTunnelPacket
# import TCPOverICMP.tcp_over_icmp_tunnel as tcp_over_icmp_tunnel
from TCPOverICMP import tcp_over_icmp_tunnel
# from proto import ICMPTunnelPacket

log = logging.getLogger(__name__)


class ProxyServer(tcp_over_icmp_tunnel.TCPoverICMPTunnel):
    
    def __init__(self):
        super(ProxyServer, self).__init__(ICMPTunnelPacket.Direction.PROXY_CLIENT)

    # async def start_session(self, icmp_tunnel_packet: ICMPTunnelPacket):
    #     """
    #     operates a start action, 
    #     """
    #     try:
    #         reader, writer = await asyncio.open_connection(icmp_tunnel_packet.destination_host, icmp_tunnel_packet.port)
    #     except ConnectionRefusedError:
    #         log.debug(f'connection.connect not started: {icmp_tunnel_packet.destination_host}:{icmp_tunnel_packet.port} refused connection.')
    #         return

    #     self.client_manager.add_client(
    #         session_id=icmp_tunnel_packet.session_id,
    #         reader=reader,
    #         writer=writer,
    #     )
    #     self.send_ack(icmp_tunnel_packet)
