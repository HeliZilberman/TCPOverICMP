import asyncio
import logging
import client_manager, icmp_socket, icmp_packet
from proto import Packet

log = logging.getLogger(__name__)

class ICMPOperationsHandler:
    ICMP_PACKET_IDENTIFIER = 0xbeef
    PACKET_SEQUENCE_MARKER = 0xdead
    RESPONSE_WAIT_TIME = 1.0 #my computer is slow - time to wait for ack 

    def __init__(self,client_manager: client_manager.ClientManager,
                 icmp_socket:icmp_socket.ICMPSocket,
                 remote_endpoint: dict,
                 direction: Packet.Direction,
                 timed_out_tcp_connections
                 ):
        self.client_manager = client_manager
        self.icmp_socket = icmp_socket
        self.remote_endpoint = remote_endpoint
        self.direction = direction
        self.timed_out_tcp_connections = timed_out_tcp_connections
        self.packets_waiting_ack = {}
        self.operations = {
            #Packet.Operation.START: self.start_session,
            Packet.Operation.TERMINATE: self.terminate_session,
            Packet.Operation.DATA_TRANSFER: self.handle_data,
            Packet.Operation.ACK: self.handle_ack,
        }
        if self.direction == Packet.Direction.PROXY_CLIENT:
            self.operations[Packet.Operation.START] = self.start_session
        
    async def execute_operation(self, tunnel_packet: Packet):
        await self.operations[tunnel_packet.operation](tunnel_packet)


    async def start_session(self, tunnel_packet: Packet):
        """
        operates a start operation, 
        """
        try:
            reader, writer = await asyncio.open_connection(tunnel_packet.destination_host, tunnel_packet.port)
        except ConnectionRefusedError:
            log.debug(f'connection.connect not started: {tunnel_packet.destination_host}:{tunnel_packet.port} refused connection.')
            return

        self.client_manager.add_client(
            session_id=tunnel_packet.session_id,
            reader=reader,
            writer=writer,
        )
        self.send_ack(tunnel_packet)
    async def terminate_session(self, tunnel_packet: Packet):
        """
        operates the TERMINATE operation. removes the client and send ack for terminate.
        """
        await self.client_manager.remove_client(tunnel_packet.session_id)
        self.send_ack(tunnel_packet)
    
    async def handle_data(self, tunnel_packet: Packet):
        """
        operate  data operation. fowards to client and sends ack 
        params: tunnel_packet: used to foward to client the data
        """
        await self.client_manager.write_to_client(
            tunnel_packet.session_id,
            tunnel_packet.seq,
            tunnel_packet.payload
        )
        self.send_ack(tunnel_packet)


    async def handle_ack(self, tunnel_packet: Packet):
        """
        operate an ACK operation.
        the packet is recognized by the session_id and the sequence of packet 
        params: tunnel packet 
        """
        packet_id = (tunnel_packet.session_id, tunnel_packet.seq)
        if packet_id in self.packets_waiting_ack:
            self.packets_waiting_ack[packet_id].set()

    def send_ack(self, tunnel_packet: Packet):
        """
        Send an ACK for a packet using EchoReply.
        used by proxy-server
        """
        ack_tunnel_packet = Packet(
            session_id=tunnel_packet.session_id,
            seq=tunnel_packet.seq,
            operation=Packet.Operation.ACK,
            direction=self.direction,
        )
        self.send_icmp_packet(
            icmp_packet.ICMPType.EchoReply,
            ack_tunnel_packet.SerializeToString(),
        )
    def send_icmp_packet(
            self,
            packet_type: int,
            payload: bytes
    ):
        """
        Build and send an ICMP packet on the ICMP socket.
        params: packet_type echo reply or request
                payload: the tunnel_packet serlized to string
        """
        new_icmp_packet = icmp_packet.ICMPPacket(
            packet_type=packet_type,
            identifier=self.ICMP_PACKET_IDENTIFIER,
            sequence_number=self.PACKET_SEQUENCE_MARKER,
            payload=payload
        )
        self.icmp_socket.sendto(new_icmp_packet, self.remote_endpoint["ip"])

    async def send_icmp_packet_wait_ack(self, tunnel_packet: Packet):
            """
            Send an ICMP packet and ensure it is acknowledged. Retry up to 3 times if necessary.
            params: tunnel_packet the packet sent it the icmp socket
            """
            self.packets_waiting_ack[(tunnel_packet.session_id, tunnel_packet.seq)] = asyncio.Event()

            for _ in range(3):
                self.send_icmp_packet(
                    icmp_packet.ICMPType.EchoRequest,
                    tunnel_packet.SerializeToString(),
                )
                try:
                    await asyncio.wait_for(
                        self.packets_waiting_ack[(tunnel_packet.session_id, tunnel_packet.seq)].wait(),
                        self.RESPONSE_WAIT_TIME
                    )
                    self.packets_waiting_ack.pop((tunnel_packet.session_id, tunnel_packet.seq))
                    return True
                except asyncio.TimeoutError:
                    log.debug(f'failed recive or send ,resending:\n{tunnel_packet}')
                # await asyncio.sleep(1)
            log.info(f'packet failed to send:\n{tunnel_packet}\nRemoving client.')
            await self.timed_out_tcp_connections.put(tunnel_packet.session_id)
