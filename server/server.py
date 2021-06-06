from socket import socket, AF_INET, SOCK_STREAM
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from threading import Thread, Lock
from src.auth import hash_password, check_password
from src.domain.user import User
from src.db import Storage
from connection import ServerEventHandler

import sqlite3
import argparse
import json


class Server:
    def __init__(self, args):
        self.ip_address = "127.0.0.1"
        self.default_port = args.port
        self.ssl_port = args.ssl_port
        self.db = Storage()
        self.logged_users = []
        self.mutex = Lock()
        self.tls_server = ServerEventHandler(self.ip_address, self.ssl_port, bufflen=1024, tls=True,
                                             tls_cert="src/server_ssl/server.crt", tls_key="src/server_ssl/server.key")
        self.no_tls_server = ServerEventHandler(
            self.ip_address, self.default_port)

    def run(self):
        self.tls_server.on("adduser", self.add_user)
        self.tls_server.on("login", self.login)
        self.tls_server.on("password_change", self.change_password)
        self.tls_server.start()

        self.no_tls_server.on("heartbeat", self.heartbeat_recv)
        self.no_tls_server.on("begin", self.new_game)
        self.no_tls_server.on("new_user_connection", self.new_user_connection)
        self.no_tls_server.on("list_players", self.list_players)
        self.no_tls_server.start()

    def heartbeat_recv(self, request, response):
        pass

    def new_game(self, request, response):
        pass

    def list_players(self, request, response):
        response.sendall(json.dumps({
            "status": "OK",
            "players": self.logged_users
        }).encode("ascii"))

    def change_password(self, request, response):
        username = request.get("username")
        current_password = request.get("current_password")
        new_password = request.get("new_password")

        user = self.db.get_user(username)
        if user and check_password(current_password, user.password):
            hashed_password = hash_password(new_password.encode("ascii"))
            try:
                self.db.change_password(username, hashed_password)
                response.sendall(json.dumps({"status": "OK"}))
            except sqlite3.IntegrityError:
                response.sendall(json.dumps(
                    {"status": "FAILD", "error": "Failed to change user password"}))

    def add_user(self, request, response):
        username, password = request.get("username"), request.get("password")
        hashed_password = hash_password(password.encode("ascii"))
        try:
            with self.mutex:
                self.db.insert_user(User(username, hashed_password))
            response.sendall(b"User created")
        except sqlite3.IntegrityError:
            response.sendall(b"Username is already in use.")

    def login(self, request, response):
        # TODO: log faild login
        username, password = request.get("username"), request.get("password")
        user = self.db.get_user(username)
        if user and check_password(password.encode("ascii"), user.password):
            payload = {"status": "OK"}
            response.sendall(json.dumps(payload).encode("ascii"))
        else:
            response.sendall(b"Invalid username or password")

    def new_user_connection(self, request, response):
        username = request.get("username")

        self.logged_users.append({"username": username, "socket": response})
        response.sendall(b"foi rapaziada")

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
