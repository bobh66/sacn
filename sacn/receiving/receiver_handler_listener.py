from sacn.messages.data_packet import DataPacket


class ReceiverHandlerListener:
    """
    Listener interface that defines methods for listening on changes on the ReceiverHandler.
    """

    def on_availability_change(self, universe: int, changed: str) -> None:
        raise NotImplementedError

    def on_dmx_data_change(self, packet: DataPacket) -> None:
        raise NotImplementedError
