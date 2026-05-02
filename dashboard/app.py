import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from config import Config
from database import init_db


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = Config.FLASK_SECRET_KEY

    init_db()

    from dashboard.routes import bp
    app.register_blueprint(bp)

    return app


if __name__ == "__main__":
    app = create_app()
    print(f"\n  ATAOL AI Techs Outreach Dashboard")
    print(f"  http://localhost:{Config.FLASK_PORT}\n")
    app.run(host="127.0.0.1", port=Config.FLASK_PORT, debug=False)
