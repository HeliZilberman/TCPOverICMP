"""
tcp_over_icmp_tunnel.py

This module defines the TCPoverICMPTunnel class, which provides the core functionality for tunneling TCP traffic 
over ICMP. The class handles the sending and receiving of ICMP packets, manages client sessions, and ensures reliable 
communication by handling acknowledgments and retransmissions. Both ProxyClient and ProxyServer classes inherit from 
this base class and customize it for client-side and server-side operations, respectively.

Key Components:
- ICMP_PACKET_IDENTIFIER: Used to validate incoming ICMP packets.
- PACKET_SEQUENCE_MARKER: Helps track the sequence of packets.
- RESPONSE_WAIT_TIME: Defines the time to wait for an acknowledgment.

Main Methods:
- run: Starts all tasks related to the tunnel.
- handle_packets_from_tcp_channel: Sends TCP data as ICMP packets.
- handle_packets_from_icmp_channel: Processes incoming ICMP packets and executes corresponding actions.
- send_icmp_packet_wait_ack: Sends an ICMP packet and waits for an acknowledgment.
"""
import asyncio
import logging
from TCPOverICMP import client_manager, icmp_socket, icmp_packet
from TCPOverICMP.tunnel_packet import ICMPTunnelPacket, Action, Direction


log = logging.getLogger(__name__)

class TCPoverICMPTunnel:
    #recognizing the protocols packets
    ICMP_PACKET_IDENTIFIER = 0xbeef
    PACKET_SEQUENCE_MARKER = 0xdead
    RESPONSE_WAIT_TIME = 1.0 #waiting time for ack

    def __init__(self,
                 direction: Direction,
                  remote_endpoint=None):
        self.remote_endpoint = {"ip": remote_endpoint}
        self.direction = direction 
        self.incoming_from_icmp_channel = asyncio.Queue()
        self.icmp_socket = icmp_socket.ICMPSocket(self.incoming_from_icmp_channel)

        self.packets_from_tcp_channel = asyncio.Queue()
        self.timed_out_tcp_connections = asyncio.Queue()
        self.client_manager = client_manager.ClientManager(self.timed_out_tcp_connections, self.packets_from_tcp_channel)


        self.main_coroutines = [
            self.handle_packets_from_tcp_channel(),
            self.handle_packets_from_icmp_channel(),
            self.wait_timed_out_connections(),
            self.icmp_socket.wait_for_incoming_packet(self.remote_endpoint),
        ]
        #handles packets from ICMP channel
        self.packets_waiting_ack = {}
        self.operations = {
            Action.TERMINATE: self.terminate_session,
            Action.DATA_TRANSFER: self.handle_data,
            Action.ACK: self.handle_ack,
        }
        if self.direction == Direction.PROXY_CLIENT:
            self.operations[Action.START] = self.start_session
        

    async def run(self):
        """
        runs the classe's coroutines - run all tasks of class
        """
        running_tasks = [asyncio.create_task(coro) for coro in self.main_coroutines]
        await asyncio.gather(*running_tasks)

    

    async def handle_packets_from_tcp_channel(self):
        """
        await for  the new data packets on the incoming TCP channel queue to send on the ICMP channel.
        """
        while True:
            data, session_id, seq = await self.packets_from_tcp_channel.get()

            new_tunnel_packet = ICMPTunnelPacket(
                session_id=session_id,
                seq=seq,
                action=Action.DATA_TRANSFER,
                direction=self.direction,
                payload=data,
            )
            log.debug(f'packet size to session:{session_id} with sequnce {seq} is: {len(data)}')
            #scheduale the packet sending action
            asyncio.create_task(self.send_icmp_packet_wait_ack(new_tunnel_packet))
    
    
    async def handle_packets_from_icmp_channel(self):
        """
        await to newe packets from the ICMP channel, parse the packets and execute the action
        """
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != self.ICMP_PACKET_IDENTIFIER:
                log.debug(f'Invalid ICMP project identifiers')
                continue

            icmp_tunnel_packet = ICMPTunnelPacket.deserialize(new_icmp_packet.payload)

            
            log.debug(f'Received: \n{icmp_tunnel_packet}')

            if icmp_tunnel_packet.direction == self.direction:
                log.debug('ignore packet to same direction')
                continue
            # if new_icmp_packet != self.operations_handler.PACKET_SEQUENCE_MARKER:

            #execute the packet action 
            await self.execute_operation(icmp_tunnel_packet=icmp_tunnel_packet) 

    async def wait_timed_out_connections(self):
        """
        await on the timed out TCP connections queue for a timed out client 
        terminate session and delete client 
        """
        while True:
            session_id = await self.timed_out_tcp_connections.get()
            new_tunnel_packet = ICMPTunnelPacket(session_id=session_id,
                                        action=Action.TERMINATE,
                                          direction=self.direction)
            
            #The subsequent code depends on the successful completion of 
            await self.send_icmp_packet_wait_ack(new_tunnel_packet)
            await self.client_manager.remove_client(session_id)
    
    #class methods handles ICMP packets

    async def execute_operation(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """executes the the packets request"""
        await self.operations[icmp_tunnel_packet.action](icmp_tunnel_packet)

    async def start_session(self, icmp_tunnel_packet: ICMPTunnelPacket):
        """implemented by proxy server"""
        return NotImplementedError()
    async def open_tcp_connection(self,destination_host, port, mss=1400):
        """implemented by proxy server"""
        return NotImplementedError()
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
