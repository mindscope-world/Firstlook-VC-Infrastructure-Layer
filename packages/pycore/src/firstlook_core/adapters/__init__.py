"""Provider-neutral interfaces with local implementations (ADR 0002).

Each adapter has a local implementation used in development and tests, and a
contract test suite (packages/pycore/tests/test_adapter_contracts.py) that any
future cloud implementation must also pass.
"""

from .bus import EventBus, get_bus
from .kms import Kms, get_kms
from .mailer import Mailer, get_mailer
from .ocr import OcrEngine, get_ocr
from .storage import ObjectStore, get_store

__all__ = [
    "EventBus",
    "Kms",
    "Mailer",
    "ObjectStore",
    "OcrEngine",
    "get_bus",
    "get_kms",
    "get_mailer",
    "get_ocr",
    "get_store",
]
