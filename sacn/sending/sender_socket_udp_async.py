# This file is under MIT license. The license file can be obtained in the root directory of this module.

try:
    import uasyncio as asyncio
    import usocket as socket
except ImportError:
    import asyncio
    import socket
import time

from sacn.messages.root_layer import RootLayer
from sacn.sending.sender_socket_base import SenderSocketBase, SenderSocketListener, DEFAULT_PORT

THREAD_NAME = 'sACN sending/sender thread'


class AsyncSenderProtocol(asyncio.protocols.DatagramProtocol):
    def __init__(self, on_con_lost: asyncio.Future):
        self.on_con_lost = on_con_lost
        self.transport = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data, addr):
        print("Received:", data.decode())

    def error_received(self, exc: Exception):
        print('Error received:', exc)

    def connection_lost(self, exc: Exception):
        print("Connection closed")
        self.on_con_lost.set_result(True)


class AsyncSenderSocketUDP(SenderSocketBase):
    """
    Implements a sender socket with a UDP socket of the OS using asyncio.
    """

    def __init__(self, listener: SenderSocketListener, bind_address: str, bind_port: int, fps: int):
        super().__init__(listener=listener)

        self._bind_address: str = bind_address
        self._bind_port: int = bind_port
        self._enabled_flag: bool = True
        self.fps: int = fps
        self._bind_address: str = bind_address
        self.transport = self.protocol = None
        self.loop = asyncio.get_event_loop()
        self.on_con_lost = self.loop.create_future()
        self.handler = AsyncSenderProtocol(self.on_con_lost)
        self.server = self.loop.create_datagram_endpoint(
            protocol_factory=lambda: self.handler, remote_addr=(self._bind_address, self._bind_port))
        self.server_future = None

    def start(self):
        # initialize thread infos
        self.server_future = asyncio.ensure_future(self.send_loop())

    async def send_loop(self) -> None:
        self._logger.info(f'Started {THREAD_NAME}')
        self._enabled_flag = True
        while self._enabled_flag:
            time_stamp = time.time()
            self._listener.on_periodic_callback(time_stamp)
            time_to_sleep = (1 / self.fps) - (time.time() - time_stamp)
            if time_to_sleep < 0:  # if time_to_sleep is negative (because the loop has too much work to do) set it to 0
                time_to_sleep = 0
            await asyncio.sleep(time_to_sleep)
            # this sleeps nearly exactly so long that the loop is called every 1/fps seconds

        self._logger.info(f'Stopped {THREAD_NAME}')

    def stop(self) -> None:
        """
        Stops a running thread and closes the underlying socket. If no thread was started, nothing happens.
        Do not reuse the socket after calling stop once.
        """
        self._enabled_flag = False
        # wait for the thread to finish
        try:
            self._thread.join()
            # stop the socket, after the loop terminated
            self._socket.close()
        except AttributeError:
            pass

    def send_unicast(self, data: RootLayer, destination: str) -> None:
        self.send_packet(data.getBytes(), destination)

    def send_multicast(self, data: RootLayer, destination: str, ttl: int) -> None:
        # make socket multicast-aware: (set TTL)
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self.send_packet(data.getBytes(), destination)

    def send_broadcast(self, data: RootLayer) -> None:
        # hint: on windows a bind address must be set, to use broadcast
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.send_packet(data.getBytes(), destination='<broadcast>')

    def send_packet(self, data: bytearray, destination: str) -> None:
        data_raw = bytearray(data)
        try:
            self._socket.sendto(data_raw, (destination, DEFAULT_PORT))
        except OSError as e:
            self._logger.warning('Failed to send packet', exc_info=e)
