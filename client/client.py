from socket import create_connection
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from src.state.user import UserMachine
from connection import ClientConnectionHandler, ServerEventHandler
import argparse
import json


class Client:
    def __init__(self, args):
        self.ip_address = args.ip_address
        self.default_port = args.port
        self.tls_port = args.tls_port
        self.tls_server_hostname = "server-ep2-mac352"
        self.pear_port = args.listen_port

        self.user_state = UserMachine()
        self.username = ""
        self.default_connection = ClientConnectionHandler(
            self.ip_address, self.default_port, 1024
        )
        self.secure_connection = ClientConnectionHandler(
            self.ip_address,
            self.tls_port,
            1024,
            "src/server_tls/server.crt",
            self.tls_server_hostname,
        )

        self.p2p_server = ServerEventHandler("localhost", self.pear_port, 1024)
        self.p2p_server.on("invitation", self.handle_invitation)

    def handle_invitation(self):
        pass

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
            json.dumps(
                {"type": "adduser", "username": params[0], "password": params[1]},
                ensure_ascii=True,
            ).encode("ascii"),
            tls=True,
        )
        response = json.loads(response)

        if response and response.get("status") == "OK":
            pass

    def __login(self, params):
        if len(params) < 2:
            print("argumentos insuficientes")
            return
        elif len(params) > 2:
            print(
                f"adduser necessita de 2 argumentos, no entanto, {len(params)} foram passados"
            )
            return

        response = self.secure_connection.request(
            json.dumps(
                {"type": "login", "username": params[0], "password": params[1]},
                ensure_ascii=True,
            ).encode("ascii"),
            tls=True,
        )
        response = json.loads(response)

        if response and response.get("status") == "OK":
            self.username = params[0]
            self.__login_callback()

    def __login_callback(self):
        payload = json.dumps(
            {
                "type": "new_user_connection",
                "username": self.username,
                "pear_port": self.pear_port,
            },
            ensure_ascii=True,
        ).encode("ascii")

        response = self.default_connection.request(payload)

        print(f"Server says: {response}")

    def __passwd(self, params):
        response = self.secure_connection.request(
            json.dumps(
                {
                    "type": "password_change",
                    "username": self.username,
                    "current_password": params[0],
                    "new_password": params[1],
                }
            )
        )
        response = response and json.loads(response)
        if response.get("status") == "OK":
            print("Password changed")

    def new_game(self, params):
        pass

    def get_leaders(self, params):
        pass

    def get_players(self, params):
        response = self.secure_connection.request(
            json.dumps(
                {
                    "type": "list_players",
                }
            )
        )

        response = response and json.loads(response)
        print(response)


def main():
    parser = argparse.ArgumentParser(
        description="Execute a client for a tic tac toe game"
    )
    parser.add_argument("--ip-address", type=str, help="server ip address")
    parser.add_argument(
        "--listen-port", type=int, help="client listener port for P2P connections"
    )
    parser.add_argument("--port", type=int, help="server port")
    parser.add_argument("--tls-port", type=int, help="secure server port")

    args = parser.parse_args()

    client = Client(args)
    client.run()


if __name__ == "__main__":
    main()
