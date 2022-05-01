# This file is under MIT license. The license file can be obtained in the root
# directory of this module.
try:
    import uasyncio as asyncio
    import usocket as socket
except ImportError:
    import asyncio
    import socket
import time

from sacn.receiving.receiver_socket_base import (
    ReceiverSocketListener,
    ReceiverSocketBase,
)


class AsyncUDPHandler(asyncio.protocols.DatagramProtocol):
    def __init__(self, listener: ReceiverSocketListener, on_con_lost: asyncio.Future):
        self._listener = listener
        self._on_con_lost = on_con_lost
        self.errors = 0
        self.transport = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        print(f"Connected: {transport}")
        self.transport = transport

    def connection_lost(self, exc) -> None:
        print(f"Connection lost {exc}")
        self._on_con_lost.set_result(True)

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self._listener.on_periodic_callback(time.time())
        self._listener.on_data(data, time.time())

    def error_received(self, exc: Exception) -> None:
        self.errors += 1


class AsyncReceiverSocketUDP(ReceiverSocketBase):
    def __init__(self, listener: ReceiverSocketListener, bind_address: str, bind_port: int):
        super().__init__(listener=listener)

        self._bind_address: str = bind_address
        self._bind_port: int = bind_port
        self._enabled_flag: bool = True
        self.transport = self.protocol = None
        self.loop = asyncio.get_event_loop()
        self.on_con_lost = self.loop.create_future()
        self.handler = AsyncUDPHandler(listener, self.on_con_lost)
        self.server_future = None

    async def start(self):
        self._enabled_flag = True
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            protocol_factory=lambda: self.handler,
            local_addr=(self._bind_address, self._bind_port)
        )

    def stop(self):
        self._enabled_flag = False
        if self.transport:
            self.transport._sock.close()

    def join_multicast(self, multicast_addr: str) -> None:
        """
        Join a specific multicast address by string. Only IPv4.
        """
        self.transport._sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP,
                                        socket.inet_aton(multicast_addr) +
                                        socket.inet_aton(self._bind_address))

    def leave_multicast(self, multicast_addr: str) -> None:
        """
        Leave a specific multicast address by string. Only IPv4.
        """
        try:
            self.transport._sock.setsockopt(socket.SOL_IP,
                                            socket.IP_DROP_MEMBERSHIP,
                                            socket.inet_aton(multicast_addr) +
                                            socket.inet_aton(self._bind_address)
                                            )
        except socket.error:  # try to leave the multicast group for the universe
            pass
