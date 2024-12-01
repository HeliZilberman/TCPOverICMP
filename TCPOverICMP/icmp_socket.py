# import sys
# import asyncio
# import socket
# import logging
# import icmp_packet, exceptions

# log = logging.getLogger(__name__)
# log.setLevel(logging.DEBUG)


# class ICMPSocket(object):
#     IP_HEADER_LENGTH = 20
#     MINIMAL_PACKET = b'\x00\x00'
#     DEFAULT_DESTINATION_PORT = 0
#     DEFAULT_DESTINATION = ('', DEFAULT_DESTINATION_PORT)
#     DEFAULT_BUFFERSIZE = 4096

#     def __init__(self, incoming_queue: asyncio.Queue):
#         self.incoming_queue = incoming_queue

#         try:
#             self._icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
#         except PermissionError as e:
#             log.fatal(f'{e}. root required for opening raw ICMP socket. rerun as root..')
#             sys.exit(1)
#         self._icmp_socket.setblocking(False) #don't wait for reply
#         self._icmp_socket.sendto(self.MINIMAL_PACKET, self.DEFAULT_DESTINATION)  # need to send one packet, because didnt bind. otherwise exception is raised when using on first packet.

#     async def recv(self, buffersize: int = DEFAULT_BUFFERSIZE):
#         """
#         receive a single ICMP packet.
#         :param buffersize:  maximal length of data to receive.
#         :return: an instance of ICMPPacket, representing a sniffed ICMP packet.
#         """
#         data = await asyncio.get_event_loop().sock_recv(self._icmp_socket, buffersize)
#         if not data:
#             raise exceptions.RecvReturnedEmptyString()
#         return icmp_packet.ICMPPacket.deserialize(data[self.IP_HEADER_LENGTH:])  # packet includes IP header, so remove it.
#     async def wait_for_incoming_packet(self):
#         """
#         "listen" on the socket, pretty much sniff raw for ICMP packets, and put them in the incoming ICMP queue.
#         :return:
#         """
#         while True:
#             try:
#                 packet = await self.recv()
#                 await self.incoming_queue.put(packet)
#             except exceptions.InvalidICMPCode:
#                 # Handle InvalidICMPCode exception by simply continuing the loop.
#                 # This mimics the behavior of contextlib.suppress.
#                 pass

#     def sendto(self, packet: icmp_packet.ICMPPacket, destination: str):
#         """
#         receive an icmp packet, and sent it to the destination.
#         :param packet: an instance if ICMPPacket that is to be sent.
#         :param destination: the IP of the destination.
#         """
#         log.debug(f'sending {packet.payload} to {destination}')
#         self._icmp_socket.sendto(packet.serialize(), (destination, self.DEFAULT_DESTINATION_PORT))
import sys
import asyncio
import socket
import logging
from icmp_packet import ICMPPacket  
import struct
import exceptions

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ICMPSocket:
    MINIMAL_PACKET = b'\x00\x00'
    DEFAULT_DESTINATION_PORT = 0
    DEFAULT_DESTINATION = ('', DEFAULT_DESTINATION_PORT)
    IP_HEADER_LENGTH = 20
    DEFAULT_BUFFERSIZE = 4096

    def __init__(self, incoming_queue: asyncio.Queue):
        self.incoming_queue = incoming_queue

        try:
            self._icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError as e:
            log.fatal(f'{e}. root required for opening raw ICMP socket. Rerun as root.')
            sys.exit(1)
        
        self._icmp_socket.setblocking(False)  #no need to wait to a replay
        #to intialize a raw socket
        self._icmp_socket.sendto(self.MINIMAL_PACKET, self.DEFAULT_DESTINATION)  

    async def recv(self, other_endpoint: dict, buffersize: int = DEFAULT_BUFFERSIZE):
        """
        Receive a single ICMP packet.
        :param buffersize: Maximum length of data to receive.
        :return: An instance of ICMPPacket representing a sniffed ICMP packet.
        """
        data = await asyncio.get_event_loop().sock_recv(self._icmp_socket, buffersize)
        if not data:
            raise exceptions.RecvReturnedEmptyString()
        # Deserialize the ICMP packet
        try:
            raw_packet = data[self.IP_HEADER_LENGTH:]  # Remove IP header
            #when handling start from the proxy_server
            if other_endpoint["ip"]==None:
                # IP header is the first 20 bytes for IPv4 without options
                ip_header = data[:20]
                # Unpack the IP header (source IP is at byte offset 12-15)
                iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
                source_ip = socket.inet_ntoa(iph[8]) 
                log.info(f"Source IP Address: {source_ip}")
                other_endpoint["ip"] = source_ip
            return ICMPPacket.deserialize(raw_packet)
        except exceptions.InvalidICMPCode:
            log.debug("Invalid ICMP code detected, skipping packet.")
            return None

    async def wait_for_incoming_packet(self, other_endpoint:dict = None):
        """
        "Listen" on the socket for incoming ICMP packets and put them into the queue.
        """
        while True:
            try:
                packet = await self.recv(other_endpoint)
                if packet is not None:
                    await self.incoming_queue.put(packet)
            except exceptions.InvalidICMPCode:
                # Ignore invalid packets
                pass

    def sendto(self, packet: ICMPPacket, destination: str):
        """
        Send an ICMP packet to the specified destination.
        :param packet: An instance of ICMPPacket to send.
        :param destination: The IP address of the destination.
        """
        log.debug(f'Sending packet with payload: {packet.payload} to {destination}')
        self._icmp_socket.sendto(packet.serialize(), (destination, self.DEFAULT_DESTINATION_PORT))