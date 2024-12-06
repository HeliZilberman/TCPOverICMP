import asyncio
import logging
from TCPOverICMP import exceptions
from TCPOverICMP.client_session import ClientSession
log = logging.getLogger(__name__)


class ClientHandler:
    def __init__(self,
                 session: ClientSession,
                 task: asyncio.Task):
        self.session = session
        self.task = task
        


class ClientManager:
    """
    manages all client sessions.
    """
    def __init__(
            self,
            timed_out_connections: asyncio.Queue,
            tcp_input_packets: asyncio.Queue
    ):
        self.clients = {}
        self.timed_out_connections = timed_out_connections
        self.tcp_input_packets = tcp_input_packets

    def client_exists(self, session_id: int):
        """
        returns if client exists
        """
        return session_id in self.clients.keys()

    def add_client(self, session_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        adds a client, a task is created to read from the flient asychronycally.
        @param session_id: the client to add, reader ,writer to create a client session
        """
        if self.client_exists(session_id):
            raise exceptions.ClientAlreadyExistsError()

        new_client_session = ClientSession(session_id, reader, writer)
        new_task = asyncio.create_task(self.read_from_client(session_id))
        self.clients[session_id] = ClientHandler(new_client_session, new_task)
        log.debug(f'added client: session_id={session_id}')

    async def remove_client(self, session_id: int):
        """
        remove a client, doing so by canceling task of cloent 
        @param session_id: the session_id to remove
        returns
        """
        if not self.client_exists(session_id):
            raise exceptions.RemovingClientThatDoesntExistError(session_id, self.clients.keys())
            

        log.debug(f'removing client session: (session_id={session_id})')
        self.clients[session_id].task.cancel()
        await self.clients[session_id].task
        await self.clients[session_id].session.stop()
        self.clients.pop(session_id)

    async def write_to_client(self, session_id: int, seq: int, data: bytes):
        """
        function for writing to a managed client.
        @param session_id: thr client id of the client to writye to.
                seq: the sequence number of the write. for correct order of the packets.
                data: the data to write.
        """
        if not self.client_exists(session_id):
            raise exceptions.WriteAttemptedToNonExistentClient()

        try:
            await self.clients[session_id].session.write(seq, data)
        except exceptions.ClientClosedConnectionError:
            await self.timed_out_connections.put(session_id)

    async def read_from_client(self, session_id: int):
        """
        always read from client, and puts in tcp_input_packets queue.
        @param session_id: the client to read from.
        """
        if not self.client_exists(session_id):
            raise exceptions.ReadAttemptedFromNonExistentClient()

        client = self.clients[session_id].session

        try:
            while True:
                try:
                    data = await client.read()
                except exceptions.ClientClosedConnectionError:
                    await self.timed_out_connections.put(session_id)
                    return

                await self.tcp_input_packets.put((data, client.session_id, next(client.seq)))
        except asyncio.CancelledError:
            pass