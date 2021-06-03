from socket import socket, AF_INET, SOCK_STREAM
import sqlite3
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from threading import Thread
from auth import hash_password, login
from domain.user import User
from db import Storage
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
        }

    def run(self):
        ssl_listener_th = Thread(target=self.ssl_listener)

        ssl_listener_th.start()
        ssl_listener_th.join()

    def ssl_listener(self):
        context = SSLContext(PROTOCOL_TLS_SERVER)
        context.load_cert_chain("server_ssl/server.crt",
                                "server_ssl/server.key")

        with socket(AF_INET, SOCK_STREAM) as server:
            server.bind((self.ip_address, self.ssl_port))
            server.listen(1)

            with context.wrap_socket(server, server_side=True) as tls:
                while True:
                    connection, address = tls.accept()
                    print(f"Connected by {address}\n")

                    data = connection.recv(1024)
                    self.handle_request(connection, json.loads(data))

    def handle_request(self, connection, request):
        self.commands.get(request.get('type', None),
                          lambda _: _)(connection, request)

    def add_user(self, connection, request):
        username, password = request.get("username"), request.get("password")
        hashed_password = hash_password(password.encode("ascii"))
        try:
            self.db.insert_user(User(username, hashed_password))
            connection.sendall(b"User created")
        except sqlite3.IntegrityError:
            connection.sendall(b"Username is already in use.")

    def login(self, connection, request):
        # TODO: log faild login
        username, password = request.get("username"), request.get("password")
        user = self.db.get_user(username)
        if user and (token := login(user, password.encode("ascii"))):
            payload = {"token": token}
            connection.sendall(json.dumps(payload).encode("ascii"))
        else:
            connection.sendall(b"Invalid username or password")


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
