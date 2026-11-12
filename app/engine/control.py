"""Shared engine control-flow exceptions."""

from __future__ import annotations


class Cancelled(Exception):
    """Raised inside a job when the user cancelled it; not an error."""
