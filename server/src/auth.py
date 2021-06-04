import bcrypt
import jwt
import secrets
import time
from src.db import Storage


def hash_password(raw_password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(raw_password, salt)
    return hashed_password


def check_password(raw_password, hashed_password):
    return bcrypt.hashpw(raw_password, hashed_password) == hashed_password
