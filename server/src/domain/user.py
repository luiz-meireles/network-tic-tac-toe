class User:
    def __init__(self, username, password, peer_server=None, online=True) -> None:
        self.username = username
        self.peer_server = peer_server
        self.online = online
        self.password = password
