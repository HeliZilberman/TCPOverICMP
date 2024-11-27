# import socket
# import exceptions


# class ICMPType:
#     EchoReply = 0
#     EchoRequest = 8


# class ICMPPacket:
#     """
#     ICMP Packet implementation 
#     """

#     CODE = 0

#     def __init__(self, packet_type, identifier, sequence_number, payload):
#         self.type = packet_type  
#         self.identifier = identifier  
#         self.sequence_number = sequence_number  
#         self.payload = payload  

#     @staticmethod
#     def unpack_header(packet : bytes):
#         """
#         Unpack the ICMP header 
#         :params packet 
#         """
#         packet_type = packet[0]
#         code = packet[1]
#         checksum = (packet[2] << 8) | packet[3]
#         identifier = (packet[4] << 8) | packet[5]
#         sequence_number = (packet[6] << 8) | packet[7]
#         return packet_type, code, checksum, identifier, sequence_number

#     @staticmethod
#     def pack_header(packet_type, code, checksum, identifier, sequence_number):
#         """
#         Pack the ICMP header to bytes 
#         :params header fields to pack into bytes
#         returns the icmp header
#         """
#         header = bytearray(8)
#         header[0] = packet_type
#         header[1] = code
#         header[2] = (checksum >> 8) & 0xFF
#         header[3] = checksum & 0xFF
#         header[4] = (identifier >> 8) & 0xFF
#         header[5] = identifier & 0xFF
#         header[6] = (sequence_number >> 8) & 0xFF
#         header[7] = sequence_number & 0xFF
#         return bytes(header)

#     @classmethod
#     def deserialize(cls, packet: bytes):
#         """
#         Build ICMPPacket based on a stream of bytes.
#         param packet: packet to deseralize into an ICMPPacket
#         returns an icmppacket
#         """
#         packet_type, code, checksum, identifier, sequence_number = cls.unpack_header(packet)

#         if code != cls.CODE:
#             raise exceptions.InvalidICMPCode()

#         computed_checksum = cls.compute_checksum(
#             cls.pack_header(packet_type, code, 0, identifier, sequence_number) + packet[8:]
#         )

#         if checksum != computed_checksum:
#             raise exceptions.WrongChecksumOnICMPPacket()

#         return cls(packet_type, identifier, sequence_number, packet[8:]) #packet [8:] is payload

#     def serialize(self):
#         """
#         Serialize the ICMPPacket into raw bytes.
#         """
#         packet_compute_checksum = self.pack_header(
#             self.type,
#             self.CODE,
#             0,
#             self.identifier,
#             self.sequence_number
#         ) + self.payload

#         checksum = self.compute_checksum(packet_compute_checksum)

#         return self.pack_header(
#             self.type,
#             self.CODE,
#             checksum,
#             self.identifier,
#             self.sequence_number
#         ) + self.payload

#     @staticmethod
#     def compute_checksum(data: bytes):
#         """
#         Compute the checksum for the ICMP packet.
#         param: data a bytes header without checksum
#         returms checksum
#         """
#         count_to = (len(data) // 2) * 2
#         total = 0
#         count = 0

#         while count < count_to:
#             total += (data[count + 1] << 8) + data[count]
#             count += 2

#         if count_to < len(data):  # Handle last byte if applicable (odd-length data)
#             total += data[-1]

#         total &= 0xFFFFFFFF  # Truncate sum to 32 bits
#         total = (total >> 16) + (total & 0xFFFF)  # Add high 16 bits to low 16 bits
#         total += (total >> 16)  # Add carry from above
#         result = ~total & 0xFFFF  # Invert and truncate to 16 bits
#         result = socket.htons(result)
#         return result

import struct
import socket
import exceptions


class ICMPType:
    EchoReply = 0
    EchoRequest = 8


class ICMPPacket:
    """
    ICMP Packet implementation using struct.Struct for serialization and deserialization.
    """

    CODE = 0
    ICMP_STRUCT = struct.Struct('>BBHHH')  # Type, Code, Checksum, Identifier, Sequence Number

    def __init__(self, packet_type, identifier, sequence_number, payload):
        self.type = packet_type  
        self.identifier = identifier  
        self.sequence_number = sequence_number  
        self.payload = payload  

    @classmethod
    def deserialize(cls, packet: bytes):
        """
        Build ICMPPacket based on a stream of bytes using ICMP_STRUCT.
        :param packet: packet to deserialize into an ICMPPacket
        :returns: an instance of ICMPPacket
        """
        # Unpack the ICMP header
        header = packet[:cls.ICMP_STRUCT.size]
        packet_type, code, checksum, identifier, sequence_number = cls.ICMP_STRUCT.unpack(header)

        # Validate the ICMP code
        if code != cls.CODE:
            raise exceptions.InvalidICMPCode()

        # Compute and validate the checksum
        computed_checksum = cls.compute_checksum(
            cls.ICMP_STRUCT.pack(packet_type, code, 0, identifier, sequence_number) + packet[cls.ICMP_STRUCT.size:]
        )
        if checksum != computed_checksum:
            raise exceptions.WrongChecksumOnICMPPacket()

        return cls(packet_type, identifier, sequence_number, packet[cls.ICMP_STRUCT.size:])  # Payload is after the header

    def serialize(self):
        """
        Serialize the ICMPPacket into raw bytes using ICMP_STRUCT.
        :returns: the serialized ICMP packet as bytes
        """
        # Create a packet without a checksum
        packet_without_checksum = self.ICMP_STRUCT.pack(
            self.type,
            self.CODE,
            0,  # Placeholder for checksum
            self.identifier,
            self.sequence_number
        ) + self.payload

        # Compute the checksum
        checksum = self.compute_checksum(packet_without_checksum)

        # Pack the final packet with the checksum
        return self.ICMP_STRUCT.pack(
            self.type,
            self.CODE,
            checksum,
            self.identifier,
            self.sequence_number
        ) + self.payload

    @staticmethod
    def compute_checksum(data: bytes):
        """
        Compute the checksum for the ICMP packet.
        :param data: the packet data for which to compute the checksum
        :returns: the checksum as an integer
        """
        count_to = (len(data) // 2) * 2
        total = 0
        count = 0

        while count < count_to:
            total += (data[count + 1] << 8) + data[count]
            count += 2

        if count_to < len(data):  # Handle the case of an odd-length packet
            total += data[-1]

        # Fold 32-bit sum into 16 bits
        total &= 0xFFFFFFFF
        total = (total >> 16) + (total & 0xFFFF)
        total += (total >> 16)

        # One's complement and network byte order
        return socket.htons(~total & 0xFFFF)