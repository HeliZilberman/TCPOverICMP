"""
tunnel_packet.py

This file defines the ICMPTunnelPacket class, which is responsible for handling the creation, serialization, 
and deserialization of tunnel packets sent over ICMP. It includes enums for Action and Direction to specify 
the type of operation and communication direction.

- Action: Enum representing operations like START, TERMINATE, DATA_TRANSFER, and ACK.
- Direction: Enum indicating whether the packet is for the PROXY_SERVER or PROXY_CLIENT.

The ICMPTunnelPacket class uses struct to pack and unpack packet fields, including:
- session_id: Unique session identifier.
- action: The action to perform (e.g., START, DATA_TRANSFER).
- direction: The direction of communication.
- seq: Optional sequence number.
- destination_host: Optional destination host.
- port: Optional destination port.
- payload: Optional payload data.

Key Methods:
- serialize(): Converts the packet into bytes for transmission.
- deserialize(): Reconstructs a packet object from a byte stream.
- __repr__(): Provides a formatted string representation for easy debugging.
"""
import struct
from enum import Enum

class Action(Enum):
    """
    Represents the action for a Tunnel Packet.
    """
    START = 0
    TERMINATE = 1
    DATA_TRANSFER = 2
    ACK = 3


class Direction(Enum):
    """
    Represents the direction for a Tunnel Packet.
    """
    PROXY_SERVER = 0
    PROXY_CLIENT = 1

class ICMPTunnelPacket:
    """
    Tunnel Packet implementation using struct for serialization and deserialization.
    Handles optional fields gracefully.
    """
    TUNNEL_STRUCT = struct.Struct('>IIIHHI')  # client_id, seq, action, direction, port,destination_host


    def __init__(self, session_id, action, direction, seq=0, destination_host='', port=0, payload=b''):
        """
        Initialize a ICMPTunnelPacket.
        @param session_id: Mandatory. ID of the session.
        @param action: Mandatory. Instance of Action Enum.
        @param direction: Mandatory. Instance of Direction Enum.
        @param seq: Optional. Sequence number.
        @param destination_host: Optional. Destination host as a string.
        @param port: Optional. Destination port as an integer.
        @param payload: Optional. Payload as bytes.
        """
        self.session_id = session_id
        self.action = action  
        self.direction = direction  
        self.seq = seq  
        self.destination_host = destination_host 
        self.port = port  
        self.payload = payload  

    def serialize(self):
        """
        Serialize the TunnelPacket into bytes using struct.
        """
        ip_bytes = self.destination_host.encode('utf-8')  # Encode the IP as bytes
        ip_length = len(ip_bytes)
        header = self.TUNNEL_STRUCT.pack(
            self.session_id,
            self.seq,
            ip_length,
            self.action.value,
            self.direction.value,
            self.port
        )
        return header + ip_bytes + self.payload
    
    @classmethod
    def deserialize(cls, packet):
        """
        Deserialize bytes into a TunnelPacket.
        """
        header_size = cls.TUNNEL_STRUCT.size
        header = packet[:header_size]
        session_id, seq, ip_length, action, direction, port = cls.TUNNEL_STRUCT.unpack(header)
        action = Action(action)
        direction = Direction(direction)

        ip_bytes = packet[header_size:header_size + ip_length]
        destination_host = ip_bytes.decode('utf-8')

        payload = packet[header_size + ip_length:]  # Remaining bytes are the payload

        return cls(session_id, action, direction, seq, destination_host, port, payload)
    

    def __repr__(self):
     base_repr = (
        f"ICMPTunnelPacket(\n"
        f"    session_id={self.session_id},\n"
        f"    seq={self.seq},\n"
        f"    action={self.action.name},\n"
        f"    direction={self.direction.name},\n"
     )

     if self.action == Action.DATA_TRANSFER:
        return (
            base_repr +
            f"    payload={self.payload}\n"
            f")"
        )
     elif self.action == Action.START:
        return (
            base_repr +
            f"    destination_host='{self.destination_host}',\n"
            f"    port={self.port}\n"
            f")"
        )
     else:
        return base_repr + ")"


  
       
   