import re


def validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Invalid email address")
    return email


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not re.match(r"^[a-zA-Z0-9_\-\.]{3,32}$", username):
        raise ValueError("Username must be 3-32 chars, alnum/_/-. only")
    return username


def validate_password(password: str) -> str:
    password = password or ""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain a lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain a digit")
    return password

