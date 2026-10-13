"""File storage behind one interface, so uploads survive restarts and work across replicas.

Three storage areas are used by the app. Each keeps the keys (and so the URLs and paths stored in
MongoDB) it has today; only where the bytes live changes:

==========  ==============================================  ===================  =========================
Area        Key example                                     Local disk           Azure Blob container
==========  ==============================================  ===================  =========================
uploads     ``attendance_selfies/<file>.jpg``                ``<root>/uploads``   ``uploads``
kyc         ``<user>_<type>_<id>.pdf.enc``                   ``<root>/secure_uploads/kyc``  ``kyc``
objects     ``airyatra/vault/<owner>/<file_id>/<name>``      Emergent object store (legacy) or ``<root>/object_store``  ``documents``
==========  ==============================================  ===================  =========================

``STORAGE_PROVIDER`` picks the backend: ``legacy`` (default, exactly today's behaviour), ``local``
(disk only, for development without Emergent) or ``azure_blob`` (production on Azure).
"""
from __future__ import annotations

import asyncio
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import Dict, Optional, Tuple

DEFAULT_CONTENT_TYPE = "application/octet-stream"

AREAS = ("uploads", "kyc", "objects")
BLOB_CONTAINERS = {"uploads": "uploads", "kyc": "kyc", "objects": "documents"}
LOCAL_SUBDIRS = {"uploads": "uploads", "kyc": "secure_uploads/kyc", "objects": "object_store"}
PROVIDERS = ("legacy", "local", "azure_blob")


class InvalidKeyError(ValueError):
    """The key would escape its storage area (absolute path, ``..``, empty)."""


def validate_key(key: str) -> str:
    """Return a normalised relative POSIX key or raise ``InvalidKeyError``."""
    if not key or "\\" in key or "\x00" in key:
        raise InvalidKeyError("invalid file key")
    path = PurePosixPath(key)
    if path.is_absolute() or any(part in ("..", "") for part in key.split("/")):
        raise InvalidKeyError("invalid file key")
    return str(path)


def guess_content_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or DEFAULT_CONTENT_TYPE


class FileStore(ABC):
    """One storage area. Keys are relative POSIX paths; ``get`` raises ``FileNotFoundError``."""

    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        """Store ``data`` under ``key`` and return the key."""

    @abstractmethod
    async def get(self, key: str) -> Tuple[bytes, str]:
        """Return ``(content, content_type)``."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete ``key``; return False if it did not exist."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...


class LocalFileStore(FileStore):
    """Files under a folder on local disk (today's behaviour)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / validate_key(key)

    async def put(self, key, data, content_type=None):
        path = self._path(key)

        def _write():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        return validate_key(key)

    async def get(self, key):
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return await asyncio.to_thread(path.read_bytes), guess_content_type(key)

    async def delete(self, key):
        path = self._path(key)
        if not path.is_file():
            return False
        await asyncio.to_thread(path.unlink)
        return True

    async def exists(self, key):
        return self._path(key).is_file()


class AzureBlobFileStore(FileStore):
    """One private Blob container, reached with the app's managed identity (no keys)."""

    def __init__(self, account_url: str, container: str, credential=None, service_client=None):
        if service_client is None:
            from azure.identity.aio import DefaultAzureCredential
            from azure.storage.blob.aio import BlobServiceClient

            service_client = BlobServiceClient(account_url, credential=credential or DefaultAzureCredential())
        self.container = service_client.get_container_client(container)

    async def put(self, key, data, content_type=None):
        from azure.storage.blob import ContentSettings

        key = validate_key(key)
        await self.container.upload_blob(
            key, data, overwrite=True,
            content_settings=ContentSettings(content_type=content_type or guess_content_type(key)),
        )
        return key

    async def get(self, key):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            downloader = await self.container.download_blob(validate_key(key))
        except ResourceNotFoundError:
            raise FileNotFoundError(key) from None
        content_type = downloader.properties.content_settings.content_type or guess_content_type(key)
        return await downloader.readall(), content_type

    async def delete(self, key):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            await self.container.delete_blob(validate_key(key))
            return True
        except ResourceNotFoundError:
            return False

    async def exists(self, key):
        return await self.container.get_blob_client(validate_key(key)).exists()


class EmergentObjectStore(FileStore):
    """The Emergent object store used today for the document vault and exchange images."""

    def __init__(self, legacy_module=None):
        if legacy_module is None:
            from services import emergent_object_store as legacy_module
        self._legacy = legacy_module

    async def put(self, key, data, content_type=None):
        result = await self._legacy.put_object(key, data, content_type or guess_content_type(key))
        return result.get("path", key)

    async def get(self, key):
        import requests

        try:
            return await self._legacy.get_object(key)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise FileNotFoundError(key) from None
            raise

    async def delete(self, key):
        raise NotImplementedError("the Emergent object store has no delete API")

    async def exists(self, key):
        try:
            await self.get(key)
            return True
        except FileNotFoundError:
            return False


class FileStorage:
    """Builds and caches one ``FileStore`` per area from settings."""

    def __init__(self, provider: str, upload_root: str, account_url: str = ""):
        if provider not in PROVIDERS:
            raise ValueError(f"STORAGE_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
        if provider == "azure_blob" and not account_url:
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required when STORAGE_PROVIDER=azure_blob")
        self.provider, self.upload_root, self.account_url = provider, Path(upload_root), account_url
        self._stores: Dict[str, FileStore] = {}
        self._credential = None

    def area(self, name: str) -> FileStore:
        if name not in AREAS:
            raise ValueError(f"unknown storage area {name!r}")
        if name not in self._stores:
            self._stores[name] = self._build(name)
        return self._stores[name]

    def _build(self, name: str) -> FileStore:
        if self.provider == "azure_blob":
            if self._credential is None:
                from azure.identity.aio import DefaultAzureCredential

                self._credential = DefaultAzureCredential()
            return AzureBlobFileStore(self.account_url, BLOB_CONTAINERS[name], credential=self._credential)
        if self.provider == "legacy" and name == "objects":
            return EmergentObjectStore()
        return LocalFileStore(self.upload_root / LOCAL_SUBDIRS[name])


_storage: Optional[FileStorage] = None


def get_file_storage() -> FileStorage:
    global _storage
    if _storage is None:
        from config import settings

        _storage = FileStorage(settings.storage_provider, settings.upload_root, settings.azure_storage_account_url)
    return _storage


def file_store(area: str) -> FileStore:
    return get_file_storage().area(area)


LEGACY_UPLOADS_PREFIX = "/app/uploads/"


def uploads_key_from_legacy_path(file_path: str) -> Optional[str]:
    """Documents store absolute ``/app/uploads/...`` paths; turn one into an ``uploads`` key."""
    if file_path and file_path.startswith(LEGACY_UPLOADS_PREFIX):
        return file_path[len(LEGACY_UPLOADS_PREFIX):]
    return None
