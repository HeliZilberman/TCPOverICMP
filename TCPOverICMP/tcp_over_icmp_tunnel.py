import asyncio
import logging
from TCPOverICMP import client_manager, icmp_socket,icmp_operations_handler 
from TCPOverICMP.tunnel_packet import ICMPTunnelPacket, Action, Direction

import time

log = logging.getLogger(__name__)

class TCPoverICMPTunnel:
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

        self.operations_handler = icmp_operations_handler.ICMPOperationsHandler(self.client_manager,
                                                                       self.icmp_socket,
                                                                       self.remote_endpoint,
                                                                       direction,
                                                                       self.timed_out_tcp_connections)
        self.main_coroutines = [
            self.handle_packets_from_tcp_channel(),
            self.handle_packets_from_icmp_channel(),
            self.wait_timed_out_connections(),
            self.icmp_socket.wait_for_incoming_packet(self.remote_endpoint),
        ]
        

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
            asyncio.create_task(self.operations_handler.send_icmp_packet_wait_ack(new_tunnel_packet))
    
    
    async def handle_packets_from_icmp_channel(self):
        """
        await to newe packets from the ICMP channel, parse the packets and execute the action
        """
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != self.operations_handler.ICMP_PACKET_IDENTIFIER:
                log.debug(f'Invalid ICMP project identifiers')
                continue

            icmp_tunnel_packet = ICMPTunnelPacket.deserialize(new_icmp_packet.payload)

            
            log.debug(f'Received: \n{icmp_tunnel_packet}')

            if icmp_tunnel_packet.direction == self.direction:
                log.debug('ignore packet to same direction')
                continue
            # if new_icmp_packet != self.operations_handler.PACKET_SEQUENCE_MARKER:

            #execute the packet action 
            await self.operations_handler.execute_operation(icmp_tunnel_packet=icmp_tunnel_packet) 


   

    async def wait_timed_out_connections(self):
        """
        await on the timed out TCP connections queue for a timed out client 
        terminate session and delete client 
        """
        while True:
            session_id = await self.timed_out_tcp_connections.get()

            # new_tunnel_packet = ICMPTunnelPacket(session_id=session_id,
            #                             action=ICMPTunnelPacket.Action.TERMINATE,
            #                               direction=self.direction)
            new_tunnel_packet = ICMPTunnelPacket(session_id=session_id,
                                        action=Action.TERMINATE,
                                          direction=self.direction)
            
            #The subsequent code depends on the successful completion of 
            await self.operations_handler.send_icmp_packet_wait_ack(new_tunnel_packet)
            await self.client_manager.remove_client(session_id)

