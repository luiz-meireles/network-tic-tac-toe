from socket import (
    socket,
    AF_INET,
    SOCK_STREAM,
    create_connection,
    error as socket_error,
)
from ssl import SSLContext, PROTOCOL_TLS_CLIENT, PROTOCOL_TLS_SERVER
from threading import Thread, Event, Lock
import json


class RequestHandler:
    def __init__(self, request_id, request_body) -> None:
        self.__request_id = request_id
        self.__request_body = request_body
        self.__ready = Event()
        self.__response = None

    def request_id(self):
        return self.__request_id

    def get_request_body(self):
        return json.dumps(
            {"request_id": self.__request_id, **self.__request_body}
        ).encode("ascii")

    def set_response(self, response):
        self.__response = response

    def get_response(self):
        response = dict(
            (key, self.__response[key])
            for key in self.__response
            if key != "request_id"
        )
        return response

    def wait(self):
        self.__ready.wait()

    def stop_wait(self):
        self.__ready.set()


class ClientConnectionHandler:
    def __init__(
        self,
        ip_address,
        port,
        bufflen=1024,
        keep_alive=True,
        tls=False,
        tls_cert=None,
        server_hostname=None,
    ):
        self.ip_address = ip_address
        self.port = port
        self.tls_cert = tls_cert
        self.tls = tls
        self.server_hostname = server_hostname
        self.bufflen = bufflen

        self.__keep_alive = keep_alive

        self.__request_count_lock = Lock()
        self.__request_count = 1

        self.__requests_lock = Lock()
        self.__requests = {}

        self.__connection_event = Event()
        self.__events = {}
        if self.__keep_alive:
            self.__run()

    def __run(self):
        listener_th = Thread(target=self.__listen)
        listener_th.start()

    def on(self, event, event_handler):
        self.__events[event] = event_handler

    def request(self, request_body):

        if not self.__keep_alive:
            self.__run()

        self.__connection_event.wait()

        request_obj = RequestHandler(self.__request_count, request_body)
        self.__add_request(request_obj)

        try:
            self.__connection.sendall(request_obj.get_request_body())
        except socket_error:
            raise socket_error

        response = self.__get_response(request_obj.request_id())
        self.__remove_request(request_obj.request_id())

        return response

    def __handle_response(self, response):
        request_id = response.get("request_id")
        self.__set_response(request_id, response)

    def __handle_event(self, event):
        event_type = event.get("type")
        event_handler = self.__events.get(event_type)

        event_handler_th = Thread(target=event_handler, args=(event, self.__connection))
        event_handler_th.start()

        return event_handler_th

    def __listen(self):
        # TODO: improve server disconnection handler
        try:
            self.__connection = create_connection((self.ip_address, self.port))
        except socket_error as e:
            # TODO: handle error
            return

        event_handler_threads = []

        if self.tls:
            self.__connection = self.__tls_wrapper(self.__connection)

        self.__connection_event.set()

        while data := self.__connection.recv(self.bufflen):
            if data := json.loads(data or "{}"):
                print(data)
                packet_type = data.get("packet_type")
                if packet_type == "response":
                    self.__handle_response(data)
                elif packet_type == "request":
                    event_handler_th = self.__handle_event(data)
                    event_handler_threads.append(event_handler_th)

            if not self.__keep_alive:
                break

        for thead in event_handler_threads:
            thead.join()

        self.__connection_event.clear()
        self.__connection = None

    def __get_response(self, request_id):
        if (request := self.__requests.get(request_id)) is not None:
            request.wait()
            return request.get_response()

    def __set_response(self, request_id, response):
        if (request := self.__requests.get(request_id)) is not None:
            request.set_response(response)
            request.stop_wait()

    def __remove_request(self, request_id):
        self.__requests.pop(request_id)

    def __add_request(self, request_obj):
        with self.__requests_lock:
            self.__requests[request_obj.request_id()] = request_obj
        with self.__request_count_lock:
            self.__request_count += 1

    def __tls_wrapper(self, socket):
        tls_context = SSLContext(PROTOCOL_TLS_CLIENT)
        tls_context.load_verify_locations(self.tls_cert)

        connection = tls_context.wrap_socket(
            socket, server_hostname=self.server_hostname
        )
        return connection


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

        self.__events = {}
        self.__connections = []
        self.__is_running = True
        self.__connection = None

        Thread.__init__(self)

    def on(self, event, event_handler):
        self.__events[event] = event_handler

    def emit(self, event, payload):
        # TODO: improve this logic
        if self.__is_running:
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
        # TODO: improve server shutdown handler

        self.__connection = socket(AF_INET, SOCK_STREAM)
        self.__connection.bind((self.ip_address, self.port))
        self.__connection.listen(1)

        if self.tls:
            context = SSLContext(PROTOCOL_TLS_SERVER)
            context.load_cert_chain(self.tls_cert, self.tls_key)
            self.__connection = context.wrap_socket(self.__connection, server_side=True)

        while self.__is_running:
            connection, address = self.__connection.accept()
            connection_th = Thread(
                target=self.__handle_connection, args=(connection, address)
            )
            connection_th.start()
            self.__connections.append((connection, address, connection_th))

    def __handle_connection(self, connection, address):
        # TODO: improve client disconnection handler
        while self.__is_running:
            payload = connection.recv(self.bufflen)

            if payload:
                data = json.loads(payload)
                event_type = data.get("packet_name")
                self.__events.get(event_type, lambda *_: _)(data, connection)
            else:
                break


class Request:
    def __init__(self, request) -> None:
        self.request = request

    @property
    def body(self):
        return self.request.get("body")

    @property
    def header(self):
        return self.request.get("header")


class Response:
    def __init__(self, request, connection):
        self.request = request
        self.connection = connection

    def get_request_body(self):
        return self.request.get("body")

    def send(self, payload):
        header = self.request.get("header", {})
        request_id = header.get("request_id")
        payload = {"header": {"request_id": request_id}, "body": payload}

        try:
            self.connection.sendall(json.dumps(payload))
        except socket_error as e:
            print(e)
