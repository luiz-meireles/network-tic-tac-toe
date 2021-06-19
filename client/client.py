from socket import create_connection
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from src.connection import ClientConnectionHandler, P2PServerEventHandler
from src.state.user import UserStateMachine
from src.input_read import InputRead
from src.game import TicTacToe

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

        # self.default_connection.on("heartbeat", self.__heartbeat)

        self.p2p_server = P2PServerEventHandler("127.0.0.1", self.listen_port)
        self.p2p_server.on("invitation", self.__handle_invitation)
        self.p2p_server.on("game_move", self.__handle_game_move)
        self.p2p_server.on("finish_game", self.__handle_finish_game)
        self.p2p_server.start()

        self.online_users = {}

        self.commands = {
            "adduser": {
                "callback": self.__add_user,
                "state": [self.user_state.logged_out],
            },
            "login": {"callback": self.__login, "state": [self.user_state.logged_out]},
            "passwd": {
                "callback": self.__passwd,
                "state": [self.user_state.logged_out, self.user_state.logged],
            },
            "list": {"callback": self.__players, "state": [self.user_state.logged]},
            "leaders": {"callback": self.__leaders, "state": [self.user_state.logged]},
            "begin": {"callback": self.__new_game, "state": [self.user_state.logged]},
            "send": {"callback": self.__send, "state": [self.user_state.playing_game]},
            "logout": {"callback": self.__logout, "state": [self.user_state.logged]},
        }

        self.game = None

    def run(self):
        self.input_non_blocking = InputRead(self.__handle_command)

    def __handle_command(self, command_line):
        command, *params = command_line.split(" ")
        action_handler = self.commands.get(command, None)

        if action_handler and self.user_state.current_state in action_handler.get(
            "state"
        ):
            action_handler.get("callback", lambda _: _)(params)
        else:
            if not action_handler:
                print("Comando inválido.")
            else:
                print("Não foi possível executar o comando no momento.")

    def __add_user(self, params):
        if len(params) != 2:
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
        if len(params) != 2:
            print(
                f"login necessita de 2 argumentos, no entanto, {len(params)} foram passados."
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
            self.user_state.login_success()
            self.__login_callback()
        else:
            self.user_state.login_fail()
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
        if len(params) != 2:
            print(
                f"passwd necessita de 2 argumentos, no entanto, {len(params)} foram passados."
            )
            return

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

    def __new_game(self, params):
        if len(params) != 1:
            print(
                f"begin necessita de 1 argumentos, no entanto, {len(params)} foram passados."
            )
            return

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

            if response.get("status") == "ACCEPT":
                self.user_state.game_init()

                self.input_non_blocking.init_request()
                player = input(f"Escolha qual jogador você deseja? (X/O)\n")
                self.input_non_blocking.end_request()

                self.game = TicTacToe(player, "O" if player == "X" else "X")
            else:
                print(f"{params[0]} recusou o seu convite para um novo jogo.")
        else:
            print(
                "Por favor, verifique se o usuário escolhido está realmente online utilizando o comando 'list'."
            )

    def __send(self, params):
        if len(params) != 2:
            print(
                f"begin necessita de 2 argumentos, no entanto, {len(params)} foram passados."
            )
            return

        row, column = params

        if self.game:
            status = self.game.play(int(row), int(column))
            self.__handle_game_status(status)
            print(status)

            if not status:
                self.user_state.waiting()
                status = self.__handle_oponent_move()
                self.user_state.ready()
                self.__handle_game_status(status)
            elif status == "invalid":
                print(
                    "Posição inválida, por favor tente com outros valores de linha/coluna."
                )
        else:
            payload = {
                "packet_type": "response",
                "packet_name": "game_move",
                "request_id": self.last_game_request.get("request_id"),
                "move": [row, column],
                "status": "OK",
            }

            self.p2p_server.emit(json.dumps(payload).encode("ascii"))

            self.user_state.waiting()
            self.input_non_blocking.init_request()
            print("Aguardando movimento do oponente...")

    def __handle_game_status(self, status):
        if status and status != "invalid":
            self.__finish_game(status)

    def __handle_oponent_move(self):
        response = self.p2p_connection.request(
            {
                "packet_type": "request",
                "packet_name": "game_move",
                "board": self.game.get_board(),
            }
        )

        if response.get("status") == "OK":
            move = response.get("move")
            status = self.game.update_oponent_move(int(move[0]), int(move[1]))

            if status == "invalid" and not self.game.get_winner():
                self.__handle_oponent_move()
            else:
                TicTacToe.print_board(self.game.get_board())
                return status

    def __finish_game(self, status):
        self.p2p_connection.request(
            {
                "packet_type": "request",
                "packet_name": "finish_game",
                "board": self.game.get_board(),
                "winner": status,
            }
        )

        TicTacToe.print_board(self.game.get_board())
        self.__finish_game_callback(status)
        self.game = None

    def __finish_game_callback(self, status):
        if status == "tie":
            print("O jogo terminou em empate! :(")
        else:
            print(f"O vencedor do jogo foi o jogador {status}")

        if self.user_state.current_state == self.user_state.waiting_game_instruction:
            self.user_state.ready()
        self.user_state.game_end()

    def __logout(self, params):
        response = self.default_connection.request(
            {
                "packet_type": "request",
                "packet_name": "logout",
                "username": self.username,
            }
        )
        self.user_state.log_off()

        print(response)

    def __handle_invitation(self, request, response):
        self.input_non_blocking.init_request()

        command = input(
            f"{request.get('username')} está querendo iniciar um novo jogo, você aceita a partida? S/N\n"
        )

        if command == "S":
            payload = {
                "packet_type": "response",
                "packet_name": "invitation",
                "request_id": request.get("request_id"),
                "status": "ACCEPT",
            }

            self.user_state.game_init()
            self.user_state.waiting()
        else:
            payload = {
                "packet_type": "response",
                "packet_name": "invitation",
                "request_id": request.get("request_id"),
                "status": "REFUSED",
            }
            self.input_non_blocking.end_request()

        response.sendall(json.dumps(payload).encode("ascii"))

    def __handle_game_move(self, request, response):
        self.user_state.ready()
        self.last_game_request = request
        TicTacToe.print_board(request.get("board"))
        self.input_non_blocking.end_request()

    def __handle_finish_game(self, request, response):
        payload = {
            "packet_type": "response",
            "packet_name": "finish_game",
            "request_id": request.get("request_id"),
            "status": "OK",
        }
        TicTacToe.print_board(request.get("board"))
        status = request.get("winner")

        self.__finish_game_callback(status)

        response.sendall(json.dumps(payload).encode("ascii"))
        self.input_non_blocking.end_request()


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
