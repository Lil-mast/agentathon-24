from flask import Flask

from app.config import Config
from app.routes.agent import agent_bp
from app.routes.ask import ask_bp
from app.routes.health import health_bp
from app.routes.internal import internal_bp


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    app.register_blueprint(health_bp)
    app.register_blueprint(ask_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(internal_bp)

    return app
