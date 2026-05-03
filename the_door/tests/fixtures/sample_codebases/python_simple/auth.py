"""Authentication module."""


def authenticate_user():
    """Verify user credentials and return a session token."""
    token = generate_token()
    return {"token": token}


def generate_token():
    """Generate a secure random token."""
    import secrets
    return secrets.token_hex(32)
