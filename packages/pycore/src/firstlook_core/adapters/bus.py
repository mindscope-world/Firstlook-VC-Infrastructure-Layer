"""Event bus. Kafka API (Redpanda locally) or in-memory for tests and seeding.

Producers should not publish directly from request paths; they write to the
transactional outbox (firstlook_core.outbox) and the relay publishes here.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from ..config import get_settings


@dataclass(frozen=True)
class Event:
    topic: str
    key: str | None
    payload: dict[str, Any]


class EventBus(Protocol):
    def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None: ...

    def flush(self) -> None: ...

    def consume(
        self,
        topics: Iterable[str],
        group: str,
        handler: Callable[[Event], None],
        *,
        max_events: int | None = None,
    ) -> int:
        """Deliver events to handler until max_events (or forever). Returns the
        number handled. At-least-once: handlers must be idempotent."""
        ...


class InMemoryBus:
    def __init__(self) -> None:
        self.topics: dict[str, list[Event]] = defaultdict(list)
        self._offsets: dict[tuple[str, str], int] = defaultdict(int)

    def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
        self.topics[topic].append(Event(topic, key, json.loads(json.dumps(payload, default=str))))

    def flush(self) -> None:
        pass

    def consume(self, topics, group, handler, *, max_events=None) -> int:
        handled = 0
        for topic in topics:
            events = self.topics[topic]
            while self._offsets[(group, topic)] < len(events):
                if max_events is not None and handled >= max_events:
                    return handled
                handler(events[self._offsets[(group, topic)]])
                self._offsets[(group, topic)] += 1
                handled += 1
        return handled


class KafkaBus:
    def __init__(self, bootstrap: str):
        from confluent_kafka import Producer

        self.bootstrap = bootstrap
        self._producer = Producer({"bootstrap.servers": bootstrap, "enable.idempotence": True, "acks": "all"})

    def publish(self, topic: str, payload: dict[str, Any], key: str | None = None) -> None:
        self._producer.produce(
            topic, json.dumps(payload, default=str).encode(), key=key.encode() if key else None
        )
        self._producer.poll(0)

    def flush(self) -> None:
        remaining = self._producer.flush(30)
        if remaining:
            raise RuntimeError(f"{remaining} events not delivered to Kafka")

    def consume(self, topics, group, handler, *, max_events=None, idle_timeout: float | None = None) -> int:
        from confluent_kafka import Consumer

        consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap,
                "group.id": group,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        consumer.subscribe(list(topics))
        handled = 0
        idle = 0.0
        try:
            while max_events is None or handled < max_events:
                msg = consumer.poll(1.0)
                if msg is None:
                    idle += 1.0
                    if idle_timeout is not None and idle >= idle_timeout:
                        break
                    continue
                idle = 0.0
                if msg.error():
                    raise RuntimeError(msg.error())
                key = msg.key().decode() if msg.key() else None
                handler(Event(msg.topic(), key, json.loads(msg.value())))
                consumer.commit(msg, asynchronous=False)
                handled += 1
        finally:
            consumer.close()
        return handled


@lru_cache
def get_bus() -> EventBus:
    s = get_settings()
    if s.bus_backend == "memory":
        return InMemoryBus()
    if s.bus_backend == "kafka":
        return KafkaBus(s.kafka_bootstrap)
    raise ValueError(f"unknown bus backend {s.bus_backend!r}")


def run_consumer(
    topics: list[str],
    group: str,
    handler: Callable[[Event], object],
    bus: EventBus | None = None,
    **kwargs: Any,
) -> int:
    """Consume with a dead-letter queue: a failing event is logged and published
    to <topic>.dlq with the error, and consumption continues."""
    import logging
    import traceback

    log = logging.getLogger(f"firstlook.consumer.{group}")
    bus = bus or get_bus()

    def safe(event: Event) -> None:
        try:
            handler(event)
        except Exception as e:  # noqa: BLE001 - every failure goes to the DLQ
            log.exception("handler failed for %s key=%s", event.topic, event.key)
            bus.publish(
                f"{event.topic}.dlq",
                {
                    "event": event.payload,
                    "error": repr(e),
                    "traceback": traceback.format_exc(limit=5),
                    "group": group,
                },
                key=event.key,
            )
            bus.flush()

    return bus.consume(topics, group, safe, **kwargs)
