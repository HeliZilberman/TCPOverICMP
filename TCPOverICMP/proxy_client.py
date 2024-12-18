"""
proxy_client.py

This module implements the ProxyClient class, which manages the client-side of the TCP-over-ICMP tunnel. 
It listens for incoming TCP connections on the localhost, sends connection requests to the Proxy TCPServer 
via ICMP, and handles the forwarding of TCP data over ICMP.

Key Components:
- `ProxyClient`: Inherits from `TCPoverICMPTunnel` and manages TCP connections.
- Listens on localhost for TCP connections.
- Sends a START packet to the Proxy TCPServer to initiate a tunnel session.
- Manages incoming TCP connections and forwards data using ICMP.

Main Methods:
- `wait_for_new_connection`: Waits for new TCP connections and sends a START request to the Proxy TCPServer.
- `start_session`: Logs ignored packets since START actions are only relevant for the Proxy TCPServer.
"""
import asyncio
import logging
from TCPOverICMP import tcp_server
from TCPOverICMP import tcp_over_icmp_tunnel
from TCPOverICMP.tunnel_packet import ICMPTunnelPacket, Action, Direction

log = logging.getLogger(__name__)


class ProxyClient(tcp_over_icmp_tunnel.TCPoverICMPTunnel):
    LOCALHOST = '127.0.0.1'

    def __init__(self, remote_endpoint, port, destination_host, destination_port):
        super(ProxyClient, self).__init__(Direction.PROXY_SERVER, remote_endpoint)
        log.info(f'proxy-server: {remote_endpoint}')
        log.info(f'transmiting to {destination_host}:{destination_port}')
        self.destination_host = destination_host
        self.destination_port = destination_port
        self.incoming_tcp_connections = asyncio.Queue()
        self.tcp_server = tcp_server.TCPServer(self.LOCALHOST, port, self.incoming_tcp_connections)
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
                action=Action.START,
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

    async def start_session(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        start action is only sent to the proxy server therfore the packet is ignored
        """
        log.info(f'ignore packet eith invalod command{icmp_tunnel_packet}')
