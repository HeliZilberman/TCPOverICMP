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
    TUNNEL_STRUCT = struct.Struct('>IHH')  # session_id, action, direction

    def __init__(self, session_id, action, direction, seq=0, destination_host='', port=0, payload=b''):
        """
        Initialize a ICMPTunnelPacket.
        :param session_id: Mandatory. ID of the session.
        :param action: Mandatory. Instance of Action Enum.
        :param direction: Mandatory. Instance of Direction Enum.
        :param seq: Optional. Sequence number.
        :param destination_host: Optional. Destination host as a string.
        :param port: Optional. Destination port as an integer.
        :param payload: Optional. Payload as bytes.
        """
        self.session_id = session_id
        self.action = action  # Must be an instance of Action Enum
        self.direction = direction  # Must be an instance of Direction Enum
        self.seq = seq  # Optional sequence number
        self.destination_host = destination_host  # Optional host, default is empty string
        self.port = port  # Optional port, default is 0
        self.payload = payload  # Optional payload, default is empty bytes

    def serialize(self):
        """
        Serialize the ICMPTunnelPacket into bytes using struct.
        Includes optional fields only if they are present.
        """
        destination_host_bytes = self.destination_host.encode('utf-8')
        host_length = len(destination_host_bytes)

        # Serialize the mandatory fields
        header = self.TUNNEL_STRUCT.pack(
            self.session_id,
            self.action.value,
            self.direction.value
        )

        # Serialize the optional fields
        optional_fields = struct.pack(
            f'>I{host_length}s{len(self.payload)}s',
            self.seq,
            destination_host_bytes,
            self.payload
        )

        return header + optional_fields

    @classmethod
    def deserialize(cls, packet):
        """
        Deserialize bytes into a ICMPTunnelPacket, handling optional fields.
        """
        mandatory_size = cls.TUNNEL_STRUCT.size
        mandatory_data = packet[:mandatory_size]
        session_id, action, direction = cls.TUNNEL_STRUCT.unpack(mandatory_data)

        # Convert enums back
        action = Action(action)
        direction = Direction(direction)

        # Handle optional fields
        optional_data = packet[mandatory_size:]
        if optional_data:
            host_len = len(optional_data) - 8  # Subtract seq (4 bytes) and payload size
            optional_format = f'>I{host_len}s{len(optional_data) - host_len - 4}s'
            seq, destination_host_bytes, payload = struct.unpack(optional_format, optional_data)
            destination_host = destination_host_bytes.decode('utf-8')
        else:
            seq = 0
            destination_host = ''
            payload = b''

        return cls(session_id, action, direction, seq, destination_host, payload)

    def __repr__(self):
        return (
            f"ICMPTunnelPacket(session_id={self.session_id}, action={self.action.name}, "
            f"direction={self.direction.name}, seq={self.seq}, destination_host='{self.destination_host}', "
            f"port={self.port}, payload={self.payload})"
        )