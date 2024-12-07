"""
icmp_socket.py

This module defines the ICMPSocket class, responsible for managing ICMP communication using raw sockets.
It facilitates sending and receiving ICMP packets asynchronously, making it suitable for non-blocking operations.

Key Components:
- _icmp_socket: A raw socket for ICMP communication.
- packet_queue: An asyncio.Queue to store received ICMP packets.

Main Methods:
- recv: Asynchronously receives ICMP packets and deserializes them.
- wait_for_incoming_packet: Continuously listens for incoming ICMP packets and adds them to the packet queue.
- sendto: Sends an ICMP packet to a specified destination.
"""


import sys
import asyncio
import socket
import logging
from TCPOverICMP.icmp_packet import ICMPPacket  
import struct
from TCPOverICMP import exceptions

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class ICMPSocket:
    DEFAULT_ICMP_TARGET = ('', 0)
    IPv4_HEADER_SIZE = 20
    SOCKET_BUFFER_SIZE = 4096
    ICMP_INIT_PACKET = b'\x00\x00'

    def __init__(self, packet_queue: asyncio.Queue):
        self.packet_queue = packet_queue

        try:
            self._icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        except PermissionError as e:
            log.fatal(f'{e}. root required for opening raw ICMP socket. Rerun as root.')
            sys.exit(1)
        
        self._icmp_socket.setblocking(False)  #no need to wait to a replay
        #to intialize a raw socket
        self._icmp_socket.sendto(self.ICMP_INIT_PACKET, self.DEFAULT_ICMP_TARGET)  

    async def recv(self, remote_endpoint: dict, buffersize: int = SOCKET_BUFFER_SIZE):
        """
        recives an icmp packet
        @param buffersize: the max data to recive (bytes)
        returns  an ICMP packet that was sniffed.
        """
        data = await asyncio.get_event_loop().sock_recv(self._icmp_socket, buffersize)
        if not data:
            raise exceptions.RecivedEmptyData()
        # Deserialize the ICMP packet
        try:
            raw_packet = data[self.IPv4_HEADER_SIZE:]  # Remove IP header
            #when handling start from the proxy_server
            if remote_endpoint["ip"]==None:
                # IP header is the first 20 bytes for IPv4 without options
                ip_header = data[:20]
                # Unpack the IP header (source IP is at byte offset 12-15)
                iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
                source_ip = socket.inet_ntoa(iph[8]) 
                log.info(f"remote endpoint: {source_ip}")
                remote_endpoint["ip"] = source_ip
            return ICMPPacket.deserialize(raw_packet)
        except exceptions.InvalidICMPCode:
            log.debug("Invalid ICMP code detected, skipping packet.")
            return None

    async def wait_for_incoming_packet(self, remote_endpoint:dict = None):
        """
        listen on socket for incoming ICMP packets and put them into the queue(sniff).
        @param remote_endpoint - initialize the ip of the repmote endpoint if needed
        """
        while True:
            try:
                packet = await self.recv(remote_endpoint)
                if packet is not None:
                    await self.packet_queue.put(packet)
            except exceptions.InvalidICMPCode:
                # Ignore invalid packets
                pass

    def sendto(self, packet: ICMPPacket, destination: str):
        """
        Send an ICMP packet to the specified destination.
        @param packet An instance of ICMPPacket to send.
        @param destination The IP address of the destination.
        """
        log.debug(f'Sending packet: \n{packet.payload} to {destination}')
        self._icmp_socket.sendto(packet.serialize(), (destination, 0))