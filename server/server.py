from socket import socket, AF_INET, SOCK_STREAM
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from threading import Thread, Lock, Timer
from src.auth import hash_password, check_password
from src.domain.user import User
from src.db import Storage
from connection import ServerEventHandler, set_interval

import sqlite3
import argparse
import json
import time


class Server:
    def __init__(self, args):
        self.ip_address = "127.0.0.1"
        self.default_port = args.port
        self.tls_port = args.tls_port
        self.db = Storage()
        self.logged_users = {}
        self.db_lock = Lock()
        self.logged_users_lock = Lock()
        self.connection_handler = ServerEventHandler(self.ip_address, self.default_port)
        self.secure_connection_handler = ServerEventHandler(
            self.ip_address,
            self.tls_port,
            bufflen=1024,
            tls=True,
            tls_cert="src/server_ssl/server.crt",
            tls_key="src/server_ssl/server.key",
        )

        set_interval(self.__heartbeat, 60)

    def run(self):
        self.secure_connection_handler.on("adduser", self.add_user)
        self.secure_connection_handler.on("login", self.login)
        self.secure_connection_handler.on("password_change", self.change_password)
        self.secure_connection_handler.start()

        self.connection_handler.on("heartbeat", self.heartbeat_recv)
        self.connection_handler.on("begin", self.new_game)
        self.connection_handler.on("new_user_connection", self.new_user_connection)
        self.connection_handler.on("list_players", self.list_players)
        self.connection_handler.on("logout", self.logout)
        self.connection_handler.start()

    def heartbeat_recv(self, request, response):
        pass

    def new_game(self, request, response):
        pass

    def list_players(self, request, response):
        payload = {
            "packet_type": "response",
            "packet_name": "list_players",
            "request_id": request.get("request_id"),
            "status": "OK",
            "players": [user.username for user in self.logged_users.values()],
        }
        response.sendall(json.dumps(payload).encode("ascii"))

    def change_password(self, request, response):
        username = request.get("username")
        current_password = request.get("current_password")
        new_password = request.get("new_password")
        user = self.db.get_user(username)

        if user and check_password(current_password.encode("ascii"), user.password):
            hashed_password = hash_password(new_password.encode("ascii"))

            try:
                with self.db_lock:
                    self.db.change_password(username, hashed_password)
                payload = {
                    "packet_type": "response",
                    "packet_name": "change_password",
                    "request_id": request.get("request_id"),
                    "status": "OK",
                }
                response.sendall(json.dumps(payload).encode("ascii"))
            except sqlite3.IntegrityError:
                payload = {
                    "packet_type": "response",
                    "packet_name": "change_password",
                    "request_id": request.get("request_id"),
                    "status": "FAIL",
                    "error": "Failed to change user password",
                }
                response.sendall(json.dumps(payload).encode("ascii"))

    def add_user(self, request, response):
        username, password = request.get("username"), request.get("password")
        hashed_password = hash_password(password.encode("ascii"))
        try:
            with self.db_lock:
                self.db.insert_user(User(username, hashed_password))
            payload = {
                "packet_type": "response",
                "packet_name": "add_user",
                "request_id": request.get("request_id"),
                "status": "OK",
            }
            response.sendall(json.dumps(payload).encode("ascii"))
        except sqlite3.IntegrityError:
            payload = {
                "packet_type": "response",
                "packet_name": "add_user",
                "request_id": request.get("request_id"),
                "status": "FAIL",
                "error": "Username is already in use",
            }
            response.sendall(json.dumps(payload).encode("ascii"))

    def login(self, request, response):
        # TODO: log faild login
        username, password = request.get("username"), request.get("password")
        with self.db_lock:
            user = self.db.get_user(username)
        if user and check_password(password.encode("ascii"), user.password):
            payload = {
                "packet_type": "response",
                "packet_name": "login",
                "request_id": request.get("request_id"),
                "status": "OK",
            }
            response.sendall(json.dumps(payload).encode("ascii"))
        else:
            payload = {
                "packet_type": "response",
                "packet_name": "login",
                "request_id": request.get("request_id"),
                "status": "FAIL",
                "error": "Invalid username or password",
            }
            response.sendall(json.dumps(payload).encode("ascii"))

    def new_user_connection(self, request, response):
        username = request.get("username")
        peer_address = request.get("peer_address")
        with self.logged_users_lock:
            self.logged_users[username] = User(username, peer_address)
        response.sendall(
            json.dumps(
                {
                    "packet_type": "response",
                    "packet_name": "new_user_connection",
                    "request_id": request.get("request_id"),
                    "status": "OK",
                }
            ).encode("ascii")
        )

    def logout(self, request, response):
        username = request.get("username")
        with self.logged_users_lock:
            if username in self.logged_users:
                self.logged_users.pop(username)
        response.sendall(
            json.dumps(
                {
                    "packet_type": "response",
                    "packet_name": "logout",
                    "request_id": request.get("request_id"),
                    "status": "OK",
                }
            ).encode("ascii")
        )

    def __heartbeat(self):
        errors = self.connection_handler.emit(
            json.dumps({"packet_type": "request", "packet_name": "heartbeat"}).encode(
                "ascii"
            )
        )
        print(errors)


def main():
    parser = argparse.ArgumentParser(
        description="Execute a server for a tic tac toe game"
    )
    parser.add_argument("-p", "--port", type=int, help="server port")
    parser.add_argument("-tlsp", "--tls-port", type=int, help="secure server port")

    args = parser.parse_args()

    server = Server(args)
    server.run()


if __name__ == "__main__":
    main()
