from __future__ import annotations

import logging

from flask import Flask

from .config import Config
from .routes import register_blueprints

logger = logging.getLogger(__name__)


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    register_blueprints(app)

    if app.config.get("ENABLE_DEV_SCHEDULER", False):
        try:
            from .scheduler import configure_scheduler
            configure_scheduler(app)
        except Exception:
            logger.exception("scheduler init failed; continuing without it")

    return app
