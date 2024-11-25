from proto import Packet


def test_packet_creation_and_serialization():
    # Create a new Packet instance
    packet = Packet()
    packet.client_id = 1234
    packet.seq = 1
    packet.operation = Packet.START
    packet.direction = Packet.PROXY_CLIENT
    packet.ip = "192.168.1.1"
    packet.port = 8080
    packet.payload = b"Test payload"

    # Serialize the Packet to a string
    serialized_packet = packet.SerializeToString()
    print("Serialized Packet:")
    print(serialized_packet)

    # Deserialize the string back into a Packet
    deserialized_packet = Packet()
    deserialized_packet.ParseFromString(serialized_packet)

    # Print the deserialized Packet
    print("\nDeserialized Packet:")
    print(f"Client ID: {deserialized_packet.client_id}")
    print(f"Sequence Number: {deserialized_packet.seq}")
    print(f"Operation: {deserialized_packet.operation}")
    print(f"Direction: {deserialized_packet.direction}")
    print(f"IP: {deserialized_packet.ip}")
    print(f"Port: {deserialized_packet.port}")
    print(f"Payload: {deserialized_packet.payload.decode()}")


if __name__ == "__main__":
    test_packet_creation_and_serialization()