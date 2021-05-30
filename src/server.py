from socket import socket, AF_INET, SOCK_STREAM
from ssl import SSLContext, PROTOCOL_TLS_SERVER
from threading import Thread
import argparse
import sqlite3
import json


class Server:
    def __init__(self, args):
        self.ip_address = "127.0.0.1"
        self.default_port = args.port
        self.ssl_port = args.ssl_port

    def run(self):
        ssl_listener_th = Thread(target=self.ssl_listener)

        ssl_listener_th.start()
        ssl_listener_th.join()

    def ssl_listener(self):
        context = SSLContext(PROTOCOL_TLS_SERVER)
        context.load_cert_chain("server_ssl/server.crt", "server_ssl/server.key")

        with socket(AF_INET, SOCK_STREAM) as server:
            server.bind((self.ip_address, self.ssl_port))
            server.listen(1)

            with context.wrap_socket(server, server_side=True) as tls:
                connection, address = tls.accept()
                print(f"Connected by {address}\n")

                data = connection.recv(1024)
                print(f"Client Says: {json.loads(data)}")

                connection.sendall(b"You're welcome")


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
