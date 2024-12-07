import asyncio
import logging
from TCPOverICMP.tunnel_packet import ICMPTunnelPacket,Action,Direction
import socket

from TCPOverICMP import tcp_over_icmp_tunnel


log = logging.getLogger(__name__)


class ProxyServer(tcp_over_icmp_tunnel.TCPoverICMPTunnel):
    
    def __init__(self):
        # super(ProxyServer, self).__init__(ICMPTunnelPacket.Direction.PROXY_CLIENT)
        super(ProxyServer, self).__init__(Direction.PROXY_CLIENT)
    async def open_tcp_connection(self,destination_host, port, mss=1400):
        """
        used to start a tcp connection bu proxy server when sent a start request
        @param destination_hst: ip adress of destination 
        @param: port port of destination 
        returns a reader write
        """
        try:
            reader, writer = await asyncio.open_connection(destination_host, port)
        except ConnectionRefusedError:
            log.debug(f'connection.connect not started: {destination_host}:{port} refused connection.')
            return
    
        # Get the underlying socket
        socket_obj = writer.get_extra_info('socket')
        if socket_obj:
            # Set the TCP MSS (Maximum Segment Size)
            socket_obj.setsockopt(socket.IPPROTO_TCP, socket.TCP_MAXSEG, mss)
        log.debug(f"Set TCP MSS to {mss} bytes")
    
        return reader, writer
    async def start_session(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        operates a start action, 
        """
        reader,writer = await self.open_tcp_connection(icmp_tunnel_packet.destination_host, icmp_tunnel_packet.port)
        self.client_manager.add_client(
            session_id=icmp_tunnel_packet.session_id,
            reader=reader,
            writer=writer,
        )
        self.send_ack(icmp_tunnel_packet)