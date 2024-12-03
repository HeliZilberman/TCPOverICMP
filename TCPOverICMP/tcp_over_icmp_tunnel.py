import asyncio
import logging
import client_manager, icmp_socket, icmp_packet
from proto import Packet

log = logging.getLogger(__name__)

class TCPoverICMPTunnel:
    RESPONSE_WAIT_TIME = 1.0 #my computer is slow - time to wait for ack 

    #special identifiers for debugging in wireshark
    ICMP_PACKET_IDENTIFIER = 0xbeef
    PACKET_SEQUENCE_MARKER = 0xdead

    def __init__(self, remote_endpoint=None):
        self.remote_endpoint = {"ip": remote_endpoint}
        self.incoming_from_icmp_channel = asyncio.Queue()
        self.icmp_socket = icmp_socket.ICMPSocket(self.incoming_from_icmp_channel)

        self.incoming_from_tcp_channel = asyncio.Queue()
        self.timed_out_tcp_connections = asyncio.Queue()
        self.client_manager = client_manager.ClientManager(self.timed_out_tcp_connections, self.incoming_from_tcp_channel)

        self.packets_waiting_ack = {}
        self.constant_coroutines = [
            self.operate_incoming_from_tcp_channel(),
            self.operate_incoming_from_icmp_channel(),
            self.wait_timed_out_connections(),
            self.icmp_socket.wait_for_incoming_packet(self.remote_endpoint),
        ]

    @property
    def direction(self):
        """recognize the packet direction (implemented in the proxy_client,proxy_server)"""
        raise NotImplementedError()

    async def operate_start_operation(self, tunnel_packet: Packet):
        """proxy server implements """
        raise NotImplementedError()
    
    async def operate_data_operation(self, tunnel_packet: Packet):
        """
        operate  data operation. fowards to client and sends ack 
        params: tunnel_packet  the packet that is sent to client ,
        """
        await self.client_manager.write_to_client(
            tunnel_packet.session_id,
            tunnel_packet.seq,
            tunnel_packet.payload
        )
        self.send_ack(tunnel_packet)

    async def operate_terminate_operation(self, tunnel_packet: Packet):
        """
        operates the TERMINATE operation. removes the client and send ack for terminate.
        """
        await self.client_manager.remove_client(tunnel_packet.session_id)
        self.send_ack(tunnel_packet)

    

    async def operate_ack_request(self, tunnel_packet: Packet):
        """
        operate an ACK operation.
        the packet is recognized by the session_id and the sequence of packet 
        params: tunnel packet 
        """
        packet_id = (tunnel_packet.session_id, tunnel_packet.seq)
        if packet_id in self.packets_waiting_ack:
            self.packets_waiting_ack[packet_id].set()

    async def run(self):
        """
        runs the classe's coroutines - run all tasks of class
        """
        running_tasks = [asyncio.create_task(coro) for coro in self.constant_coroutines]
        await asyncio.gather(*running_tasks)

    async def operate_incoming_from_tcp_channel(self):
        """
        await for  the new data packets on the incoming TCP channel queue to send on the ICMP channel.
        """
        while True:
            data, session_id, seq = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Packet(
                session_id=session_id,
                seq=seq,
                operation=Packet.Operation.DATA_TRANSFER,
                direction=self.direction,
                payload=data,
            )
            asyncio.create_task(self.send_icmp_packet_wait_ack(new_tunnel_packet))
    
    
    async def operate_incoming_from_icmp_channel(self):
        """
        await to newe packets from the ICMP channel, parse the packets and execute the action
        """
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != self.ICMP_PACKET_IDENTIFIER or new_icmp_packet.sequence_number != self.PACKET_SEQUENCE_MARKER:
                log.debug(f'Invalid magic (identifier={new_icmp_packet.identifier})'
                          f'(sequence_number={new_icmp_packet.sequence_number}), ignoring.')
                continue

            tunnel_packet = Packet()
            tunnel_packet.ParseFromString(new_icmp_packet.payload)
            log.debug(f'Received:\n{tunnel_packet}')

            if tunnel_packet.direction == self.direction:
                log.debug('ifnore packet to same direction')
                continue
            #execute the packet action    
            operations = {
                Packet.Operation.START: self.operate_start_operation,
                Packet.Operation.TERMINATE: self.operate_terminate_operation,
                Packet.Operation.DATA_TRANSFER: self.operate_data_operation,
                Packet.Operation.ACK: self.operate_ack_request,
            }
            await operations[tunnel_packet.operation](tunnel_packet)

   

    async def wait_timed_out_connections(self):
        """
        await on the timed out TCP connections queue for a timed out client 
        terminate session and delete client 
        """
        while True:
            session_id = await self.timed_out_tcp_connections.get()

            new_tunnel_packet = Packet(session_id=session_id, operation=Packet.Operation.TERMINATE, direction=self.direction)

            await self.send_icmp_packet_wait_ack(new_tunnel_packet)
            await self.client_manager.remove_client(session_id)

    def send_ack(self, tunnel_packet: Packet):
        """
        Send an ACK for a packet using EchoReply.
        used by proxy-server
        """
        new_tunnel_packet = Packet(
            session_id=tunnel_packet.session_id,
            seq=tunnel_packet.seq,
            operation=Packet.Operation.ACK,
            direction=self.direction,
        )
        self.send_icmp_packet(
            icmp_packet.ICMPType.EchoReply,
            new_tunnel_packet.SerializeToString(),
        )

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
