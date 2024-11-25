# import asyncio
# import logging
# # from TCPOverICMP import client_manager, icmp_socket, icmp_packet
# # from TCPOverICMP.proto import Packet
# import client_manager, icmp_socket, icmp_packet
# from proto import Packet

# log = logging.getLogger(__name__)


# class TunnelEndpoint:
#     MAGIC_IDENTIFIER = 0xcafe
#     MAGIC_SEQUENCE_NUMBER = 0xbabe
#     ACK_WAITING_TIME = 0.7

#     def __init__(self, other_endpoint = None):
#         self.other_endpoint = other_endpoint
#         log.info(f'other tunnel endpoint: {self.other_endpoint}')

#         self.stale_tcp_connections = asyncio.Queue()
#         self.incoming_from_icmp_channel = asyncio.Queue()
#         self.incoming_from_tcp_channel = asyncio.Queue()

#         self.icmp_socket = icmp_socket.ICMPSocket(self.incoming_from_icmp_channel)
#         self.client_manager = client_manager.ClientManager(self.stale_tcp_connections, self.incoming_from_tcp_channel)

#         self.packets_requiring_ack = {}
#         self.coroutines_to_run = []

#     @property
#     def direction(self):
#         raise NotImplementedError()

#     async def handle_start_request(self, tunnel_packet: Packet):
#         raise NotImplementedError()

#     async def handle_end_request(self, tunnel_packet: Packet):
#         """
#         generic handle for TERMINATE request. remove client and send ack
#         :param tunnel_packet: packet containing the client_id to remove.
#         :return:
#         """
#         await self.client_manager.remove_client(tunnel_packet.client_id)
#         self.send_ack(tunnel_packet)

#     async def handle_data_request(self, tunnel_packet: Packet):
#         """
#         generic handle for data request. forwards to the proper client and sends an ack.
#         :param tunnel_packet: the packet to send.
#         """
#         await self.client_manager.write_to_client(
#             tunnel_packet.client_id,
#             tunnel_packet.seq,
#             tunnel_packet.payload
#         )
#         self.send_ack(tunnel_packet)

#     async def handle_ack_request(self, tunnel_packet: Packet):
#         """
#         generic handle for an ack request.
#         packet can be recognized singularly by combining client_id and seq
#         :param tunnel_packet: the packet to ack.
#         """
#         packet_id = (tunnel_packet.client_id, tunnel_packet.seq)
#         if packet_id in self.packets_requiring_ack:
#             self.packets_requiring_ack[packet_id].set()

#     async def run(self):
#         """
#         run the whole tunnel endpoint, which pretty much means run all the basic tasks and gather them.
#         """
#         constant_coroutines = [
#             self.handle_incoming_from_tcp_channel(),
#             self.handle_incoming_from_icmp_channel(),
#             self.wait_for_stale_connection(),
#             self.icmp_socket.wait_for_incoming_packet(),
#         ]
#         running_tasks = [asyncio.create_task(coroutine) for coroutine in self.coroutines_to_run + constant_coroutines]

#         await asyncio.gather(*running_tasks)

#     async def handle_incoming_from_icmp_channel(self):
#         """
#         listen for new tunnel packets from the icmp channel. parse and execute them.
#         """
#         while True:
#             new_icmp_packet = await self.incoming_from_icmp_channel.get()
#             if new_icmp_packet.identifier != self.MAGIC_IDENTIFIER or new_icmp_packet.seq != self.MAGIC_SEQUENCE_NUMBER:
#                 log.debug(f'wrong magic (identifier={new_icmp_packet.identifier})'
#                           f'(seq_num={new_icmp_packet.seq}), ignoring')
#                 continue

#             tunnel_packet = Packet()
#             tunnel_packet.ParseFromString(new_icmp_packet.payload)
#             log.debug(f'received:\n{tunnel_packet}')
#             #check that uses same function
#             if tunnel_packet.direction == self.direction:
#                 log.debug('ignoring packet headed in the wrong direction')
#                 continue

#             actions = {
#                 Packet.Operation.START: self.handle_start_request,
#                 Packet.Operation.TERMINATE: self.handle_end_request,
#                 Packet.Operation.DATA_TRANSFER: self.handle_data_request,
#                 Packet.Operation.ack: self.handle_ack_request,
#             }
#             await actions[tunnel_packet.operation](tunnel_packet)

#     async def handle_incoming_from_tcp_channel(self):
#         """
#         await on the incoming_from_tcp_channel queue for new data packets to send on the icmp channel.
#         """
#         while True:
#             data, client_id, seq = await self.incoming_from_tcp_channel.get()

#             new_tunnel_packet = Packet(
#                 client_id=client_id,
#                 seq=seq,
#                 operation=Packet.Operation.DATA_TRANSFER,
#                 direction=self.direction,
#                 payload=data,
#             )
#             asyncio.create_task(self.send_icmp_packet_blocking(new_tunnel_packet))

