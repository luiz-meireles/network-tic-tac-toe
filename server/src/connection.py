from socket import (
    socket,
    AF_INET,
    SOCK_STREAM,
    SOL_SOCKET,
    SO_REUSEADDR,
    create_connection,
    error as socket_error,
)
from ssl import SSLContext, PROTOCOL_TLS_CLIENT, PROTOCOL_TLS_SERVER
from threading import Thread, Lock, Timer
from types import SimpleNamespace
import json


class ServerEventHandler(Thread):
    def __init__(
        self, ip_address, port, bufflen=1024, tls=False, tls_cert=None, tls_key=None
    ):
        self.ip_address = ip_address
        self.port = port
        self.bufflen = bufflen
        self.tls = tls
        self.tls_cert = tls_cert
        self.tls_key = tls_key

        self.__events_lock = Lock()
        self.__events = {}
        self.__connections_lock = Lock()
        self.__connections = {}
        self.__is_running = True
        self.__connection = None

        Thread.__init__(self)

    def on(self, event, event_handler):
        self.__events[event] = event_handler

    def emit(self, payload):
        # TODO: improve this logic
        connection_errors = []
        if self.__is_running:
            with self.__connections_lock:
                for address, connection_info in self.__connections.items():
                    connection, _ = connection_info
                    try:
                        connection.sendall(payload)
                    except ConnectionResetError:
                        connection_errors.append(address)
        return connection_errors

    def run(self):
        # TODO: improve server shutdown handler

        self.__connection = socket(AF_INET, SOCK_STREAM)
        self.__connection.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.__connection.bind((self.ip_address, self.port))
        self.__connection.listen(1)

        if self.tls:
            context = SSLContext(PROTOCOL_TLS_SERVER)
            context.load_cert_chain(self.tls_cert, self.tls_key)
            self.__connection = context.wrap_socket(self.__connection, server_side=True)

        while self.__is_running:
            connection, address = self.__connection.accept()
            connection_th = Thread(
                target=self.__handle_connection, args=(connection, address), daemon=True
            )
            connection_th.start()
            with self.__connections_lock:
                self.__connections[address] = (connection, connection_th)

            self.__events.get("connection", lambda *_: _)({}, connection)

    def __handle_connection(self, connection, address):
        # TODO: improve client disconnection handler
        connection.sendall(b"OK")
        while self.__is_running:
            payload = connection.recv(self.bufflen)

            if payload:
                data = json.loads(payload)
                event_type = data.get("packet_name")

                with self.__events_lock:
                    self.__events.get(event_type, lambda *_: _)(data, connection)
            else:
                with self.__connections_lock:
                    if address in self.__connections:
                        self.__connections.pop(address)
                        self.__events.get("disconnection", lambda *_: _)({}, connection)
                break


def set_interval(func, sec):
    def func_wrapper():
        set_interval(func, sec)
        func()

    t = Timer(sec, func_wrapper)
    t.start()

    return t


def response_wrapper(handler):
    def _send(request, connection):
        def send(packet_name, data={}, packet_type="response"):
            connection.sendall(
                json.dumps(
                    {
                        "packet_type": packet_type,
                        "packet_name": packet_name,
                        "request_id": request.request_id,
                        **data,
                    }
                ).encode("ascii")
            )

        return SimpleNamespace(send=send, peername=connection.getpeername())

    def wrapper(self, request, connection):
        req_obg = SimpleNamespace(**request)
        handler(self, req_obg, _send(req_obg, connection))

    return wrapper
