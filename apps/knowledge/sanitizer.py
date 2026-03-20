"""Content sanitizer for clinical knowledge ingestion.

Strips known prompt injection patterns from content before embedding.
Logs sanitization events for audit trail.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that could be used for prompt injection in RAG context.
# These are stripped during ingestion, before content enters the knowledge base.
INJECTION_PATTERNS = [
    # Direct instruction override attempts
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE), "instruction_override"),
    (re.compile(r"disregard\s+(all\s+)?previous\s+(instructions?|context)", re.IGNORECASE), "instruction_override"),
    (re.compile(r"forget\s+(everything|all|what)\s+(you|I)\s+(told|said)", re.IGNORECASE), "instruction_override"),
    # System/role injection
    (re.compile(r"^system\s*:", re.IGNORECASE | re.MULTILINE), "role_injection"),
    (re.compile(r"^(assistant|user|human)\s*:", re.IGNORECASE | re.MULTILINE), "role_injection"),
    (re.compile(r"\[INST\].*?\[/INST\]", re.IGNORECASE | re.DOTALL), "role_injection"),
    # Delimiter manipulation
    (re.compile(r"</?(system|prompt|instruction|context)>", re.IGNORECASE), "delimiter_manipulation"),
    (re.compile(r"---\s*END\s*(OF\s+)?(SYSTEM|CONTEXT|INSTRUCTIONS?)\s*---", re.IGNORECASE), "delimiter_manipulation"),
    # Output manipulation
    (
        re.compile(r"(do\s+not|don'?t)\s+mention\s+(this|the\s+above|these\s+instructions?)", re.IGNORECASE),
        "output_manipulation",
    ),
    (re.compile(r"(pretend|act\s+as\s+if)\s+you\s+(are|were)", re.IGNORECASE), "output_manipulation"),
    # Data exfiltration
    (
        re.compile(r"(repeat|print|output|show)\s+(your|the)\s+(system\s+)?(prompt|instructions?)", re.IGNORECASE),
        "data_exfiltration",
    ),
]


def sanitize_content(content: str, source_name: str = "") -> tuple[str, list[dict]]:
    """Sanitize content by removing known prompt injection patterns.

    Args:
        content: Raw text content to sanitize.
        source_name: Name of the source (for audit logging).

    Returns:
        Tuple of (sanitized_content, list of sanitization events).
        Each event is a dict with 'pattern_type', 'match', and 'position'.
    """
    events = []
    sanitized = content

    for pattern, pattern_type in INJECTION_PATTERNS:
        for match in pattern.finditer(sanitized):
            events.append(
                {
                    "pattern_type": pattern_type,
                    "match": match.group()[:100],  # Truncate long matches
                    "position": match.start(),
                }
            )

        sanitized = pattern.sub("", sanitized)

    # Clean up any resulting double-whitespace from removals
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    sanitized = re.sub(r"  +", " ", sanitized)

    if events:
        logger.warning(
            "Sanitized %d injection pattern(s) from %s: %s",
            len(events),
            source_name or "unknown source",
            [e["pattern_type"] for e in events],
        )

    return sanitized.strip(), events