#     async def wait_for_stale_connection(self):
#         """
#         await on the stale_tcp_connections queue for a stale client
#         """
#         while True:
#             client_id = await self.stale_tcp_connections.get()

#             new_tunnel_packet = Packet(client_id=client_id, operation=Packet.Operation.TERMINATE, direction=self.direction)

#             await self.send_icmp_packet_blocking(new_tunnel_packet)
#             await self.client_manager.remove_client(client_id)  # remove client, doesnt matter if the packet was acked.

#     def send_ack(self, tunnel_packet: Packet):
#         """
#         send an ack for a given packet using echoReply
#         :param tunnel_packet: the packet to ack
#         """
#         new_tunnel_packet = Packet(
#             client_id=tunnel_packet.client_id,
#             seq=tunnel_packet.seq,
#             operation=Packet.Operation.ack,
#             direction=self.direction,
#         )
#         self.send_icmp_packet(
#             icmp_packet.ICMPType.EchoReply,
#             new_tunnel_packet.SerializeToString(),
#         )

#     async def send_icmp_packet_blocking(self, tunnel_packet: Packet):
#         """
#         coroutine that tries to send a icmp packet and assert that an ack was received. if an ack wasnt received, send again, up to 3 times.
#         :param tunnel_packet: the packet to send on the icmp socket.
#         :return: boolean representing wether the packet was successfully acked.
#         """
#         self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.seq)] = asyncio.Event()

#         for _ in range(3):
#             self.send_icmp_packet(
#                 icmp_packet.ICMPType.EchoRequest,
#                 tunnel_packet.SerializeToString(),
#             )
#             try:
#                 await asyncio.wait_for(
#                     self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.seq)].wait(),
#                     self.ACK_WAITING_TIME
#                 )
#                 self.packets_requiring_ack.pop((tunnel_packet.client_id, tunnel_packet.seq))  # if i reached here, means that ack was received. can remove event.
#                 return True
#             except asyncio.TimeoutError:
#                 log.debug(f'failed to send, resending:\n{tunnel_packet}')
#         log.info(f'message failed to send:\n{tunnel_packet}\nremoving client.')
#         await self.stale_tcp_connections.put(tunnel_packet.client_id)  # remove client, cannot send his messages.

#     def send_icmp_packet(
#             self,
#             type: icmp_packet.ICMPType,
#             payload: bytes
#     ):
#         """
#         build and send an icmp packet on the icmp socket.
#         :param type: wether to send an echoRequest or an echoReply
#         :param payload: the payload to push into the icmp
#         """
#         new_icmp_packet = icmp_packet.ICMPPacket(
#             type=type,
#             identifier=self.MAGIC_IDENTIFIER,
#             seq=self.MAGIC_SEQUENCE_NUMBER,
#             payload=payload
#         )
#         self.icmp_socket.sendto(new_icmp_packet, self.other_endpoint)
import asyncio
import logging
import client_manager, icmp_socket, icmp_packet
from proto import Packet

log = logging.getLogger(__name__)

