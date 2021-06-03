import bcrypt
import jwt
from db import Storage


def hash_password(raw_password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(raw_password, salt)
    return hashed_password


def check_password(raw_password, hashed_password):
    return bcrypt.hashpw(raw_password, hashed_password) == hashed_password


def login(user, password):
    if user and check_password(password, user.password):
        token = jwt.encode({"username": user.username},
                           "secret", algorithm="HS256")
        return token
    return None
