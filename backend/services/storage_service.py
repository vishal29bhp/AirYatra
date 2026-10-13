"""Object storage for the document vault and exchange images.

Same functions and return shapes as before. With ``STORAGE_PROVIDER=legacy`` (the default) calls go
to the Emergent object store exactly as today; otherwise the bytes go to the backend chosen in
``services/file_storage.py``. Keys are unchanged, so ``storage_path`` values already in MongoDB keep
working after migration.
"""
from typing import Tuple

from services import emergent_object_store
from services.file_storage import file_store, get_file_storage


def _legacy() -> bool:
    return get_file_storage().provider == "legacy"


async def put_object(path: str, data: bytes, content_type: str) -> dict:
    if _legacy():
        return await emergent_object_store.put_object(path, data, content_type)
    key = await file_store("objects").put(path, data, content_type)
    return {"path": key, "size": len(data)}


async def get_object(path: str) -> Tuple[bytes, str]:
    if _legacy():
        return await emergent_object_store.get_object(path)
    return await file_store("objects").get(path)
