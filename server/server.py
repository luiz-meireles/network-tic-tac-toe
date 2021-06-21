from threading import Thread, Lock, Timer
from socket import socket, AF_INET, SOCK_DGRAM
from src.auth import hash_password, check_password
from src.domain.user import User
from src.db import Storage
from src.connection import ServerEventHandler, set_interval, response_wrapper

import sqlite3
import argparse
import json
import signal


class Server:
    def __init__(self, args):
        self.default_port = args.port
        self.tls_port = args.tls_port
        self.db = Storage()
        self.logged_users = {}
        self.db_lock = Lock()
        self.logged_users_lock = Lock()
        self.ip_address = args.ip_address

    def run(self):

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

        print(
            f"Servidor está escutando no ip {self.ip_address} nas portas {self.default_port} e {self.tls_port} (para conexões TLS)"
        )

        set_interval(self.__heartbeat, 60)

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
        self.connection_handler.on("init_game_permission", self.__init_game_permission)
        self.connection_handler.on("init_game", self.__init_game)
        self.connection_handler.on("finish_game", self.__finish_game)
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

            with self.db_lock:
                self.db.change_password(username, hashed_password)

            response.send(
                "password_change",
                {
                    "status": "OK",
                },
            )
        else:
            response.send(
                "password_change",
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
            self.logged_users[username] = [addr[0], client_listen_port, "IDLE"]

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
    def __init_game_permission(self, request, response):
        player_one, player_two = request.users

        with self.logged_users_lock:
            player_one_data = self.logged_users.get(player_one)
            player_two_data = self.logged_users.get(player_two)

            if (
                player_one_data
                and player_one_data[2] == "IDLE"
                and player_two_data
                and player_two_data[2] == "IDLE"
            ):
                response.send("init_game", {"status": "OK"})
                self.logged_users[player_one][2] = "WAITING"
                self.logged_users[player_two][2] = "WAITING"
            else:
                response.send("init_game", {"status": "FAIL"})

    @response_wrapper
    def __init_game(self, request, response):
        player_one, player_two = request.users

        with self.logged_users_lock:
            if request.invitation_status == "ACCEPT":
                self.logged_users[player_one][2] = "PLAYING"
                self.logged_users[player_two][2] = "PLAYING"

                with self.db_lock:
                    self.db.insert_log(
                        "new_game",
                        {
                            "ip_player_one": self.logged_users[player_one][0],
                            "username_player_one": player_one,
                            "ip_player_two": self.logged_users[player_two][0],
                            "username_player_two": player_two,
                        },
                    )
            elif request.invitation_status == "REFUSED":
                self.logged_users[player_one][2] = "IDLE"
                self.logged_users[player_two][2] = "IDLE"

        response.send("init_game", {"status": "OK"})

    @response_wrapper
    def __finish_game(self, request, response):
        player_one, player_two = request.users
        winner = request.winner

        with self.db_lock:
            self.db.update_user_status(
                player_one, self.__check_game_status(player_one, winner)
            )
            self.db.update_user_status(
                player_two, self.__check_game_status(player_two, winner)
            )

        with self.logged_users_lock:
            with self.db_lock:
                self.logged_users[player_one][2] = "IDLE"
                self.logged_users[player_two][2] = "IDLE"
                self.db.insert_log(
                    "end_game",
                    {
                        "end_status": request.end_status,
                        "winner": winner,
                        "ip_player_one": self.logged_users[player_one][0],
                        "username_player_one": player_one,
                        "ip_player_two": self.logged_users[player_two][0],
                        "username_player_two": player_two,
                    },
                )

        response.send("finish_game", {"status": "OK"})

    def __check_game_status(self, player_name, winner):
        player_status = None

        if winner == "tie":
            player_status = "tie"
        elif winner == player_name:
            player_status = "win"
        else:
            player_status = "lose"

        return player_status

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

    parser.add_argument(
        "-ip",
        "--ip-address",
        help="ip for the server, default as the local ip",
    )

    parser.add_argument(
        "-p", "--port", type=int, help="server port, default is 8080", default=8080
    )
    parser.add_argument(
        "-tlsp",
        "--tls-port",
        type=int,
        help="secure server port, default is 8081",
        default=8081,
    )

    args = parser.parse_args()

    if args.ip_address is None:
        _socket = socket(AF_INET, SOCK_DGRAM)
        _socket.connect(("8.8.8.8", 1))
        args.ip_address = _socket.getsockname()[0]

    server = Server(args)
    server.run()


if __name__ == "__main__":
    main()
