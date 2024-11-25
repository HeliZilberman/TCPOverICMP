from proto import Packet

def test_packet():
    # Create an instance of the Packet message
    packet = Packet()
    packet.session_id = 12345
    packet.packet_num = 1
    packet.operation = Packet.Operation.START
    packet.direction = Packet.Direction.PROXY_CLIENT
    packet.ip = "192.168.1.1"
    packet.port = 8080
    packet.payload = b"This is a test payload"

    # Serialize the packet to a byte string
    serialized_packet = packet.SerializeToString()
    print("Serialized Packet:")
    print(serialized_packet)

    # Deserialize the byte string back to a Packet object
    new_packet = Packet()
    new_packet.ParseFromString(serialized_packet)
    print("\nDeserialized Packet:")
    print(f"Session ID: {new_packet.session_id}")
    print(f"Packet Number: {new_packet.packet_num}")
    print(f"Operation: {new_packet.operation}")
    print(f"Direction: {new_packet.direction}")
    print(f"IP: {new_packet.ip}")
    print(f"Port: {new_packet.port}")
    print(f"Payload: {new_packet.payload.decode()}")

if __name__ == "__main__":
    test_packet()