from threading import Thread, Lock, Timer
from src.auth import hash_password, check_password
from src.domain.user import User
from src.db import Storage
from src.connection import ServerEventHandler, set_interval, response_wrapper

import sqlite3
import argparse
import json


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

        with self.db_lock:
            self.db.insert_log("server_started", {"status": "OK"})

        set_interval(self.__heartbeat, 60)

    def run(self):
        self.secure_connection_handler.on("adduser", self.__add_user)
        self.secure_connection_handler.on("login", self.__login)
        self.secure_connection_handler.on("password_change", self.__change_password)
        self.secure_connection_handler.on("connection", self.__connection)
        self.secure_connection_handler.on("disconnection", self.__disconnection)

        self.secure_connection_handler.start()

        self.connection_handler.on("new_user_connection", self.__new_user_connection)
        self.connection_handler.on("list_players", self.__list_players)
        self.connection_handler.on("leaderboard", self.__leaderboard)
        self.connection_handler.on("logout", self.__logout)
        self.connection_handler.on("update_player_status", self.__update_player_status)
        self.connection_handler.on("connection", self.__connection)
        self.connection_handler.start()

    @response_wrapper
    def __list_players(self, request, response):
        response.send(
            "list_players",
            {
                "status": "OK",
                "players": self.logged_users,
            },
        )

    @response_wrapper
    def __leaderboard(self, request, response):
        users = self.db.get_all_users()
        users_list = list(
            map(
                lambda user: {
                    "username": user[0],
                    "wins": user[1],
                    "ties": user[3],
                    "loses": user[2],
                    "points": 2 * user[1] + user[3],
                },
                users,
            )
        )
        leaderboard = sorted(users_list, key=lambda user: user["points"], reverse=True)

        response.send("leaderboard", {"status": "OK", "leaderboard": list(leaderboard)})

    @response_wrapper
    def __change_password(self, request, response):
        username = request.username
        current_password = request.current_password
        new_password = request.new_password
        user = self.db.get_user(username)

        if user and check_password(current_password.encode("ascii"), user.password):
            hashed_password = hash_password(new_password.encode("ascii"))

            try:
                with self.db_lock:
                    self.db.change_password(username, hashed_password)
                response.sendall(
                    "change_password",
                    {
                        "status": "OK",
                    },
                )
            except sqlite3.IntegrityError:

                response.send(
                    "change_password",
                    {
                        "status": "FAIL",
                        "error": "Failed to change user password",
                    },
                )

    @response_wrapper
    def __add_user(self, request, response):
        username, password = request.username, request.password
        hashed_password = hash_password(password.encode("ascii"))
        try:
            with self.db_lock:
                self.db.insert_user(User(username, hashed_password))
            response.send("add_user", {"status": "OK"})
        except sqlite3.IntegrityError:
            response.send(
                "add_user",
                {
                    "status": "FAIL",
                    "error": "Username is already in use",
                },
            )

    @response_wrapper
    def __login(self, request, response):
        # TODO: log faild login
        username, password = request.username, request.password
        user = self.db.get_user(username)

        if user and check_password(password.encode("ascii"), user.password):
            with self.db_lock:
                self.db.insert_log(
                    "login",
                    {"status": "OK", "ip": response.peername[0], "username": username},
                )
            response.send("login", {"status": "OK"})
        else:
            with self.db_lock:
                self.db.insert_log(
                    "login",
                    {
                        "status": "FAIL",
                        "ip": response.peername[0],
                        "username": username,
                    },
                )
            response.send(
                "login",
                {
                    "status": "FAIL",
                    "error": "Invalid username or password",
                },
            )

    @response_wrapper
    def __new_user_connection(self, request, response):
        username = request.username
        client_listen_port = request.listen_port
        addr = response.peername

        with self.logged_users_lock:
            self.logged_users[username] = [addr[0], client_listen_port]
        response.send(
            "new_user_connection",
            {
                "status": "OK",
            },
        )

    @response_wrapper
    def __logout(self, request, response):
        username = request.username
        ip, _ = response.peername
        with self.logged_users_lock, self.db_lock:
            if username in self.logged_users:
                self.logged_users.pop(username)
                self.db.insert_log("logout", {"ip": ip})
        response.send(
            "logout",
            {
                "status": "OK",
            },
        )

    @response_wrapper
    def __update_player_status(self, request, response):
        username, game_status = request.username, request.game_status

        with self.db_lock:
            self.db.update_user_status(username, game_status)
        response.send("update_game_status", {"status": "OK"})

    def __heartbeat(self):
        address_errors = self.connection_handler.emit(
            json.dumps({"packet_type": "request", "packet_name": "heartbeat"}).encode(
                "ascii"
            )
        )
        if len(address_errors) > 0:
            with self.db_lock:
                for addr in address_errors:
                    ip, _ = addr
                    self.db.insert_log("connection", {"ip": ip})

    def __connection(self, request, response):
        ip, _ = response.getpeername()
        with self.db_lock:
            self.db.insert_log("connection", {"ip": ip})

    def __disconnection(self, request, response):
        ip, _ = response.getpeername()
        with self.db_lock:
            self.db.insert_log("disconnection", {"ip": ip})


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
