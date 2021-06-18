from collections import Counter


class TicTacToe:
    def __init__(self, player, oponent) -> None:
        self.restart(player, oponent)

    def play(self, lin, col):
        return self.__insert_move(lin, col, self.player)

    def update_oponent_move(self, lin, col):
        return self.__insert_move(lin, col, self.oponent)

    def restart(self, player, oponent):
        self.board = self.__create_board()
        self.player = player
        self.oponent = oponent
        self.winner = None
        self.moves_count = 0

    def __create_board(self):
        return [[None for j in range(3)] for i in range(3)]

    def update_oponent_move(self, lin, col):
        return self.__insert_move(lin, col, self.oponent)

    def __get_main_diagonal(self):
        return [self.board[i][i] for i in range(len(self.board))]

    def __get_secondary_diagonal(self):
        return [self.board[i][len(self.board) - i - 1] for i in range(len(self.board))]

    def __check_for_winner(self, counter):
        highest_score = next(iter(counter.most_common(1)), None)
        if highest_score and highest_score[1] == 3:
            return highest_score[0]
        return None

    def __insert_move(self, lin, col, player):

        if not self.winner and self.moves_count < 9 and not self.board[lin][col]:
            self.moves_count += 1
            self.board[lin][col] = player
        else:
            return "invalid"

        # Check for winner in main diagonal
        if lin == col:
            main_diagonal = Counter(self.__get_main_diagonal())
            if winner := self.__check_for_winner(main_diagonal):
                self.winner = winner
                return winner

        # Check for winner in secondary diagonal
        if lin == 2 and col == 0 or lin == 0 and col == 2:
            secondary_diagonal = Counter(self.__get_secondary_diagonal())
            if winner := self.__check_for_winner(secondary_diagonal):
                self.winner = winner
                return winner

        # Check for winner in rows and columns from (lin, col)
        n = len(self.board)
        column = Counter()
        row = Counter()

        for i in range(n):
            column.update(self.board[lin][i % n])
            row.update(self.board[i % n][col])

        if winner := self.__check_for_winner(column):
            self.winner = winner
            return winner
        if winner := self.__check_for_winner(row):
            self.winner = winner
            return winner

        # Check for tie
        if self.moves_count == 9:
            self.status = "tie"
            return "tie"
