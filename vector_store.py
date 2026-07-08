import os

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

import db

_CHROMA_PATH = os.environ.get("CHROMA_PATH", "data/chroma")
_client = None
_incidents_col = None
_conditions_col = None


def _get_collections():
    global _client, _incidents_col, _conditions_col
    if _client is None:
        ef = DefaultEmbeddingFunction()
        _client = chromadb.PersistentClient(path=_CHROMA_PATH)
        _incidents_col = _client.get_or_create_collection("incidents", embedding_function=ef)
        _conditions_col = _client.get_or_create_collection("camera_conditions", embedding_function=ef)
    return _incidents_col, _conditions_col


def index_incidents() -> int:
    incidents_col, _ = _get_collections()
    incidents = db.all_incidents()
    if not incidents:
        return 0
    docs = [
        f"{inc['description']} at {inc['location']} ({inc['main_route']}) since {inc['start_date']}"
        for inc in incidents
    ]
    ids = [str(inc["id"]) for inc in incidents]
    incidents_col.upsert(documents=docs, ids=ids)
    return len(docs)


def index_camera_conditions() -> int:
    _, conditions_col = _get_collections()
    snapshots = db.all_snapshots()
    if not snapshots:
        return 0
    docs = [
        f"Camera {s['camera_id']} at {s['captured_at']}: {s['label']} "
        f"(confidence {s['confidence']:.2f}) - {s['notes']}"
        for s in snapshots
    ]
    ids = [f"{s['camera_id']}_{s['captured_at']}" for s in snapshots]
    conditions_col.upsert(documents=docs, ids=ids)
    return len(docs)


def search(query: str, n_results: int = 5) -> dict:
    incidents_col, conditions_col = _get_collections()
    combined: list = []
    for col in (incidents_col, conditions_col):
        try:
            res = col.query(query_texts=[query], n_results=n_results)
            combined.extend(res.get("documents", [[]])[0])
        except Exception:
            pass
    return {"documents": [combined[:n_results]]}


if __name__ == "__main__":
    from config import Config
    cfg = Config()
    db.init_db(cfg.db_path)
    print(f"Indexed {index_incidents()} incidents and {index_camera_conditions()} camera conditions.")
