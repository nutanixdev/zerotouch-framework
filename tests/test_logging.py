"""Tests for logging configuration helpers."""

import io
import logging
import time

from ztf.utils.utils import (
    ColoredFormatter,
    LocalTimeFormatter,
    stream_logger_format,
)


def test_local_time_formatter_uses_localtime() -> None:
    """LocalTimeFormatter must use local time, not UTC."""
    formatter = LocalTimeFormatter()
    assert formatter.converter is time.localtime


def test_local_time_formatter_no_utc_z_suffix() -> None:
    """Formatted output must not contain a trailing UTC 'Z' indicator."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatter = LocalTimeFormatter()
    formatted = formatter.format(record)
    assert "hello" in formatted
    asctime_part = formatted.split(" INFO")[0]
    assert not asctime_part.endswith("Z")


def test_local_time_formatter_uses_ztf_format() -> None:
    """LocalTimeFormatter must use the ZTF log format string."""
    formatter = LocalTimeFormatter()
    assert formatter._style._fmt == stream_logger_format


def test_sdk_logger_formatter_override(monkeypatch) -> None:
    """Entity handler _initialize_config must replace SDK UTC formatter."""
    sdk_logger = logging.getLogger("ntnx_test_sdk_py_client")
    sdk_logger.handlers = []
    sdk_logger.propagate = False

    handler = logging.StreamHandler()
    utc_fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    utc_fmt.converter = time.gmtime
    handler.setFormatter(utc_fmt)
    sdk_logger.addHandler(handler)

    ztf_formatter = LocalTimeFormatter()
    for h in sdk_logger.handlers:
        h.setFormatter(ztf_formatter)

    assert handler.formatter is ztf_formatter
    assert handler.formatter.converter is time.localtime

    sdk_logger.handlers = []
    sdk_logger.propagate = True


# ---------------------------------------------------------------------------
# ColoredFormatter
# ---------------------------------------------------------------------------


def _make_record(level: int, msg: str = "test message") -> logging.LogRecord:
    """Create a minimal LogRecord at the given level."""
    return logging.LogRecord(
        name="test",
        level=level,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_colored_formatter_no_color_on_non_tty() -> None:
    """Non-TTY streams must produce plain output (no ANSI escapes)."""
    stream = io.StringIO()
    formatter = ColoredFormatter(stream=stream)
    output = formatter.format(_make_record(logging.INFO))
    assert "\033[" not in output
    assert "test message" in output


def test_colored_formatter_color_on_tty(monkeypatch) -> None:
    """TTY streams must wrap output with ANSI color codes."""

    class FakeTTY(io.StringIO):
        def isatty(self) -> bool:
            return True

    stream = FakeTTY()
    formatter = ColoredFormatter(stream=stream)
    output = formatter.format(_make_record(logging.WARNING))
    assert "\033[33m" in output  # yellow
    assert "\033[0m" in output  # reset


def test_colored_formatter_levels() -> None:
    """Each log level must use its designated color on a TTY."""

    class FakeTTY(io.StringIO):
        def isatty(self) -> bool:
            return True

    stream = FakeTTY()
    formatter = ColoredFormatter(stream=stream)
    expected = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    for level, code in expected.items():
        output = formatter.format(_make_record(level))
        assert code in output, f"Level {level} should use color {code!r}"


def test_colored_formatter_unknown_level_no_color() -> None:
    """Log levels without a colour mapping are output uncolored on TTY."""

    class FakeTTY(io.StringIO):
        def isatty(self) -> bool:
            return True

    stream = FakeTTY()
    formatter = ColoredFormatter(stream=stream)
    record = _make_record(logging.NOTSET, "plain message")
    output = formatter.format(record)
    assert "\033[" not in output
    assert "plain message" in output