class TunnelEndpoint:
    MAGIC_IDENTIFIER = 0xcafe
    MAGIC_SEQUENCE_NUMBER = 0xbabe
    ACK_WAITING_TIME = 0.7

    def __init__(self, other_endpoint=None):
        self.other_endpoint = other_endpoint
        log.info(f'Other tunnel endpoint: {self.other_endpoint}')

        self.stale_tcp_connections = asyncio.Queue()
        self.incoming_from_icmp_channel = asyncio.Queue()
        self.incoming_from_tcp_channel = asyncio.Queue()

        self.icmp_socket = icmp_socket.ICMPSocket(self.incoming_from_icmp_channel)
        self.client_manager = client_manager.ClientManager(self.stale_tcp_connections, self.incoming_from_tcp_channel)

        self.packets_requiring_ack = {}
        self.coroutines_to_run = []

    @property
    def direction(self):
        raise NotImplementedError()

    async def handle_start_request(self, tunnel_packet: Packet):
        raise NotImplementedError()

    async def handle_end_request(self, tunnel_packet: Packet):
        """
        Generic handle for TERMINATE request. Remove client and send ACK.
        """
        await self.client_manager.remove_client(tunnel_packet.client_id)
        self.send_ack(tunnel_packet)

    async def handle_data_request(self, tunnel_packet: Packet):
        """
        Generic handle for data request. Forwards to the proper client and sends an ACK.
        """
        await self.client_manager.write_to_client(
            tunnel_packet.client_id,
            tunnel_packet.seq,
            tunnel_packet.payload
        )
        self.send_ack(tunnel_packet)

    async def handle_ack_request(self, tunnel_packet: Packet):
        """
        Generic handle for an ACK request.
        Packet can be recognized uniquely by combining client_id and seq.
        """
        packet_id = (tunnel_packet.client_id, tunnel_packet.seq)
        if packet_id in self.packets_requiring_ack:
            self.packets_requiring_ack[packet_id].set()

    async def run(self):
        """
        Run the tunnel endpoint tasks.
        """
        constant_coroutines = [
            self.handle_incoming_from_tcp_channel(),
            self.handle_incoming_from_icmp_channel(),
            self.wait_for_stale_connection(),
            self.icmp_socket.wait_for_incoming_packet(),
        ]
        running_tasks = [asyncio.create_task(coro) for coro in self.coroutines_to_run + constant_coroutines]

        await asyncio.gather(*running_tasks)

    async def handle_incoming_from_icmp_channel(self):
        """
        Listen for new tunnel packets from the ICMP channel. Parse and execute them.
        """
        while True:
            new_icmp_packet = await self.incoming_from_icmp_channel.get()
            if new_icmp_packet.identifier != self.MAGIC_IDENTIFIER or new_icmp_packet.sequence_number != self.MAGIC_SEQUENCE_NUMBER:
                log.debug(f'Invalid magic (identifier={new_icmp_packet.identifier})'
                          f'(sequence_number={new_icmp_packet.sequence_number}), ignoring.')
                continue

            tunnel_packet = Packet()
            tunnel_packet.ParseFromString(new_icmp_packet.payload)
            log.debug(f'Received:\n{tunnel_packet}')

            if tunnel_packet.direction == self.direction:
                log.debug('Ignoring packet headed in the wrong direction.')
                continue

            actions = {
                Packet.Operation.START: self.handle_start_request,
                Packet.Operation.TERMINATE: self.handle_end_request,
                Packet.Operation.DATA_TRANSFER: self.handle_data_request,
                Packet.Operation.ack: self.handle_ack_request,
            }
            await actions[tunnel_packet.operation](tunnel_packet)

    async def handle_incoming_from_tcp_channel(self):
        """
        Await on the incoming TCP channel queue for new data packets to send on the ICMP channel.
        """
        while True:
            data, client_id, seq = await self.incoming_from_tcp_channel.get()

            new_tunnel_packet = Packet(
                client_id=client_id,
                seq=seq,
                operation=Packet.Operation.DATA_TRANSFER,
                direction=self.direction,
                payload=data,
            )
            asyncio.create_task(self.send_icmp_packet_blocking(new_tunnel_packet))

    async def wait_for_stale_connection(self):
        """
        Await on the stale TCP connections queue for a stale client.
        """
        while True:
            client_id = await self.stale_tcp_connections.get()

            new_tunnel_packet = Packet(client_id=client_id, operation=Packet.Operation.TERMINATE, direction=self.direction)

            await self.send_icmp_packet_blocking(new_tunnel_packet)
            await self.client_manager.remove_client(client_id)

    def send_ack(self, tunnel_packet: Packet):
        """
        Send an ACK for a given packet using EchoReply.
        """
        new_tunnel_packet = Packet(
            client_id=tunnel_packet.client_id,
            seq=tunnel_packet.seq,
            operation=Packet.Operation.ack,
            direction=self.direction,
        )
        self.send_icmp_packet(
            icmp_packet.ICMPType.EchoReply,
            new_tunnel_packet.SerializeToString(),
        )

    async def send_icmp_packet_blocking(self, tunnel_packet: Packet):
        """
        Send an ICMP packet and ensure it is acknowledged. Retry up to 3 times if necessary.
        """
        self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.seq)] = asyncio.Event()

        for _ in range(3):
            self.send_icmp_packet(
                icmp_packet.ICMPType.EchoRequest,
                tunnel_packet.SerializeToString(),
            )
            try:
                await asyncio.wait_for(
                    self.packets_requiring_ack[(tunnel_packet.client_id, tunnel_packet.seq)].wait(),
                    self.ACK_WAITING_TIME
                )
                self.packets_requiring_ack.pop((tunnel_packet.client_id, tunnel_packet.seq))
                return True
            except asyncio.TimeoutError:
                log.debug(f'Failed to send, resending:\n{tunnel_packet}')
        log.info(f'Message failed to send:\n{tunnel_packet}\nRemoving client.')
        await self.stale_tcp_connections.put(tunnel_packet.client_id)

    def send_icmp_packet(
            self,
            packet_type: int,
            payload: bytes
    ):
        """
        Build and send an ICMP packet on the ICMP socket.
        """
        new_icmp_packet = icmp_packet.ICMPPacket(
            packet_type=packet_type,
            identifier=self.MAGIC_IDENTIFIER,
            sequence_number=self.MAGIC_SEQUENCE_NUMBER,
            payload=payload
        )
        self.icmp_socket.sendto(new_icmp_packet, self.other_endpoint)
