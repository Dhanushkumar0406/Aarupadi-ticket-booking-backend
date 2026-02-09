import bcrypt


def hash_password(plain_text):
    hashed = bcrypt.hashpw(plain_text.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def check_password(plain_text, hashed_text):
    return bcrypt.checkpw(plain_text.encode("utf-8"), hashed_text.encode("utf-8"))
