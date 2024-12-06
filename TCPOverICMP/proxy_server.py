import asyncio
import logging
# from TCPOverICMP.proto import ICMPTunnelPacket
from TCPOverICMP.tunnel_packet import Direction


from TCPOverICMP import tcp_over_icmp_tunnel


log = logging.getLogger(__name__)


class ProxyServer(tcp_over_icmp_tunnel.TCPoverICMPTunnel):
    
    def __init__(self):
        # super(ProxyServer, self).__init__(ICMPTunnelPacket.Direction.PROXY_CLIENT)
        super(ProxyServer, self).__init__(Direction.PROXY_CLIENT)

