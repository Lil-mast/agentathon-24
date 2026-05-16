from __future__ import annotations

from flask import Flask

from .health import bp as health_bp
from .internal import bp as internal_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(internal_bp)
