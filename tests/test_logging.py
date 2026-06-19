import logging

from app.core.config import settings
from app.core.logging import configure_logging


def test_logging_debug_in_local(monkeypatch):
    """Verify DEBUG logging is set in local environment"""
    monkeypatch.setattr(settings, "app_env", "local")
    configure_logging()

    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_logging_info_in_prod(monkeypatch):
    """Verify INFO logging is set in production"""
    monkeypatch.setattr(settings, "app_env", "production")
    configure_logging()

    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO


def test_provider_http_logs_do_not_use_debug(monkeypatch):
    monkeypatch.setattr("app.core.logging.settings.app_env", "local")

    configure_logging()

    assert logging.getLogger("openai").level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
