from typing import Any, Optional, Text

from pymongo import MongoClient

from .exceptions import MultipleResultsFound, NotFound
from .query import delete, select, update
from .version import VERSION

__version__ = VERSION

__all__ = [
    "create_engine",
    "select",
    "update",
    "delete",
    "NotFound",
    "MultipleResultsFound",
]


def create_engine(
    host: Optional[Text] = None,
    port: Optional[int] = None,
    document_class: Optional[Text] = None,
    tz_aware: Optional[bool] = None,
    connect: Optional[bool] = None,
    type_registry: Optional[Text] = None,
    **kwargs: Any
) -> MongoClient:
    engine = MongoClient(
        host=host,
        port=port,
        document_class=document_class,
        tz_aware=tz_aware,
        connect=connect,
        type_registry=type_registry,
        **kwargs
    )
    return engine
