import logging
import os
from typing import Generator

import pytest
from pymongo import MongoClient

from mongotic import create_engine

logger = logging.getLogger("pytest")


@pytest.fixture
def mongo_engine() -> Generator["MongoClient", None, None]:
    if "MONGODB_URI" not in os.environ:
        raise Exception("Testing MONGODB_URI environment variable not set.")

    mongo_conn_str = os.environ["MONGODB_URI"]
    logger.debug(f"Connect to MongoDB: {mongo_conn_str}")

    engine = create_engine(mongo_conn_str)
    yield engine
    engine.close()
