# python -m unittest test_overhead.py
import unittest
from TCPOverICMP.tunnel_packet import ICMPTunnelPacket, Action, Direction
from TCPOverICMP.icmp_packet import ICMPPacket,ICMPType


#test overhead
class TestTCPOvertICMP(unittest.TestCase):

    def test_icmp_packet_overhead(self):
        """
        Calculate the total overhead, including the ICMP header and serialized tunnel packet.
        """
        # Create a Tunnel ICMPTunnelPacket
        tunnel_packet = ICMPTunnelPacket(
            session_id=1,
            seq=1,
            action=Action.DATA_TRANSFER,
            direction=Direction.PROXY_CLIENT,
            destination_host="127.0.0.1",
            port=8080,
            payload=b""  # No payload
        )

        # Serialize Tunnel ICMPTunnelPacket
        serialized_tunnel_packet = tunnel_packet.serialize()
        tunnel_packet_size = len(serialized_tunnel_packet)
        # Create an ICMP ICMPTunnelPacket
        icmp_packet = ICMPPacket(
            packet_type=ICMPType.EchoRequest,
            identifier=0x1234,  # Example identifier
            sequence_number=0x5678,  # Example sequence number
            payload=serialized_tunnel_packet
        )

        # Serialize ICMP ICMPTunnelPacket
        serialized_icmp_packet = icmp_packet.serialize()
        icmp_packet_size = len(serialized_icmp_packet)

        # Calculate overhead
        icmp_header_size = 8  # Fixed ICMP header size
        total_overhead = icmp_packet_size - len(tunnel_packet.payload)

        print(f"Tunnel ICMPTunnelPacket Overhead: {tunnel_packet_size} bytes")
        print(f"ICMP ICMPTunnelPacket Overhead: {icmp_packet_size} bytes (including ICMP header)")
        print(f"ICMP Header Size: {icmp_header_size} bytes")
        print(f"Total Overhead (Tunnel + ICMP): {total_overhead} bytes")

        # Assert that overhead is within expected bounds
        self.assertGreater(icmp_packet_size, icmp_header_size)
        self.assertGreater(total_overhead, tunnel_packet_size)

if __name__ == "__main__":
    unittest.main()
