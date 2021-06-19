from collections import Counter


class TicTacToe:
    def __init__(self, player, oponent) -> None:
        self.restart(player, oponent)

    def restart(self, player, oponent):
        self.board = self.__create_board()
        self.player = player
        self.oponent = oponent
        self.winner = None
        self.moves_count = 0

    def play(self, row, col):
        return self.__insert_move(row, col, self.player)

    def update_oponent_move(self, row, col):
        return self.__insert_move(row, col, self.oponent)

    def get_winner(self):
        return self.winner

    def main_player(self):
        return self.player

    def __create_board(self):
        return [["" for j in range(3)] for i in range(3)]

    def __get_main_diagonal(self):
        return [self.board[i][i] for i in range(len(self.board))]

    def __get_secondary_diagonal(self):
        return [self.board[i][len(self.board) - i - 1] for i in range(len(self.board))]

    def __check_for_winner(self, counter):
        highest_score = next(iter(counter.most_common(1)), None)
        if highest_score and highest_score[0] in (self.player, self.oponent):
            if highest_score[1] == 3:
                return highest_score[0]

        return None

    def __insert_move(self, row, col, player):
        if row not in range(1, 4) or col not in range(1, 4):
            return "invalid"

        row, col = row - 1, col - 1

        if not self.winner and self.moves_count < 9 and not self.board[row][col]:
            self.moves_count += 1
            self.board[row][col] = player
        else:
            return "invalid"

        # Check for winner in main diagonal
        if row == col:
            main_diagonal = Counter(self.__get_main_diagonal())
            if winner := self.__check_for_winner(main_diagonal):
                self.winner = winner
                return winner

        # Check for winner in secondary diagonal
        if (row, col) in [(1, 1), (2, 0), (0, 2)]:
            secondary_diagonal = Counter(self.__get_secondary_diagonal())
            if winner := self.__check_for_winner(secondary_diagonal):
                self.winner = winner
                return winner

        # Check for winner in rows and columns from (row, col)
        n = len(self.board)
        _column = Counter()
        _row = Counter()

        for i in range(n):
            _column.update(self.board[row][i % n])
            _row.update(self.board[i % n][col])

        if winner := self.__check_for_winner(_column):
            self.winner = winner
            return winner
        if winner := self.__check_for_winner(_row):
            self.winner = winner
            return winner

        # Check for tie
        if self.moves_count == 9:
            self.winner = "tie"
            return self.winner

    def __str__(self):
        n = len(self.board)
        row = "{}    {:<2} |  {:<2} |  {:<2}\n"
        sep = "    ---------------\n"
        string = "     {:<2}    {:<2}    {:<2}\n\n".format(1, 2, 3)

        for i in range(n):
            string += row.format(i + 1, *[val for val in self.board[i]])
            string += sep if i < n - 1 else ""

        return string
