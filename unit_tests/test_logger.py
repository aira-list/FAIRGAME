"""Tests for the centralized logging helper."""

from __future__ import annotations

import logging
import unittest
from unittest import mock

from src.utils import logger as logger_module


class TestLogger(unittest.TestCase):
    def setUp(self) -> None:
        # Reset module state for test isolation.
        logger_module._CONFIGURED = False
        logging.getLogger().handlers.clear()

    def tearDown(self) -> None:
        logger_module._CONFIGURED = False
        logging.getLogger().handlers.clear()

    def test_configure_logging_idempotent_unless_forced(self) -> None:
        logger_module.configure_logging(level="DEBUG")
        first_handlers = list(logging.getLogger().handlers)
        logger_module.configure_logging(level="ERROR")
        # No-op the second time.
        self.assertEqual(list(logging.getLogger().handlers), first_handlers)

        logger_module.configure_logging(level="ERROR", force=True)
        self.assertEqual(logging.getLogger().level, logging.ERROR)

    def test_get_logger_lazy_configures(self) -> None:
        log = logger_module.get_logger("fairgame.test")
        self.assertTrue(logger_module._CONFIGURED)
        self.assertEqual(log.name, "fairgame.test")

    def test_invalid_env_var_falls_back_to_default(self) -> None:
        with mock.patch.dict("os.environ", {"FAIRGAME_LOG_LEVEL": ""}):
            logger_module.configure_logging(force=True)
            self.assertEqual(logging.getLogger().level, logging.INFO)


if __name__ == "__main__":
    unittest.main()
