from typing import Any, MutableMapping, Optional, Text, Type

from bson.codec_options import TypeRegistry
from pymongo import AsyncMongoClient

from mongotic.model import MongoBaseModel


def create_async_engine(
    host: Optional[Text] = None,
    port: Optional[int] = None,
    document_class: Optional[Type[MutableMapping]] = None,
    tz_aware: Optional[bool] = None,
    connect: Optional[bool] = None,
    type_registry: Optional[TypeRegistry] = None,
    **kwargs: Any,
) -> AsyncMongoClient:
    return AsyncMongoClient(
        host=host,
        port=port,
        document_class=document_class,
        tz_aware=tz_aware,
        connect=connect,
        type_registry=type_registry,
        **kwargs,
    )


async def create_async_indexes(
    engine: AsyncMongoClient, *models: Type[MongoBaseModel]
) -> None:
    for model in models:
        if not model.__indexes__:
            continue
        collection = engine[model.__databasename__][model.__tablename__]
        await collection.create_indexes(model.__indexes__)
