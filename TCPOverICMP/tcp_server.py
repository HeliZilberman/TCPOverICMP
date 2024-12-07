import asyncio
import itertools
import socket
import logging


log = logging.getLogger(__name__)

class Server:
    """
    handles tcp connections
    """
    def __init__(self, host: str, port: int, incoming_tcp_connections: asyncio.Queue):
        self.host = host
        self.port = port
        self.incoming_tcp_connections = incoming_tcp_connections
        self.new_session_id = itertools.count()

    async def server_loop(self):
        server = await asyncio.start_server(
            self.operate_new_tcp_connection,
            host=self.host,
            port=self.port,
            family=socket.AF_INET
        )
        log.info(f'listening on {self.host}:{self.port}')
        await server.serve_forever()
    #zzzzzz
    async def operate_new_tcp_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
         # Set the TCP socket send buffer size
        socket_obj = writer.get_extra_info('socket')
        if socket_obj:
            socket_obj.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1400)  
        await self.incoming_tcp_connections.put((next(self.new_session_id), reader, writer))
        log.info(f"new TCP connection {self.new_session_id}")
