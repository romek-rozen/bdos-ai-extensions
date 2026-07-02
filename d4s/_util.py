"""Shared internals for d4s wrappers: client resolution and geo params."""

from .d4s_client import Client


def get_client(client):
    """Return the given client, or a default env-configured one."""
    return client if client is not None else Client()


def geo(task, location=None, language=None):
    """Attach location/language to a task dict.

    A string is sent as ``location_name`` / ``language_name``; an int as
    ``location_code`` / ``language_code``. ``None`` is skipped.
    """
    if location is not None:
        key = "location_code" if isinstance(location, int) else "location_name"
        task[key] = location
    if language is not None:
        key = "language_code" if isinstance(language, int) else "language_name"
        task[key] = language
    return task
