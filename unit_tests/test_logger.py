"""Tests for the centralized logging helper."""

from __future__ import annotations

import logging
import unittest
from unittest import mock

from src.utils import logger as logger_module


class _LoggerTestBase(unittest.TestCase):
    """Reset module state between tests so they don't leak handlers."""

    def setUp(self) -> None:
        logger_module._CONFIGURED = False
        logging.getLogger().handlers.clear()

    def tearDown(self) -> None:
        logger_module._CONFIGURED = False
        logging.getLogger().handlers.clear()


class TestConfigureLogging(_LoggerTestBase):
    def test_first_call_configures_root_logger(self) -> None:
        self.assertFalse(logger_module._CONFIGURED)
        logger_module.configure_logging(level="DEBUG")
        self.assertTrue(logger_module._CONFIGURED)
        self.assertEqual(logging.getLogger().level, logging.DEBUG)
        # Exactly one handler is installed on the root logger.
        self.assertEqual(len(logging.getLogger().handlers), 1)

    def test_second_call_is_a_noop(self) -> None:
        logger_module.configure_logging(level="DEBUG")
        snapshot = list(logging.getLogger().handlers)
        logger_module.configure_logging(level="ERROR")
        # No new handler, root level unchanged from first call.
        self.assertEqual(list(logging.getLogger().handlers), snapshot)
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_force_reconfigures(self) -> None:
        logger_module.configure_logging(level="DEBUG")
        logger_module.configure_logging(level="ERROR", force=True)
        self.assertEqual(logging.getLogger().level, logging.ERROR)
        self.assertEqual(len(logging.getLogger().handlers), 1)

    def test_levels_are_case_insensitive(self) -> None:
        logger_module.configure_logging(level="debug")
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_invalid_level_raises_value_error(self) -> None:
        # logging.setLevel rejects unknown level strings — surface that
        # to the caller rather than swallowing it.
        with self.assertRaises(ValueError):
            logger_module.configure_logging(level="not_a_level")

    def test_quiets_known_noisy_loggers(self) -> None:
        logger_module.configure_logging(level="DEBUG")
        for noisy in ("urllib3", "botocore", "s3fs", "aiobotocore", "httpx"):
            self.assertEqual(
                logging.getLogger(noisy).level,
                logging.WARNING,
                msg=f"{noisy} not quieted",
            )


class TestGetLogger(_LoggerTestBase):
    def test_lazy_configures_on_first_call(self) -> None:
        self.assertFalse(logger_module._CONFIGURED)
        log = logger_module.get_logger("fairgame.test")
        self.assertTrue(logger_module._CONFIGURED)
        self.assertEqual(log.name, "fairgame.test")

    def test_subsequent_calls_dont_reconfigure(self) -> None:
        logger_module.get_logger("a")
        snapshot = list(logging.getLogger().handlers)
        logger_module.get_logger("b")
        self.assertEqual(list(logging.getLogger().handlers), snapshot)

    def test_returns_a_logger_instance(self) -> None:
        log = logger_module.get_logger("fairgame.x")
        self.assertIsInstance(log, logging.Logger)

    def test_distinct_names_yield_distinct_loggers(self) -> None:
        a = logger_module.get_logger("fairgame.a")
        b = logger_module.get_logger("fairgame.b")
        self.assertIsNot(a, b)


class TestEnvVarFallback(_LoggerTestBase):
    def test_empty_env_var_falls_back_to_info(self) -> None:
        with mock.patch.dict("os.environ", {"FAIRGAME_LOG_LEVEL": ""}):
            logger_module.configure_logging(force=True)
            self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_unset_env_var_falls_back_to_info(self) -> None:
        env_without_level = {
            k: v for k, v in __import__("os").environ.items()
            if k != "FAIRGAME_LOG_LEVEL"
        }
        with mock.patch.dict("os.environ", env_without_level, clear=True):
            logger_module.configure_logging(force=True)
            self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_env_var_warning_takes_effect(self) -> None:
        with mock.patch.dict("os.environ", {"FAIRGAME_LOG_LEVEL": "WARNING"}):
            logger_module.configure_logging(force=True)
            self.assertEqual(logging.getLogger().level, logging.WARNING)

    def test_explicit_level_overrides_env_var(self) -> None:
        with mock.patch.dict("os.environ", {"FAIRGAME_LOG_LEVEL": "ERROR"}):
            logger_module.configure_logging(level="DEBUG", force=True)
            self.assertEqual(logging.getLogger().level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
