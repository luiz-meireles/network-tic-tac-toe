# TicTacToe Online Game
A server and client implementation of a tictactoe game

## How to execute:

cd server/ && python3 server.py [-h] [-ip IP_ADDRESS] [-p PORT] [-tlsp TLS_PORT]

cd client/ && python3 client.py [-h] [-ip SERVER_IP_ADDRESS] [-p PORT] [-tlsp TLS_PORT] -lp P2P_LISTEN_PORT 

**Example**

`cd server/ && python3 server.py`
  - run server on local host ip, listening to ports 8080 and 8081 (TLS connections)

`cd client/ && python3 client.py -lp 9000`
  - execute a client which send requests to server on local host ip and ports 8080 and 8081. Moreover, listen to p2p connections on port 9000.

## Client commands

- adduser <user> <password>
- passwd <current password> <new password>
- login <user> <password>
- leaders: player ranking
- list: list all users connected to the server
- begin <oponent>: invite a player to a new tictactoe game
- send <row> <column>: send a game move
- end: leave a game before it finishs
- logout
- exit
