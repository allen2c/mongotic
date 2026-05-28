import logging
import os
from typing import Generator

import pytest
import pytest_asyncio
from pymongo import AsyncMongoClient, MongoClient

from mongotic import create_engine

logger = logging.getLogger("pytest")


def _is_cosmos() -> bool:
    uri = os.environ.get("MONGODB_URI", "").lower()
    return "cosmos" in uri or "documents.azure.com" in uri


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "cosmos_unsupported: test exercises an operation Azure Cosmos DB does not support",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not _is_cosmos():
        return
    skip_cosmos = pytest.mark.skip(
        reason="Cosmos DB limitation (see docs/cosmos-compatibility.md)"
    )
    for item in items:
        if "cosmos_unsupported" in item.keywords:
            item.add_marker(skip_cosmos)


@pytest.fixture
def mongo_engine() -> Generator["MongoClient", None, None]:
    if "MONGODB_URI" not in os.environ:
        raise Exception("Testing MONGODB_URI environment variable not set.")

    mongo_conn_str = os.environ["MONGODB_URI"]
    logger.debug(f"Connect to MongoDB: {mongo_conn_str}")

    engine = create_engine(mongo_conn_str)
    yield engine
    engine.close()


@pytest_asyncio.fixture
async def async_mongo_engine():
    if "MONGODB_URI" not in os.environ:
        raise Exception("Testing MONGODB_URI environment variable not set.")
    engine = AsyncMongoClient(os.environ["MONGODB_URI"])
    try:
        yield engine
    finally:
        await engine.aclose()
