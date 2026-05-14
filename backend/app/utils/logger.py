import io
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


Path("logs").mkdir(exist_ok=True)

# ── Emoji prefixes for each log level ────────────────────────────────────────
_LEVEL_EMOJI = {
    "DEBUG":    "🔍",
    "INFO":     "✅",
    "WARNING":  "⚠️",
    "ERROR":    "❌",
    "CRITICAL": "🔴",
}

# ── Component badges ─────────────────────────────────────────────────────────
_COMPONENT_BADGE = {
    "AGENT":       "🤖 AGENT",
    "NLP":         "📝 NLP",
    "DB":          "🗄️  DB",
    "APP":         "🚀 APP",
    "SQUAD":       "💳 SQUAD",
    "TXN_MONITOR": "📊 TXN",
    "OCR":         "👁️  OCR",
}

# ── Single shared UTF-8 stdout (prevents duplicate writes) ───────────────────
_SHARED_STDOUT: io.TextIOWrapper | None = None


def _utf8_stdout() -> io.TextIOWrapper:
    """Return a single UTF-8 stdout wrapper so emoji work on Windows (cp1252).
    Reuses the same wrapper across all loggers to prevent duplicate output."""
    global _SHARED_STDOUT
    if _SHARED_STDOUT is None or _SHARED_STDOUT.closed:
        if hasattr(sys.stdout, "buffer"):
            _SHARED_STDOUT = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
            )
        else:
            _SHARED_STDOUT = sys.stdout
    return _SHARED_STDOUT


class _TrustGateFormatter(logging.Formatter):
    """Colourful, emoji-rich formatter for terminal output."""

    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", record.name.split(".")[-1].upper())
        badge = _COMPONENT_BADGE.get(component, f"📦 {component}")
        emoji = _LEVEL_EMOJI.get(record.levelname, "")

        msg = record.getMessage()
        if msg.startswith("   "):
            formatted = f"[TrustGate {badge}] {self._ts(record)} │ {msg}"
        elif msg.startswith("──") or msg.startswith("▶") or msg.startswith("✓"):
            formatted = f"[TrustGate {badge}] {self._ts(record)} │ {msg}"
        else:
            formatted = f"[TrustGate {badge}] {self._ts(record)} │ {emoji} {msg}"

        return formatted

    @staticmethod
    def _ts(record: logging.LogRecord) -> str:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%H:%M:%S")


class _FileFormatter(logging.Formatter):
    """Plain formatter for log files (no emoji, no colour codes)."""

    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", record.name.split(".")[-1].upper())
        return f"[{record.levelname}] {self.formatTime(record, '%H:%M:%S')} | {component} | {record.getMessage()}"


def get_logger(name: str) -> logging.Logger:
    component = name.upper()
    log = logging.getLogger(f"trustgate.{component}")

    if not log.handlers:
        log.setLevel(logging.DEBUG)
        log.propagate = False

        # ── Console handler (pretty, UTF-8 safe) ─────────────────────────
        console = logging.StreamHandler(_utf8_stdout())
        console.setLevel(logging.DEBUG)
        console.setFormatter(_TrustGateFormatter())
        log.addHandler(console)

        # ── File handler (plain) ─────────────────────────────────────────
        file_handler = RotatingFileHandler(
            f"logs/{component}.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_FileFormatter())
        log.addHandler(file_handler)

    return log


# ── Kill any root-level handlers that cause duplicates ───────────────────────
logging.root.handlers.clear()
logging.root.setLevel(logging.WARNING)


def _log(component: str, msg: str, level: str = "info") -> None:
    log = get_logger(component)
    getattr(log, level)(msg, extra={"component": component.upper()})


def agent_log(msg: str, level: str = "info") -> None:
    _log("AGENT", msg, level)


def nlp_log(msg: str, level: str = "info") -> None:
    _log("NLP", msg, level)


def squad_log(msg: str, level: str = "info") -> None:
    _log("SQUAD", msg, level)


def db_log(msg: str, level: str = "info") -> None:
    _log("DB", msg, level)


def txn_log(msg: str, level: str = "info") -> None:
    _log("TXN_MONITOR", msg, level)


def ocr_log(msg: str, level: str = "info") -> None:
    _log("OCR", msg, level)


# Backward-compatible app logger for older modules.
logger = get_logger("APP")
