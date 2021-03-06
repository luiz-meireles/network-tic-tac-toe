from random import randint
from socket import socket, AF_INET, SOCK_DGRAM
from src.connection import (
    connection_except,
    response_wrapper,
    ClientConnectionHandler,
    P2PServerEventHandler,
)
from src.state.user import UserStateMachine
from src.input_read import InputRead
from src.game import TicTacToe

import sys
import os
import argparse
import json
import signal


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

        _socket = socket(AF_INET, SOCK_DGRAM)
        _socket.connect(("8.8.8.8", 1))

        self.client_ip_address = _socket.getsockname()[0]

        self.p2p_server = P2PServerEventHandler(
            self.client_ip_address, self.listen_port
        )

        self.p2p_server.on("invitation", self.__handle_invitation)
        self.p2p_server.on("game_init", self.__handle_game_init)
        self.p2p_server.on("game_move", self.__handle_game_move)
        self.p2p_server.on("game_end", self.__handle_game_end)
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
            "end": {
                "callback": self.__end_game,
                "state": [
                    self.user_state.playing_game,
                    self.user_state.waiting_game_instruction,
                ],
            },
            "logout": {"callback": self.__logout, "state": [self.user_state.logged]},
            "exit": {
                "callback": self.__exit_client,
                "state": [self.user_state.logged_out, self.user_state.logged],
            },
        }

        self.game = None
        self.p2p_connection = None

        signal.signal(signal.SIGINT, self.__handle_signal)

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
                print("Comando inv??lido.")
            elif (
                self.user_state.current_state
                == self.user_state.waiting_game_instruction
            ):
                print(
                    "Voc?? est?? no meio de uma partida, esperando pelo movimento do oponente."
                )
            else:
                print("N??o foi poss??vel executar o comando no momento.")

    def __add_user(self, params):
        if len(params) != 2:
            print(
                f"adduser necessita de 2 argumentos, no entanto, {len(params)} foram passados"
            )
            return

        with connection_except():
            response = self.secure_connection.request(
                "adduser",
                {
                    "username": params[0],
                    "password": params[1],
                },
            )

        if response and response.get("status") == "OK":
            print("Usu??rio adicionado com sucesso.")
        else:
            print("Nome de usu??rio indispon??vel, tente outro.")

    def __login(self, params):
        if len(params) != 2:
            print(
                f"login necessita de 2 argumentos, no entanto, {len(params)} foram passados."
            )
            return
        with connection_except():
            response = self.secure_connection.request(
                "login",
                {
                    "username": params[0],
                    "password": params[1],
                },
            )

        if response.get("status") == "OK":
            self.username = params[0]
            self.user_state.login_success()
            self.__login_callback()
        else:
            print("Falha ao efetuar login. Verifique suas credenciais.")

    def __login_callback(self):
        with connection_except():
            self.default_connection.request(
                "new_user_connection",
                {
                    "username": self.username,
                    "listen_port": self.listen_port,
                },
            )

        print("Login efetuado com sucesso.")

    def __passwd(self, params):
        if len(params) != 2:
            print(
                f"passwd necessita de 2 argumentos, no entanto, {len(params)} foram passados."
            )
            return
        with connection_except():
            response = self.secure_connection.request(
                "password_change",
                {
                    "username": self.username,
                    "current_password": params[0],
                    "new_password": params[1],
                },
            )

        if response.get("status") == "OK":
            print("Senha atualizada com sucesso.")
        else:
            print("Senha atual incorreta.")

    def __players(self, params):
        with connection_except():
            response = self.default_connection.request("list_players")
        self.online_users = response.get("players")

        print("\nUSU??RIOS ONLINE\n")
        for user, data in self.online_users.items():
            if user != self.username:
                print(
                    f"  {user} - {'ACEITANDO PARTIDA' if data[2] == 'IDLE' else 'INDISPON??VEL'}"
                )
        print()

    def __leaders(self, params):
        with connection_except():
            response = self.default_connection.request("leaderboard")

        print(
            "{:<12} {:<12} {:<12} {:<12} {:<12} {:<12}".format(
                "POSI????O", "USU??RIO", "VIT??RIAS", "EMPATES", "DERROTAS", "PONTUA????O"
            )
        )

        for index, user in enumerate(response.get("leaderboard")):
            if user != self.username:
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

        oponent_user = params[0]
        oponent_data = self.online_users.get(oponent_user)

        if oponent_user == self.username:
            print("Voc?? n??o pode jogar uma partida contra voc?? mesmo :(")
            return

        if oponent_data:
            target_user_addr, target_user_port, target_user_state = oponent_data

            if target_user_state != "IDLE":
                print(
                    f"{oponent_user} se encontra indispon??vel no momento, por favor escolha outro jogador."
                )

                return

            with connection_except():
                permission_response = self.default_connection.request(
                    "init_game_permission",
                    {
                        "users": [self.username, oponent_user],
                    },
                )

            if permission_response.get("status") != "OK":
                print(
                    "Houve algum problema, por favor use o comando 'list' novamente para buscar por jogadores dispon??veis."
                )

                return

            self.p2p_connection = ClientConnectionHandler(
                target_user_addr, target_user_port
            )
            self.p2p_connection.on("game_move", self.__handle_game_move)
            self.p2p_connection.on("game_end", self.__handle_game_end)

            with connection_except():
                response = self.p2p_connection.request(
                    "invitation",
                    {
                        "username": self.username,
                    },
                )

            with connection_except():
                self.default_connection.request(
                    "init_game",
                    {
                        "users": [self.username, oponent_user],
                        "invitation_status": response.get("status"),
                    },
                )

            if response.get("status") == "ACCEPT":
                self.user_state.game_init()
                self.game_controller = True
                self.oponent_user = oponent_user

                first_player = randint(0, 1)
                player_choice = None

                if first_player == 0:
                    player_choice = self.__player_choice()
                    current_choice = "O" if player_choice == "X" else "X"
                    self.game = TicTacToe(player_choice, current_choice)
                with connection_except():
                    response = self.p2p_connection.request(
                        "game_init",
                        {
                            "first_player": first_player,
                            "player_choice": player_choice,
                        },
                    )

                if first_player == 1:
                    player_choice = response.get("player_choice")
                    current_choice = "O" if player_choice == "X" else "X"
                    print(
                        f"O oponente foi sorteado como primeiro jogador, voc?? ser?? o jogador {current_choice}."
                    )
                    self.game = TicTacToe(current_choice, player_choice)
                    self.user_state.waiting()
            else:
                print(f"{params[0]} recusou o seu convite para um novo jogo.")
        else:
            print(
                "Por favor, verifique se o usu??rio escolhido est?? realmente online utilizando o comando 'list'."
            )

    def __player_choice(self):
        with self.input_non_blocking.block_input():
            print("\nVoc?? foi sorteado como primeiro jogador...")
            player = input(f"Qual jogador voc?? deseja? (X/O)\n")

            while player.lower() != "x" and player.lower() != "o":
                player = input(f"Qual jogador voc?? deseja? (X/O)\n")

        return player.upper()

    def __send(self, params):
        if len(params) != 2:
            print(
                f"send necessita de 2 argumentos, no entanto, {len(params)} foram passados."
            )
            return

        row, column = params

        if not row.isnumeric() or not column.isnumeric():
            print("send aceita apenas caracteres n??mericos entre 1 e 3.")
            return

        move_status = self.game.play(int(row), int(column))

        if not move_status or move_status != "invalid":
            print(self.game)
            print()
            self.user_state.waiting()

            if self.game_controller:
                with connection_except():
                    self.p2p_connection.request(
                        "game_move",
                        {
                            "move": [row, column],
                        },
                    )
            else:
                self.p2p_server.emit(
                    json.dumps(
                        {
                            "packet_type": "request",
                            "packet_name": "game_move",
                            "move": [row, column],
                        }
                    ).encode("ascii")
                )

            if move_status:
                self.user_state.ready()
                self.__finish_game(move_status)
        elif move_status == "invalid":
            print("Jogada inv??lida, por favor tente novamente.")

    def __finish_game(self, status):
        player_status = "win" if self.game.main_player() == status else "lose"

        if status == "tie":
            print("O jogo terminou em empate!")
        elif player_status == "win":
            print(f"Voc?? foi o vencedor do jogo!")
        else:
            print(f"Voc?? perdeu o jogo :(")

        print()

        if self.game_controller:
            winner = (
                "tie"
                if status == "tie"
                else self.username
                if player_status == "win"
                else self.oponent_user
            )

            with connection_except():
                self.default_connection.request(
                    "finish_game",
                    {
                        "users": [self.username, self.oponent_user],
                        "end_status": "GAME_END",
                        "winner": winner,
                    },
                )

        self.__clean_user_state()

    def __clean_user_state(self):
        if self.game_controller:
            self.p2p_connection.close()
            self.p2p_connection = None
            self.game_controller = None
        else:
            self.p2p_server.clear_connections()

        self.game = None
        self.oponent_user = None

        if self.user_state.current_state == self.user_state.waiting_game_instruction:
            self.user_state.ready()

        self.user_state.game_end()

    def __logout(self, params):
        with connection_except():
            self.default_connection.request(
                "logout",
                {
                    "username": self.username,
                },
            )
        self.user_state.log_off()

        print("Logout efetuado com sucesso.")

    def __end_game(self, params):
        with self.input_non_blocking.block_input():
            command = input(f"Voc?? realmente deseja sair da partida? S/N\n").strip()

            if command.lower() == "n":
                return

            if self.game_controller:
                with connection_except():
                    self.default_connection.request(
                        "finish_game",
                        {
                            "users": [self.username, self.oponent_user],
                            "end_status": "GAME_INTERRUPTED_BY_END",
                            "winner": "None",
                        },
                    )

                with connection_except():
                    self.p2p_connection.request("game_end")
            else:
                self.p2p_server.emit(
                    json.dumps(
                        {
                            "packet_type": "request",
                            "packet_name": "game_end",
                        }
                    ).encode("ascii")
                )

            self.__clean_user_state()

    def __exit_client(self, params):
        print("\n Fechando...")
        if self.user_state.current_state == self.user_state.logged:
            self.__logout(None)

        if self.p2p_connection:
            self.p2p_connection.close()

        self.p2p_server.stop_server()
        exit(0)

    @response_wrapper
    def __handle_invitation(self, request, response):
        with self.input_non_blocking.block_input():
            command = input(
                f"\nO usu??rio {request.username} est?? querendo iniciar um novo jogo, voc?? aceita a partida? S/N\n"
            ).strip()

            status = None

            if command.lower() == "s":
                status = "ACCEPT"
                self.oponent_user = request.username
            else:
                status = "REFUSED"

            response.send(
                "invitation",
                {
                    "status": status,
                },
            )

    @response_wrapper
    def __handle_game_init(self, request, response):
        with self.input_non_blocking.block_input():
            self.user_state.game_init()
            self.game_controller = False
            first_player = request.first_player
            player_choice = None

            if first_player == 0:
                player_choice = request.player_choice
                current_choice = "O" if player_choice == "X" else "X"
                print(
                    f"O oponente foi sorteado como primeiro jogador, voc?? ser?? o jogador {current_choice}."
                )
                self.game = TicTacToe(current_choice, player_choice)
                self.user_state.waiting()
            elif first_player == 1:
                player_choice = self.__player_choice()
                current_choice = "O" if player_choice == "X" else "X"
                self.game = TicTacToe(player_choice, current_choice)

            response.send("game_init", {"player_choice": player_choice})

    @response_wrapper
    def __handle_game_move(self, request, response):
        with self.input_non_blocking.block_input():
            if not self.game_controller:
                response.send(
                    "game_move",
                    {
                        "status": "OK",
                    },
                )

            row, col = request.move
            move_status = self.game.update_oponent_move(int(row), int(col))

            print(self.game)
            print()
            self.user_state.ready()

            if move_status:
                self.__finish_game(move_status)

    @response_wrapper
    def __handle_game_end(self, request, response):
        with self.input_non_blocking.block_input():
            if not self.game_controller:
                response.send(
                    "game_end",
                    {
                        "status": "OK",
                    },
                )
            else:
                with connection_except():
                    self.default_connection.request(
                        "finish_game",
                        {
                            "users": [self.username, self.oponent_user],
                            "end_status": "GAME_INTERRUPTED_BY_END",
                            "winner": "None",
                        },
                    )

            print("O oponente abandonou a partida.")
            print()
            self.__clean_user_state()

    def __handle_signal(self, signum, frame):
        self.input_non_blocking.close()
        self.input_non_blocking.join()

        self.__exit_client([])


def main():
    parser = argparse.ArgumentParser(
        description="Execute a client for a tic tac toe game"
    )

    parser.add_argument(
        "-ip", "--ip-address", type=str, help="server ip address, default is local ip"
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

    requiredNamed = parser.add_argument_group("required named arguments")
    requiredNamed.add_argument(
        "-lp",
        "--listen-port",
        type=int,
        help="client port for P2P connections",
        required=True,
    )

    args = parser.parse_args()

    if args.ip_address is None:
        _socket = socket(AF_INET, SOCK_DGRAM)
        _socket.connect(("8.8.8.8", 1))
        args.ip_address = _socket.getsockname()[0]

    client = Client(args)
    client.run()


if __name__ == "__main__":
    main()
