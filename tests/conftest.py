import logging

import pytest


class HealthyDb:
    def execute(self, statement):
        return None


@pytest.fixture(autouse=True)
def reset_logger_state():
    """Reset logging to initial state after each test"""
    yield
    logging.getLogger().handlers.clear()
    logging.getLogger().setLevel(logging.WARNING)
