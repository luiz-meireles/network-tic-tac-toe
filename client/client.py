from socket import create_connection
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from connection import ClientConnectionHandler, ServerEventHandler
from src.state.user import UserStateMachine
from src.input_read import InputRead
from threading import Event

import argparse
import json


class Client:
    def __init__(self, args):
        self.ip_address = args.ip_address
        self.default_port = args.port
        self.tls_port = args.tls_port
        self.tls_server_hostname = "server-ep2-mac352"
        self.listen_port = args.listen_port

        self.user_state = UserStateMachine()
        self.username = ""
        self.default_connection = ClientConnectionHandler(
            self.ip_address, self.default_port
        )

        self.secure_connection = ClientConnectionHandler(
            self.ip_address,
            self.tls_port,
            keep_alive=False,
            tls=True,
            tls_cert="src/server_ssl/server.crt",
            server_hostname=self.tls_server_hostname,
        )

        self.default_connection.on("heartbeat", self.__heartbeat)

        self.p2p_server = ServerEventHandler("127.0.0.1", self.listen_port)
        self.p2p_server.on("invitation", self.__invitation)
        self.p2p_server.start()

        self.online_users = {}

        self.command_read_event = Event()
        self.request_event = Event()
        self.request_event.set()

    def run(self):
        self.input_non_blocking = InputRead(
            self.__handle_command, self.command_read_event, self.request_event
        )
        self.input_non_blocking.run()

    def __handle_command(self, command_line):
        commands = {
            "adduser": self.__add_user,
            "login": self.__login,
            "passwd": self.__passwd,
            "list": self.__players,
            "leaders": self.__leaders,
            "begin": self.__new_game,
            "logout": self.__logout,
        }

        command, *params = command_line.split(" ")
        commands.get(command, lambda _: _)(params)
        self.command_read_event.set()

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
            "listen_port": self.listen_port,
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

    def __players(self, params):
        response = self.default_connection.request(
            {
                "packet_type": "request",
                "packet_name": "list_players",
            }
        )

        self.online_users = response.get("players")

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

    def __new_game(self, params):
        user = self.online_users.get(params[0])

        if user:
            target_user_addr, target_user_port = user
            self.p2p_connection = ClientConnectionHandler(
                target_user_addr, target_user_port
            )

            response = self.p2p_connection.request(
                {
                    "packet_type": "request",
                    "packet_name": "invitation",
                    "username": self.username,
                }
            )

            if response.get("status") == "OK":
                print("dahora")
            else:
                print("falhou")
        else:
            print(
                "Por favor, verifique se o usuário escolhido está realmente online utilizando o comando 'list'."
            )

    def __invitation(self, request, response):
        self.command_read_event.clear()
        self.input_non_blocking.pause_read()

        command = input(
            f"{request.get('username')} está querendo iniciar um novo jogo, você aceita a partida? S/N\n"
        )

        if command == "S":
            payload = {
                "packet_type": "response",
                "packet_name": "invitation",
                "request_id": request.get("request_id"),
                "status": "OK",
            }
        else:
            payload = {
                "packet_type": "response",
                "packet_name": "invitation",
                "request_id": request.get("request_id"),
                "status": "FAIL",
            }

        response.sendall(json.dumps(payload).encode("ascii"))
        print("bla")

        self.command_read_event.set()

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
