"""Rewrite style registry: style key -> label + prompt guidance."""

from __future__ import annotations

REWRITE_STYLES: dict[str, dict[str, str]] = {
    "professional": {
        "label": "Professional",
        "guidance": (
            "Formal, precise business tone. Clean sentences, confident voice, "
            "no slang or contractions."
        ),
    },
    "casual": {
        "label": "Casual",
        "guidance": (
            "Relaxed conversational tone, contractions welcome, like explaining "
            "to a friend over coffee."
        ),
    },
    "genz": {
        "label": "Gen Z",
        "guidance": (
            "Playful, energetic internet-native tone. Casual slang and modern "
            "phrasing are welcome; keep it readable and never cringe-forced."
        ),
    },
    "technical": {
        "label": "Technical",
        "guidance": (
            "Precise engineering tone. Exact terminology, concrete examples, "
            "explicit assumptions and caveats."
        ),
    },
    "marketing": {
        "label": "Marketing",
        "guidance": (
            "Persuasive copywriting tone. Benefit-led framing, strong verbs, "
            "clear calls to action."
        ),
    },
    "minimal": {
        "label": "Minimal",
        "guidance": (
            "Stripped-down, short sentences, zero filler. Say everything in "
            "the fewest words that stay complete."
        ),
    },
}


def get_style(key: str) -> dict[str, str]:
    try:
        return REWRITE_STYLES[key]
    except KeyError:
        raise ValueError(f"Unknown rewrite style: {key}") from None
