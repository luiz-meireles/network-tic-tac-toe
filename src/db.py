import sqlite3
from domain.user import User


class ConstraintError(Exception):
    pass


class Storage:
    def __init__(self):
        # self.db = "./tictactoe.db"
        self._migration = "./migration.sql"
        self._connection = sqlite3.connect(
            "tictactoe.db", check_same_thread=False)
        self.run_migrations()

    def run_migrations(self):
        with open(self._migration, "r") as migrations:
            cursor = self._connection.cursor()
            cursor.execute(migrations.read())
            self._connection.commit()
            cursor.close()

    def insert_user(self, user):
        cursor = self._connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (user.username, user.password),
        )
        self._connection.commit()
        cursor.close()

    def get_user(self, username):
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT username, password FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        if not user:
            return None

        _, password = user
        return User(username, password)


if __name__ == "__main__":
    pass
    # storage = Storage()
    # storage.run_migrations()

    # user1 = User("tavela", "euamomelao")
    # user2 = User("tom", "odeiocaqui")

    # storage.insert_user(user1)
    # storage.insert_user(user2)

    # print(storage.get_user("tavela"))
