"""
security.py — Input sanitization and prompt-injection detection.
No API keys, no secrets, pure string logic.
"""
import re
import logging

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
MAX_TOPIC_LENGTH = 300

# Patterns that indicate prompt-injection attempts.
# Compiled once at import time for speed.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"\bsystem\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an)\b", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\b", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[system\]", re.IGNORECASE),
    re.compile(r"###\s*instruction", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"override\s+(your\s+)?(previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"prompt\s+injection", re.IGNORECASE),
]


def sanitize_topic(topic: str) -> str:
    """
    Strip leading/trailing whitespace and collapse internal whitespace runs.
    Returns the cleaned topic string.
    """
    if not isinstance(topic, str):
        raise ValueError("Topic must be a string.")
    cleaned = topic.strip()
    # Collapse multiple consecutive whitespace characters
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def check_prompt_injection(topic: str) -> bool:
    """
    Returns True if the topic contains a known prompt-injection pattern.
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(topic):
            logger.warning(
                "Prompt injection pattern detected. Pattern=%s Input_prefix=%.60r",
                pattern.pattern,
                topic,
            )
            return True
    return False


def validate_input(topic: str) -> str:
    """
    Full validation pipeline:
      1. Sanitize whitespace
      2. Enforce length cap
      3. Check for prompt-injection patterns

    Returns the sanitized topic on success.
    Raises ValueError with a user-safe message on failure.
    """
    cleaned = sanitize_topic(topic)

    if not cleaned:
        raise ValueError("Topic must not be empty.")

    if len(cleaned) > MAX_TOPIC_LENGTH:
        raise ValueError(
            f"Topic exceeds the maximum allowed length of {MAX_TOPIC_LENGTH} characters "
            f"(got {len(cleaned)})."
        )

    if check_prompt_injection(cleaned):
        raise ValueError(
            "Topic contains disallowed content. Please submit a plain research topic."
        )

    return cleaned
