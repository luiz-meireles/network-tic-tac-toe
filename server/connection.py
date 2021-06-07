from socket import socket, AF_INET, SOCK_STREAM, create_connection
from ssl import SSLContext, PROTOCOL_TLS_CLIENT, PROTOCOL_TLS_SERVER
from threading import Thread
from queue import Queue
import json


class ClientConnectionHandler:
    def __init__(
        self, ip_address, port, bufflen=1024, tls_cert=None, server_hostname=None
    ):
        self.ip_address = ip_address
        self.port = port
        self.tls_cert = tls_cert
        self.server_hostname = server_hostname
        self.bufflen = bufflen
        self.events = {}
        self.events_queue = Queue()

    def on(self, event, event_handler):
        self.events[event] = event_handler

    def __tls_wrapper(self, socket):
        tls_context = SSLContext(PROTOCOL_TLS_CLIENT)
        tls_context.load_verify_locations(self.tls_cert)
        connection = tls_context.wrap_socket(
            socket, server_hostname=self.server_hostname
        )
        return connection

    def request(self, request, tls=False):
        with self(tls) as connection:
            connection.sendall(request)
            response = connection.recv(self.bufflen)
        return response

    def listen(self):
        pass

    def __call__(self, tls=False):
        return self.__enter__(tls)

    def __enter__(self, tls=False):
        self.connection = create_connection((self.ip_address, self.port))
        if tls:
            self.connection = self.__tls_wrapper(self.connection)
        return self.connection

    def __exit__(self):
        self.connection.close()


class ServerEventHandler(Thread):
    def __init__(
        self, ip_address, port, bufflen=1024, tls=False, tls_cert=None, tls_key=None
    ) -> None:
        self.ip_address = ip_address
        self.port = port
        self.events = {}
        self.__connections = []
        self.is_running = True
        self.bufflen = bufflen
        self.tls = tls
        self.tls_cert = tls_cert
        self.tls_key = tls_key
        Thread.__init__(self)

    def on(self, event, event_handler):
        self.events[event] = event_handler

    def emit(self, event, payload):
        if self.is_running:
            for connection in self.__connections:
                connection[0].sendall(
                    json.dumps(
                        {
                            "event": event,
                            "payload": payload,
                        }
                    ).encode("ascii")
                )

    def run(self):
        with socket(AF_INET, SOCK_STREAM) as server:
            server.bind((self.ip_address, self.port))
            server.listen(1)

            if self.tls:
                context = SSLContext(PROTOCOL_TLS_SERVER)
                context.load_cert_chain(self.tls_cert, self.tls_key)
                server = context.wrap_socket(server, server_side=True)

            while self.is_running:
                connection, address = server.accept()
                connection_th = Thread(
                    target=self.__handle_connection, args=(connection, address)
                )
                connection_th.start()
                self.__connections.append((connection, address, connection_th))

    def __handle_connection(self, connection, address):
        payload = connection.recv(self.bufflen)

        if payload:
            data = json.loads(payload)
            event_type = data.get("type")
            self.events.get(event_type, lambda *_: _)(data, connection)
