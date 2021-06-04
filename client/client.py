from socket import create_connection
from ssl import SSLContext, PROTOCOL_TLS_CLIENT
from src.state.user import UserMachine
import argparse
import json


class Client:
    def __init__(self, args):
        self.ip_address = args.ip_address
        self.default_port = args.port
        self.ssl_port = args.ssl_port
        self.ssl_server_hostname = 'server-ep2-mac352'
        self.init_ssl_context()
        self.user_state = UserMachine()
        self.username = ''
        self.server_connection = None

    def init_ssl_context(self):
        self.ssl_context = SSLContext(PROTOCOL_TLS_CLIENT)
        self.ssl_context.load_verify_locations('src/server_ssl/server.crt')

    def run(self):
        command = input('JogoDaVelha> ')

        while command != 'exit':
            self.handle_command(command)
            command = input('JogoDaVelha> ')

    def handle_command(self, command_line):
        commands = {'adduser': self.add_user, 'login': self.login}

        command, *params = command_line.split(' ')
        commands.get(command, lambda _: _)(params)

    def add_user(self, params):
        if len(params) < 2:
            print('argumentos insuficientes')
            return
        elif len(params) > 2:
            print(
                f'adduser necessita de 2 argumentos, no entanto, {len(params)} foram passados')
            return

        with create_connection((self.ip_address, self.ssl_port)) as client:
            with self.ssl_context.wrap_socket(client, server_hostname=self.ssl_server_hostname) as tls:
                print(f'Using {tls.version()}\n')
                test = json.dumps(
                    {"type": "adduser", 'username': params[0], 'password': params[1]}, ensure_ascii=True).encode('ascii')
                tls.sendall(test)

                data = tls.recv(1024)
                print(f'Server says: {data}')

    def login(self, params):
        if len(params) < 2:
            print('argumentos insuficientes')
            return
        elif len(params) > 2:
            print(
                f'adduser necessita de 2 argumentos, no entanto, {len(params)} foram passados')
            return

        with create_connection((self.ip_address, self.ssl_port)) as client:
            with self.ssl_context.wrap_socket(client, server_hostname=self.ssl_server_hostname) as tls:
                print(f'Using {tls.version()}\n')
                payload = json.dumps(
                    {"type": "login", 'username': params[0], 'password': params[1]}, ensure_ascii=True).encode('ascii')
                tls.sendall(payload)

                data = tls.recv(1024)
                response = json.loads(data)

                if response and response.get("status") == "OK":
                    self.username = params[0]
                    self.login_callback()

    def login_callback(self):
        self.server_connection = create_connection(
            (self.ip_address, self.default_port))
        payload = json.dumps(
            {"type": "new_user_connection", "username": self.username}, ensure_ascii=True).encode("ascii")
        self.server_connection.sendall(payload)
        data = self.server_connection.recv(1024)
        print(f'Server says: {data}')


def main():
    parser = argparse.ArgumentParser(
        description='Execute a client for a tic tac toe game')
    parser.add_argument('--ip-address', type=str, help='server ip address')
    parser.add_argument('--port', type=int, help='server port')
    parser.add_argument('--ssl-port', type=int, help='secure server port')

    args = parser.parse_args()

    client = Client(args)
    client.run()


if __name__ == '__main__':
    main()
