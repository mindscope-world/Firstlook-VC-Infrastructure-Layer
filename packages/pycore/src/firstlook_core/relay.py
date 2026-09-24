"""Outbox relay: moves committed outbox rows to the event bus.

uv run python -m firstlook_core.relay
"""

from __future__ import annotations

import logging
import time

from .adapters.bus import get_bus
from .db import system_tx
from .outbox import relay_once

log = logging.getLogger("firstlook.relay")


def main(poll_seconds: float = 0.5) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    bus = get_bus()
    while True:
        try:
            with system_tx() as conn:
                n = relay_once(conn, bus)
            if n:
                log.info("relayed %d events", n)
                continue
        except Exception:  # noqa: BLE001 - keep relaying; rows stay unpublished and are retried
            log.exception("relay failed")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
