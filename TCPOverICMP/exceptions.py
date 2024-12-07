
class InvalidChecksum(Exception):
    pass


class InvalidICMPCode(Exception):
    pass


class RecivedEmptyData(Exception):
    pass

class ClientConnectionClosed(Exception):
    pass


class WriteNonExistentClient(Exception):
    pass


class ReadNonExistentClient(Exception):
    pass


class ClientSessionAlreadyON(Exception):
    pass


class RemoveNonExistClient(Exception):
    pass
