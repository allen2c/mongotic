from typing import Any, List, MutableMapping, Optional, Text, Type

from bson.codec_options import TypeRegistry
from pymongo import MongoClient

from .exceptions import MultipleResultsFound, NotFound
from .model import MongoBaseModel, and_, not_, or_
from .query import delete, select, update
from .version import VERSION

__version__ = VERSION

__all__ = [
    "create_engine",
    "create_indexes",
    "select",
    "update",
    "delete",
    "or_",
    "and_",
    "not_",
    "NotFound",
    "MultipleResultsFound",
]


def create_indexes(engine: MongoClient, *models: Type[MongoBaseModel]) -> None:
    """Create MongoDB indexes declared in ``model.__indexes__``.

    Example::

        create_indexes(engine, User, Post)
    """
    for model in models:
        if not model.__indexes__:
            continue
        collection = engine[model.__databasename__][model.__tablename__]
        collection.create_indexes(model.__indexes__)


def create_engine(
    host: Optional[Text] = None,
    port: Optional[int] = None,
    document_class: Optional[Type[MutableMapping]] = None,
    tz_aware: Optional[bool] = None,
    connect: Optional[bool] = None,
    type_registry: Optional[TypeRegistry] = None,
    **kwargs: Any,
) -> MongoClient:
    engine = MongoClient(
        host=host,
        port=port,
        document_class=document_class,
        tz_aware=tz_aware,
        connect=connect,
        type_registry=type_registry,
        **kwargs,
    )
    return engine
