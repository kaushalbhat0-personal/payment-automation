import logging
import os

from dotenv import load_dotenv
from flask import Flask

from app.config import Config

def create_app() -> Flask:
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger(__name__)

    app = Flask(__name__)
    cfg = Config.from_env()
    app.config["APP_CONFIG"] = cfg

    skip_raw = os.environ.get("SKIP_WEBHOOK_VERIFY")
    log.info(
        "SKIP_WEBHOOK_VERIFY from environment: %r -> parsed skip_webhook_verify=%s",
        skip_raw,
        cfg.skip_webhook_verify,
    )

    from app.routes.health import bp as health_bp
    from app.routes.webhooks import bp as webhooks_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(webhooks_bp)

    if os.environ.get("FLASK_DEBUG") == "1":
        app.logger.setLevel(logging.DEBUG)

    return app
