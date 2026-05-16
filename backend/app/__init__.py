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
from .config import load_config
from .routes.amendments import amendments_bp
from .routes.internal import internal_bp
from .routes.sms import sms_bp
from .routes.subscribe import subscribe_bp
from .scheduler import configure_scheduler
from .services.bq import ensure_person3_tables


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(load_config())

    app.register_blueprint(subscribe_bp)
    app.register_blueprint(amendments_bp)
    app.register_blueprint(internal_bp)
    app.register_blueprint(sms_bp)

    ensure_person3_tables(app.config)
    configure_scheduler(app)

    @app.get("/health")
    def health() -> tuple[dict, int]:
        return {"status": "ok"}, 200

    return app
