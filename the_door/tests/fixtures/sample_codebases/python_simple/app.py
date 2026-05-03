"""Main application entry point."""
from flask import Flask
from .auth import authenticate_user
from .tasks import schedule_cleanup

app = Flask(__name__)


@app.route("/login", methods=["POST"])
def login():
    """Handle user login requests."""
    return authenticate_user()


@app.route("/users", methods=["GET"])
def list_users():
    """List all registered users."""
    return {"users": []}
