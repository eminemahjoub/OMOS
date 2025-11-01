"""Local-first AI placeholder logic used by OMOS."""

# ---------------- Standard Library Imports ----------------
from __future__ import annotations

import platform
import random
import socket
from datetime import datetime


# ---------------- Helper Functions ----------------
def _current_time() -> str:
    """Return a friendly formatted current time string."""
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def _current_date() -> str:
    """Return a friendly formatted current date string."""
    return datetime.now().strftime("%A, %B %d, %Y")


def _system_summary() -> str:
    """Provide a quick summary of the host system without external calls."""
    hostname = socket.gethostname()
    os_name = platform.system()
    os_version = platform.version()
    return f"Running on {os_name} {os_version} — host name {hostname}."


def _default_responses() -> list[str]:
    """Return a rotating list of canned responses for unmatched prompts."""
    return [
        "I am here and listening. Try asking about the system or the time.",
        "Still offline-friendly — no cloud calls were harmed in this reply.",
        "Processing locally. You can customise my brain inside ai/ai_core.py.",
        "Let's keep things simple. Ask for date, time, or a system status update.",
    ]


# ---------------- Main Entry Point ----------------
def answer(prompt: str) -> str:
    """Generate a canned response to the supplied user prompt."""
    if not prompt:
        return "I did not catch anything to process."

    prompt_lower = prompt.lower()
    if any(keyword in prompt_lower for keyword in ("time", "clock")):
        return f"Current time: {_current_time()}"

    if any(keyword in prompt_lower for keyword in ("date", "day")):
        return f"Today is {_current_date()}"

    if "hello" in prompt_lower or "hi" in prompt_lower:
        return "Hello! Ready to help locally."

    if "who" in prompt_lower and "you" in prompt_lower:
        return "I am OMOS — a desktop-first assistant keeping your data on device."

    if "system" in prompt_lower or "status" in prompt_lower:
        return _system_summary()

    if "help" in prompt_lower:
        return "Try asking for the current time, current date, or a quick system summary."

    return random.choice(_default_responses())
