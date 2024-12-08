"""
client_session.py

This module defines the ClientSession class, responsible for managing individual TCP client sessions.
It uses asyncio for asynchronous I/O operations, allowing non-blocking communication.

Key Components:
- session_id: A unique identifier for the session.
- reader: An asyncio StreamReader for receiving data from the client.
- writer: An asyncio StreamWriter for sending data to the client.
- seq: A sequence number generator to track the order of packets.
- packets: A dictionary to store packets that are queued for writing.

Main Methods:
- stop: Closes the client session by shutting down the underlying socket.
- read: Reads a fixed amount of data from the client connection.
- write: Writes data to the client sequentially, ensuring that packets are sent in the correct order.
"""
import asyncio
import logging
import itertools
from TCPOverICMP import exceptions

log = logging.getLogger(__name__)


class ClientSession:
    DATA_SIZE = 1550
    SEQUENCE_INIT = 1
    def __init__(
            self,
            session_id: int,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
    ):
        self.session_id = session_id
        self.reader = reader
        self.writer = writer
        self.seq = itertools.count(self.SEQUENCE_INIT) #handled by ClientManager
        self.last_written = self.SEQUENCE_INIT - 1
        self.packets = {}

    async def stop(self):
        """
        close socket stop client session
        """
        log.debug(f'(session_id={self.session_id}): CLOSING')
        self.writer.close()
        await self.writer.wait_closed()

    async def read(self):
        """
        read RECV_BLOCK_SIZE from the reader
        :return: the data that was just read
        """
        try:
            data = await self.reader.read(self.DATA_SIZE)
        except ConnectionResetError:
            raise exceptions.ClientConnectionClosed()

        if not data:
            raise exceptions.ClientConnectionClosed()
        return data

    async def write(self, seq: int, data: bytes):
        """
        write a packet to the current client, sequentially
        @param seq: the sequence number of the packet. this enables packets to be written in sequence, without duplicates
        @param data: the data to be written
        """
        if self.writer.is_closing():
            raise exceptions.ClientConnectionClosed()

        if seq in self.packets.keys():
            log.debug(f'ignore repeated packet with sequence :{seq}')
            return
        self.packets[seq] = data
        #write all packts before seq number to the StramWriter
        while (self.last_written + 1) in self.packets.keys():
            self.last_written += 1

            self.writer.write(self.packets[self.last_written])
            await self.writer.drain()

            self.packets.pop(self.last_written)
