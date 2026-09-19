"""A resilient wrapper around pypresence.

Discord silently drops rich presence updates sent faster than roughly five per
twenty seconds, and pypresence raises as soon as the Discord client is not
there. This class absorbs both problems:

  * identical payloads are never re-sent,
  * bursts are collapsed into one queued update that is flushed once the
    cooldown has passed,
  * a missing or restarted Discord client is retried in the background instead
    of taking the whole script down.
"""

import logging
import time

from pypresence import Presence
from pypresence.exceptions import PyPresenceException

import config

log = logging.getLogger(__name__)

# Discord rejects state/details strings shorter than 2 or longer than 128 chars.
_MIN_TEXT = 2
_MAX_TEXT = 128


def _sanitise(payload):
    """Drop empty fields and clamp text so Discord never rejects the payload."""
    clean = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if len(value) < _MIN_TEXT:
                continue
            value = value[:_MAX_TEXT]
        clean[key] = value
    return clean


class PresenceClient:
    def __init__(self, app_id=config.APP_ID):
        self._app_id = app_id
        self._rpc = None
        self._sent = None          # last payload Discord actually accepted
        self._pending = None       # payload waiting for the cooldown to pass
        self._sent_at = 0.0
        self._retry_at = 0.0

    @property
    def connected(self):
        return self._rpc is not None

    # -- connection ---------------------------------------------------------

    def _connect(self):
        """Try to attach to a running Discord client. Never raises."""
        now = time.monotonic()
        if self._rpc is not None or now < self._retry_at:
            return self._rpc is not None
        try:
            rpc = Presence(self._app_id)
            rpc.connect()
        except (PyPresenceException, OSError, RuntimeError) as exc:
            self._retry_at = now + config.RECONNECT_DELAY
            log.warning("Discord not reachable (%s), retrying in %.0fs",
                        type(exc).__name__, config.RECONNECT_DELAY)
            return False
        self._rpc = rpc
        self._sent = None          # force a resend after a reconnect
        log.info("Connected to Discord")
        return True

    def _drop(self, exc):
        log.warning("Lost the Discord connection (%s)", type(exc).__name__)
        try:
            self._rpc.close()
        except Exception:
            pass
        self._rpc = None
        self._sent = None
        self._retry_at = time.monotonic() + config.RECONNECT_DELAY

    # -- updates ------------------------------------------------------------

    def set(self, payload):
        """Queue a presence. Sent immediately if the cooldown allows it."""
        if payload is None:
            return
        payload = _sanitise(payload)
        if payload == self._sent or payload == self._pending:
            return
        self._pending = payload
        self.flush()

    def flush(self):
        """Send the queued presence if one is waiting and Discord is ready."""
        if self._pending is None:
            return
        if time.monotonic() - self._sent_at < config.RPC_MIN_INTERVAL:
            return
        if not self._connect():
            return
        payload = self._pending
        try:
            self._rpc.update(**payload)
        except (PyPresenceException, OSError, RuntimeError) as exc:
            self._drop(exc)        # keep _pending so the retry resends it
            return
        self._pending = None
        self._sent = payload
        self._sent_at = time.monotonic()
        log.debug("presence -> %s", payload)

    def clear(self):
        """Remove the presence but keep the connection, so relaunches are instant."""
        self._pending = None
        if self._rpc is None or self._sent is None:
            return
        try:
            self._rpc.clear()
        except (PyPresenceException, OSError, RuntimeError) as exc:
            self._drop(exc)
            return
        self._sent = None
        self._sent_at = time.monotonic()
        log.info("Presence cleared")

    def close(self):
        if self._rpc is None:
            return
        try:
            self._rpc.clear()
            self._rpc.close()
        except Exception:
            pass
        self._rpc = None
        self._sent = None


class _Sink:
    """Stands in for the Discord pipe and just says what it was given."""

    def connect(self):
        pass

    def update(self, **payload):
        shown = {k: v for k, v in payload.items() if k != "status_display_type"}
        log.info("would send %s", shown)

    def clear(self):
        log.info("would clear the presence")

    def close(self):
        pass


class DryRunClient(PresenceClient):
    """Same throttling and dedup, but nothing ever reaches Discord."""

    def _connect(self):
        if self._rpc is None:
            self._rpc = _Sink()
            log.info("Dry run: Discord will not be contacted")
        return True
