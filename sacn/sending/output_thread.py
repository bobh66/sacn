# This file is under MIT license. The license file can be obtained in the root directory of this module.

import threading
import socket
import time

from .output import Output
from ..messages.universe_discovery import UniverseDiscoveryPacket

DEFAULT_PORT = 5568
SEND_OUT_INTERVAL = 1
E131_E131_UNIVERSE_DISCOVERY_INTERVAL = 10


class OutputThread(threading.Thread):
    def __init__(self, cid: tuple, source_name: str, outputs: dict, bind_address,
                 bind_port: int = DEFAULT_PORT, fps: int = 30, universe_discovery: bool = True):
        super().__init__(name='sACN sending/sender thread')
        self.__CID: tuple = cid
        self._sourceName: str = source_name
        self._outputs: dict = outputs
        self._bindAddress = bind_address
        self.enabled_flag: bool = True
        self.fps: int = fps
        self._bind_port = bind_port
        self._socket: socket.socket = None
        self.universeDiscovery: bool = universe_discovery

    def run(self):
        self._socket = socket.socket(socket.AF_INET,  # Internet
                                     socket.SOCK_DGRAM)  # UDP
        try:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except:  # Not all systems support multiple sockets on the same port and interface
            pass
        self._socket.bind((self._bindAddress, self._bind_port))

        last_time_uni_discover = 0
        self.enabled_flag = True
        while self.enabled_flag:
            time_stamp = time.time()

            # send out universe discovery packets if necessary
            if abs(time.time() - last_time_uni_discover) > E131_E131_UNIVERSE_DISCOVERY_INTERVAL \
                    and self.universeDiscovery:
                self.send_uni_discover_packets()
                last_time_uni_discover = time.time()

            # go through the list of outputs and send everything out that has to be send out
            for output in list(self._outputs.values()):  # dict may changes size during iteration (multithreading)
                # send out when the 1 second interval is over
                if abs(time.time() - output._last_time_send) > SEND_OUT_INTERVAL or output._changed:
                    # make socket multicast-aware: (set TTL)
                    self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, output.ttl)
                    self.send_out(output)

            time_to_sleep = (1 / self.fps) - (time.time() - time_stamp)
            if time_to_sleep < 0:  # if time_to_sleep is negative (because the loop has too much work to do) set it to 0
                time_to_sleep = 0
            time.sleep(time_to_sleep)
            # this sleeps nearly exactly so long that the loop is called every 1/fps seconds
        self._socket.close()

    def send_out(self, output: Output):
        # 1st: Destination (check if multicast)
        if output.multicast:
            udp_ip = output._packet.calculate_multicast_addr()
            # make socket multicast-aware: (set TTL) for some reason that does not work here,
            # so its in the run method from above
            # socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, sending.ttl)
        else:
            udp_ip = output.destination

        self.send_packet(output._packet, udp_ip)
        output._last_time_send = time.time()
        # increase the sequence counter
        output._packet.sequence_increase()
        # the changed flag is not necessary any more
        output._changed = False

    def send_uni_discover_packets(self):  # hint: on windows a bind address must be set, to use broadcast
        packets = UniverseDiscoveryPacket.make_multiple_uni_disc_packets(
            cid=self.__CID, sourceName=self._sourceName, universes=list(self._outputs.keys()))
        for packet in packets:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.send_packet(packet=packet, destination="<broadcast>")

    def send_packet(self, packet, destination: str):
        MESSAGE = bytearray(packet.getBytes())
        self._socket.sendto(MESSAGE, (destination, DEFAULT_PORT))
