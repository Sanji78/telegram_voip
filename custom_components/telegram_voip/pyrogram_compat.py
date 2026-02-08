from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


def patch_pyrogram_send() -> None:
    """Make Pyrogram v2 compatible with libs expecting Client.send().

    Some third-party libraries still call `client.send(...)` (Pyrogram v1 style).
    Pyrogram v2 uses `client.invoke(...)`. In some runtimes (e.g. HA on Python 3.13)
    Client.send is not present, so we alias it to invoke.
    """
    try:
        from pyrogram import Client
    except Exception as err:
        _LOGGER.debug("Pyrogram not available to patch: %s", err)
        return

    if hasattr(Client, "send"):
        return

    invoke = getattr(Client, "invoke", None)
    if not callable(invoke):
        _LOGGER.warning("Cannot patch Pyrogram: Client.invoke is missing")
        return

    # Add alias
    setattr(Client, "send", invoke)
    _LOGGER.debug("Patched Pyrogram: added Client.send alias to Client.invoke")