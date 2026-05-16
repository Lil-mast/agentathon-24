from __future__ import annotations

import logging

from flask import Flask

from .health import bp as health_bp
from .internal import bp as internal_bp

logger = logging.getLogger(__name__)


def register_blueprints(app: Flask) -> None:
    """Register all available blueprints.

    Core blueprints (health, internal/search) are mandatory.
    Person 2 (subscribe/sms/amendments) and Person 3 (ask/agent) blueprints
    are imported lazily so a missing optional dep does not block startup.
    """
    app.register_blueprint(health_bp)
    app.register_blueprint(internal_bp)

    for module_name, attr in [
        ("app.routes.subscribe", "subscribe_bp"),
        ("app.routes.amendments", "amendments_bp"),
        ("app.routes.sms", "sms_bp"),
        ("app.routes.ask", "ask_bp"),
        ("app.routes.agent", "agent_bp"),
    ]:
        try:
            module = __import__(module_name, fromlist=[attr])
            app.register_blueprint(getattr(module, attr))
        except Exception:
            logger.exception("Skipped blueprint %s.%s (import failed)", module_name, attr)
