from os import curdir
from typing import Counter
from datetime import datetime
from src.domain.user import User
import sqlite3
import json


class ConstraintError(Exception):
    pass


class Storage:
    def __init__(self):
        self._migration = "./src/migration.sql"
        self._connection = sqlite3.connect(
            "./src/tictactoe.db", check_same_thread=False
        )
        self.run_migrations()

    def run_migrations(self):
        with open(self._migration, "r") as migrations:
            cursor = self._connection.cursor()
            cursor.executescript(migrations.read())
            cursor.close()

    def insert_user(self, user):
        cursor = self._connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, win_count, lose_count, tie_count) VALUES (?, ?, ?, ?, ?)",
            (user.username, user.password, 0, 0, 0),
        )
        self._connection.commit()
        cursor.close()

    def get_user(self, username):
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT username, password FROM users WHERE username = '%s'" % username
        )
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return None

        _, password = user
        return User(username, password)

    def get_all_users(self):
        cursor = self._connection.cursor()
        cursor.execute("SELECT username, win_count, lose_count, tie_count FROM users")
        users = cursor.fetchall()
        cursor.close()

        if not users:
            return None

        return users

    def change_password(self, username, password):
        cursor = self._connection.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE username = ?", (username, password)
        )

        self._connection.commit()

    def update_user_status(self, username, game_status):
        cursor = self._connection.cursor()
        sql_query = f"UPDATE users SET {game_status}_count = {game_status}_count + 1 WHERE username = '{username}'"
        cursor.execute(sql_query)

        self._connection.commit()

    def insert_log(self, type, data):
        cursor = self._connection.cursor()
        sql_query = f"INSERT INTO logs (created_at, type, log) VALUES (?, ?, ?)"
        cursor.execute(sql_query, (datetime.utcnow(), type, json.dumps(data)))
        self._connection.commit()


if __name__ == "__main__":
    pass
