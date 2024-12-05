import asyncio
import logging
from TCPOverICMP import client_manager, icmp_socket,icmp_operations_handler 
from TCPOverICMP.proto import ICMPTunnelPacket


log = logging.getLogger(__name__)

class TCPoverICMPTunnel:
    def __init__(self,direction: ICMPTunnelPacket.Direction , remote_endpoint=None):
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
                action=ICMPTunnelPacket.Action.DATA_TRANSFER,
                direction=self.direction,
                payload=data,
            )
            log.info(f'data size is: {len(data)}')
            #scheduale the packet sending action
            asyncio.create_task(self.operations_handler.send_icmp_packet_wait_ack(new_tunnel_packet))
    
    
    async def handle_packets_from_icmp_channel(self):
        """
        await to newe packets from the ICMP channel, parse the packets and execute the action
        """
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != self.operations_handler.ICMP_PACKET_IDENTIFIER or new_icmp_packet.sequence_number != self.operations_handler.PACKET_SEQUENCE_MARKER:
                log.debug(f'Invalid ICMP project identifiers')
                continue

            icmp_tunnel_packet = ICMPTunnelPacket()
            icmp_tunnel_packet.ParseFromString(new_icmp_packet.payload)
            log.debug(f'Received:\n{icmp_tunnel_packet}')

            if icmp_tunnel_packet.direction == self.direction:
                log.debug('ifnore packet to same direction')
                continue


            #execute the packet action 
            await self.operations_handler.execute_operation(icmp_tunnel_packet=icmp_tunnel_packet) 

            # operations = {
            #     ICMPTunnelPacket.Action.START: self.start_session,
            #     ICMPTunnelPacket.Action.TERMINATE: self.terminate_session,
            #     ICMPTunnelPacket.Action.DATA_TRANSFER: self.handle_data,
            #     ICMPTunnelPacket.Action.ACK: self.handle_ack,
            # }
            # await operations[icmp_tunnel_packet.action](icmp_tunnel_packet)

   

    async def wait_timed_out_connections(self):
        """
        await on the timed out TCP connections queue for a timed out client 
        terminate session and delete client 
        """
        while True:
            session_id = await self.timed_out_tcp_connections.get()

            new_tunnel_packet = ICMPTunnelPacket(session_id=session_id,
                                        action=ICMPTunnelPacket.Action.TERMINATE,
                                          direction=self.direction)
            #The subsequent code depends on the successful completion of 
            await self.operations_handler.send_icmp_packet_wait_ack(new_tunnel_packet)
            await self.client_manager.remove_client(session_id)

    # def send_ack(self, icmp_tunnel_packet: ICMPTunnelPacket):
    #     """
    #     Send an ACK for a packet using EchoReply.
    #     used by proxy-server
    #     """
    #     ack_tunnel_packet = ICMPTunnelPacket(
    #         session_id=icmp_tunnel_packet.session_id,
    #         seq=icmp_tunnel_packet.seq,
    #         action=ICMPTunnelPacket.Action.ACK,
    #         direction=self.direction,
    #     )
    #     self.send_icmp_packet(
    #         icmp_packet.ICMPType.EchoReply,
    #         ack_tunnel_packet.SerializeToString(),
    #     )

    # async def send_icmp_packet_wait_ack(self, icmp_tunnel_packet: ICMPTunnelPacket):
    #     """
    #     Send an ICMP packet and ensure it is acknowledged. Retry up to 3 times if necessary.
    #     params: icmp_tunnel_packet the packet sent it the icmp socket
    #     """
    #     self.packets_waiting_ack[(icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq)] = asyncio.Event()

    #     for _ in range(3):
    #         # self.send_icmp_packet(
    #         #     icmp_packet.ICMPType.EchoRequest,
    #         #     icmp_tunnel_packet.SerializeToString(),
    #         # )
    #         self.operations_handler.send_icmp_packet(
    #             icmp_packet.ICMPType.EchoRequest,
    #             icmp_tunnel_packet.SerializeToString(),
    #         )
    #         try:
    #             await asyncio.wait_for(
    #                 self.packets_waiting_ack[(icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq)].wait(),
    #                 self.RESPONSE_WAIT_TIME
    #             )
    #             self.packets_waiting_ack.pop((icmp_tunnel_packet.session_id, icmp_tunnel_packet.seq))
    #             return True
    #         except asyncio.TimeoutError:
    #             log.debug(f'failed recive or send ,resending:\n{icmp_tunnel_packet}')
    #         # await asyncio.sleep(1)
    #     log.info(f'packet failed to send:\n{icmp_tunnel_packet}\nRemoving client.')
    #     await self.timed_out_tcp_connections.put(icmp_tunnel_packet.session_id)

    # def send_icmp_packet(
    #         self,
    #         packet_type: int,
    #         payload: bytes
    # ):
    #     """
    #     Build and send an ICMP packet on the ICMP socket.
    #     params: packet_type echo reply or request
    #             payload: the icmp_tunnel_packet serlized to string
    #     """
    #     new_icmp_packet = icmp_packet.ICMPPacket(
    #         packet_type=packet_type,
    #         identifier=self.ICMP_PACKET_IDENTIFIER,
    #         sequence_number=self.PACKET_SEQUENCE_MARKER,
    #         payload=payload
    #     )
    #     self.icmp_socket.sendto(new_icmp_packet, self.remote_endpoint["ip"])
