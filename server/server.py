from socket import socket, AF_INET, SOCK_STREAM
import sqlite3
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from threading import Thread, Lock
from src.auth import hash_password, check_password
from src.domain.user import User
from src.db import Storage
import argparse
import json


class Server:
    def __init__(self, args):
        self.ip_address = "127.0.0.1"
        self.default_port = args.port
        self.ssl_port = args.ssl_port
        self.db = Storage()
        self.commands = {
            "adduser": self.add_user,
            "login": self.login,
            "new_user_connection": self.new_user_connection
        }
        self.logged_users = []
        self.mutex = Lock()

    def run(self):
        default_listener_th = Thread(target=self.default_listener)
        ssl_listener_th = Thread(target=self.ssl_listener)

        default_listener_th.start()
        ssl_listener_th.start()

        default_listener_th.join()
        ssl_listener_th.join()

    def default_listener(self):
        with socket(AF_INET, SOCK_STREAM) as server:
            server.bind((self.ip_address, self.default_port))
            server.listen(1)

            while True:
                connection, address = server.accept()
                print(f"Connected by {address}\n")

                data = connection.recv(1024)
                request_th = Thread(target=self.handle_request, args=(
                    connection, json.loads(data)))
                request_th.start()

    def ssl_listener(self):
        context = SSLContext(PROTOCOL_TLS_SERVER)
        context.load_cert_chain("src/server_ssl/server.crt",
                                "src/server_ssl/server.key")

        with socket(AF_INET, SOCK_STREAM) as server:
            server.bind((self.ip_address, self.ssl_port))
            server.listen(1)

            with context.wrap_socket(server, server_side=True) as tls:
                while True:
                    connection, address = tls.accept()
                    print(f"Connected by {address}\n")

                    data = connection.recv(1024)
                    request_th = Thread(target=self.handle_request, args=(
                        connection, json.loads(data)))
                    request_th.start()

    def handle_request(self, connection, request):
        self.commands.get(request.get('type', None),
                          lambda _: _)(connection, request)

    def add_user(self, connection, request):
        username, password = request.get("username"), request.get("password")
        hashed_password = hash_password(password.encode("ascii"))
        try:
            self.mutex.acquire()
            self.db.insert_user(User(username, hashed_password))
            self.mutex.release()
            connection.sendall(b"User created")
        except sqlite3.IntegrityError:
            connection.sendall(b"Username is already in use.")

    def login(self, connection, request):
        # TODO: log faild login
        username, password = request.get("username"), request.get("password")
        user = self.db.get_user(username)
        if user and check_password(password.encode("ascii"), user.password):
            payload = {"status": "OK"}
            connection.sendall(json.dumps(payload).encode("ascii"))
        else:
            connection.sendall(b"Invalid username or password")

    def new_user_connection(self, connection, request):
        username = request.get("username")

        self.logged_users.append({"username": username, "socket": connection})
        connection.sendall(b"foi rapaziada")

    def heartbeat_polling_thread(self):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Execute a server for a tic tac toe game"
    )
    parser.add_argument("--port", type=int, help="server port")
    parser.add_argument("--ssl-port", type=int, help="secure server port")

    args = parser.parse_args()

    server = Server(args)
    server.run()


if __name__ == "__main__":
    main()
