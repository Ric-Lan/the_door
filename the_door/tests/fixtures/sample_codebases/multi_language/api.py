"""REST API gateway."""
from flask import Flask

app = Flask(__name__)


@app.route("/health")
def health_check():
    """System health endpoint."""
    return {"status": "ok"}
