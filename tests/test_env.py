from pymongo import MongoClient


def test_engine_connected(mongo_engine: MongoClient) -> None:
    server_info = mongo_engine.server_info()
    print(server_info)
    assert server_info
    assert server_info["ok"] == 1.0
