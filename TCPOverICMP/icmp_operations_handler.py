import asyncio
import logging
from TCPOverICMP import client_manager, icmp_socket, icmp_packet


#from TCPOverICMP.proto import ICMPTunnelPacket
from TCPOverICMP.tunnel_packet import ICMPTunnelPacket, Action, Direction


log = logging.getLogger(__name__)

class ICMPOperationsHandler:
    ICMP_PACKET_IDENTIFIER = 0xbeef
    PACKET_SEQUENCE_MARKER = 0xdead
    RESPONSE_WAIT_TIME = 1.0 #my computer is slow - time to wait for ack 

    def __init__(self,client_manager: client_manager.ClientManager,
                 icmp_socket:icmp_socket.ICMPSocket,
                 remote_endpoint: dict,
                 direction,
                 timed_out_tcp_connections
                 ):
        self.client_manager = client_manager
        self.icmp_socket = icmp_socket
        self.remote_endpoint = remote_endpoint
        self.direction = direction
        self.timed_out_tcp_connections = timed_out_tcp_connections
        self.packets_waiting_ack = {}
        # self.operations = {
        #     ICMPTunnelPacket.Action.TERMINATE: self.terminate_session,
        #     ICMPTunnelPacket.Action.DATA_TRANSFER: self.handle_data,
        #     ICMPTunnelPacket.Action.ACK: self.handle_ack,
        # }
        # if self.direction == ICMPTunnelPacket.Direction.PROXY_CLIENT:
        #     self.operations[ICMPTunnelPacket.Action.START] = self.start_session

        self.operations = {
            Action.TERMINATE: self.terminate_session,
            Action.DATA_TRANSFER: self.handle_data,
            Action.ACK: self.handle_ack,
        }
        if self.direction == Direction.PROXY_CLIENT:
            self.operations[Action.START] = self.start_session
        
    async def execute_operation(self, icmp_tunnel_packet: ICMPTunnelPacket):
        await self.operations[icmp_tunnel_packet.action](icmp_tunnel_packet)


    async def start_session(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        operates a start action, 
        """
        try:
            reader, writer = await asyncio.open_connection(icmp_tunnel_packet.destination_host, icmp_tunnel_packet.port)
        except ConnectionRefusedError:
            log.debug(f'connection.connect not started: {icmp_tunnel_packet.destination_host}:{icmp_tunnel_packet.port} refused connection.')
            return

        self.client_manager.add_client(
            session_id=icmp_tunnel_packet.session_id,
            reader=reader,
            writer=writer,
        )
        self.send_ack(icmp_tunnel_packet)
    async def terminate_session(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        operates the TERMINATE action. removes the client and send ack for terminate.
        """
        await self.client_manager.remove_client(icmp_tunnel_packet.session_id)
        self.send_ack(icmp_tunnel_packet)
    
    async def handle_data(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        operate  data action. fowards to client and sends ack 
        @param icmp_tunnel_packet: used to foward to client the data
        """
        await self.client_manager.write_to_client(
            icmp_tunnel_packet.session_id,
            icmp_tunnel_packet.seq,
            icmp_tunnel_packet.payload
        )
        self.send_ack(icmp_tunnel_packet)


    async def handle_ack(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        operate an ACK action.
        the packet is recognized by the session_id and the sequence of packet 
        @param tunnel packet 
        """
        packet_id = (icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq)
        if packet_id in self.packets_waiting_ack:
            self.packets_waiting_ack[packet_id].set()

    def send_ack(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """
        Send an ACK for a packet using EchoReply.
        used by proxy-server
        """
        # ack_tunnel_packet = ICMPTunnelPacket(
        #     session_id=icmp_tunnel_packet.session_id,
        #     seq=icmp_tunnel_packet.seq,
        #     action=ICMPTunnelPacket.Action.ACK,
        #     direction=self.direction,
        # )
        # self.send_icmp_packet(
        #     icmp_packet.ICMPType.EchoReply,
        #     ack_tunnel_packet.SerializeToString(),
        # )
        ack_tunnel_packet = ICMPTunnelPacket(
            session_id=icmp_tunnel_packet.session_id,
            seq=icmp_tunnel_packet.seq,
            action=Action.ACK,
            direction=self.direction,
        )
        self.send_icmp_packet(
            icmp_packet.ICMPType.EchoReply,
            ack_tunnel_packet.serialize(),
        )
    def send_icmp_packet(
            self,
            packet_type: int,
            payload: bytes
    ):
        """
        Build and send an ICMP packet on the ICMP socket.
        @param packet_type echo reply or request
        @param payload the icmp_tunnel_packet serlized 
        """
        new_icmp_packet = icmp_packet.ICMPPacket(
            packet_type=packet_type,
            identifier=self.ICMP_PACKET_IDENTIFIER,
            sequence_number=self.PACKET_SEQUENCE_MARKER,
            payload=payload
        )
        self.icmp_socket.sendto(new_icmp_packet, self.remote_endpoint["ip"])

    async def send_icmp_packet_wait_ack(self, icmp_tunnel_packet: ICMPTunnelPacket):
            """
            Send an ICMP packet and ensure it is acknowledged. Retry up to 3 times if necessary.
            @param icmp_tunnel_packet the packet sent it the icmp socket
            """
            self.packets_waiting_ack[(icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq)] = asyncio.Event()

            for _ in range(3):
                # self.send_icmp_packet(
                #     icmp_packet.ICMPType.EchoRequest,
                #     icmp_tunnel_packet.SerializeToString(),
                # )
                self.send_icmp_packet(
                    icmp_packet.ICMPType.EchoRequest,
                    icmp_tunnel_packet.serialize(),
                )
                try:
                    await asyncio.wait_for(
                        self.packets_waiting_ack[(icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq)].wait(),
                        self.RESPONSE_WAIT_TIME
                    )
                    self.packets_waiting_ack.pop((icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq))
                    return True
                except asyncio.TimeoutError:
                    log.debug(f'failed recive or send ,resending:\n{icmp_tunnel_packet}')
                # await asyncio.sleep(1)
            log.info(f'packet failed to send:\n{icmp_tunnel_packet}\nRemoving client.')
            await self.timed_out_tcp_connections.put(icmp_tunnel_packet.session_id)
