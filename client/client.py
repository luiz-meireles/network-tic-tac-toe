from socket import create_connection
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from src.state.user import UserStateMachine
from connection import ClientConnectionHandler, ServerEventHandler
from tabulate import tabulate
import argparse
import json


class Client:
    def __init__(self, args):
        self.ip_address = args.ip_address
        self.default_port = args.port
        self.tls_port = args.tls_port
        self.tls_server_hostname = "server-ep2-mac352"
        self.peer_port = args.listen_port

        self.user_state = UserStateMachine()
        self.username = ""
        self.default_connection = ClientConnectionHandler(
            self.ip_address, self.default_port, bufflen=1024
        )

        self.secure_connection = ClientConnectionHandler(
            self.ip_address,
            self.tls_port,
            bufflen=1024,
            keep_alive=False,
            tls=True,
            tls_cert="src/server_ssl/server.crt",
            server_hostname=self.tls_server_hostname,
        )

        self.default_connection.on("heartbeat", self.__heartbeat)

        self.p2p_server = ServerEventHandler("localhost", self.peer_port, 1024)
        self.p2p_server.on("invitation", self.__invitation)

    def run(self):
        command = input("JogoDaVelha> ")

        while command != "exit":
            self.__handle_command(command)
            command = input("JogoDaVelha> ")

    def __handle_command(self, command_line):
        commands = {
            "adduser": self.__add_user,
            "login": self.__login,
            "passwd": self.__passwd,
            "list": self.__players,
            "leaders": self.__leaders,
            "logout": self.__logout,
        }

        command, *params = command_line.split(" ")
        commands.get(command, lambda _: _)(params)

    def __add_user(self, params):
        if len(params) < 2:
            print("argumentos insuficientes")
            return
        elif len(params) > 2:
            print(
                f"adduser necessita de 2 argumentos, no entanto, {len(params)} foram passados"
            )
            return

        response = self.secure_connection.request(
            {
                "packet_type": "request",
                "packet_name": "adduser",
                "username": params[0],
                "password": params[1],
            },
        )

        if response and response.get("status") == "OK":
            pass

    def __login(self, params):
        # TODO: don't let login twice, improve user output message.
        if len(params) < 2:
            print("argumentos insuficientes")
            return
        elif len(params) > 2:
            print(
                f"adduser necessita de 2 argumentos, no entanto, {len(params)} foram passados"
            )
            return

        response = self.secure_connection.request(
            {
                "packet_type": "request",
                "packet_name": "login",
                "username": params[0],
                "password": params[1],
            }
        )

        if response.get("status") == "OK":
            self.username = params[0]
            self.__login_callback()
        else:
            print(response)

    def __login_callback(self):
        payload = {
            "packet_type": "request",
            "packet_name": "new_user_connection",
            "username": self.username,
            "peer_port": self.peer_port,
        }

        response = self.default_connection.request(payload)

        print(response)

    def __passwd(self, params):
        response = self.secure_connection.request(
            {
                "packet_type": "request",
                "packet_name": "password_change",
                "username": self.username,
                "current_password": params[0],
                "new_password": params[1],
            }
        )

        if response.get("status") == "OK":
            print("Password changed")

    def __new_game(self, params):
        pass

    def __players(self, params):
        response = self.default_connection.request(
            {
                "packet_type": "request",
                "packet_name": "list_players",
            }
        )

        print("USUÁRIOS ONLINE")

        for user in response.get("players"):
            print(user)

    def __leaders(self, params):
        response = self.default_connection.request(
            {
                "packet_type": "request",
                "packet_name": "leaderboard",
            }
        )

        print(
            "{:<12} {:<12} {:<12} {:<12} {:<12} {:<12}".format(
                "POSIÇÃO", "USUÁRIO", "VITÓRIAS", "EMPATES", "DERROTAS", "PONTUAÇÃO"
            )
        )

        for index, user in enumerate(response.get("leaderboard")):
            print(
                "{:<12} {:<12} {:<12} {:<12} {:<12} {:<12}".format(
                    index + 1,
                    user.get("username"),
                    user.get("wins"),
                    user.get("ties"),
                    user.get("loses"),
                    user.get("points"),
                )
            )

    def __logout(self, params):
        response = self.default_connection.request(
            {
                "packet_type": "request",
                "packet_name": "logout",
                "username": self.username,
            }
        )

        print(response)

    def __invitation(self):
        pass

    def __heartbeat(self, request, response):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Execute a client for a tic tac toe game"
    )
    parser.add_argument("-ip", "--ip-address", type=str, help="server ip address")
    parser.add_argument(
        "-lp",
        "--listen-port",
        type=int,
        help="client listener port for P2P connections",
    )
    parser.add_argument("-p", "--port", type=int, help="server port")
    parser.add_argument("-tlsp", "--tls-port", type=int, help="secure server port")

    args = parser.parse_args()

    client = Client(args)
    client.run()


if __name__ == "__main__":
    main()
