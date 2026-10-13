"""Storage adapter: same keys and behaviour on local disk and Azure Blob, no path escapes."""
import pytest
from azure.core.exceptions import ResourceNotFoundError

from services import file_storage, storage_service
from services.file_storage import (
    AzureBlobFileStore, EmergentObjectStore, FileStorage, InvalidKeyError, LocalFileStore,
    uploads_key_from_legacy_path, validate_key,
)


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../secret", "a/../../b", "a//b", "a\\b", "kyc/\x00.enc", "a/"])
def test_keys_that_escape_the_area_are_rejected(key):
    with pytest.raises(InvalidKeyError):
        validate_key(key)


def test_normal_keys_are_kept_as_is():
    assert validate_key("airyatra/vault/u1/doc_1/passport scan.pdf") == "airyatra/vault/u1/doc_1/passport scan.pdf"


async def test_local_store_round_trip(tmp_path):
    store = LocalFileStore(tmp_path)
    assert await store.put("profile_photos/u1.jpg", b"jpeg") == "profile_photos/u1.jpg"
    assert (tmp_path / "profile_photos" / "u1.jpg").read_bytes() == b"jpeg"
    assert await store.get("profile_photos/u1.jpg") == (b"jpeg", "image/jpeg")
    assert await store.exists("profile_photos/u1.jpg")
    assert await store.delete("profile_photos/u1.jpg") is True
    assert await store.delete("profile_photos/u1.jpg") is False
    with pytest.raises(FileNotFoundError):
        await store.get("profile_photos/u1.jpg")


async def test_local_store_refuses_traversal(tmp_path):
    (tmp_path / "secret.txt").write_text("x")
    store = LocalFileStore(tmp_path / "uploads")
    with pytest.raises(InvalidKeyError):
        await store.get("../secret.txt")


class FakeDownloader:
    def __init__(self, data, content_type):
        self.data = data
        self.properties = type("P", (), {"content_settings": type("C", (), {"content_type": content_type})()})()

    async def readall(self):
        return self.data


class FakeContainer:
    def __init__(self):
        self.blobs = {}

    async def upload_blob(self, name, data, overwrite, content_settings):
        assert overwrite is True
        self.blobs[name] = (data, content_settings.content_type)

    async def download_blob(self, name):
        if name not in self.blobs:
            raise ResourceNotFoundError("missing")
        return FakeDownloader(*self.blobs[name])

    async def delete_blob(self, name):
        if self.blobs.pop(name, None) is None:
            raise ResourceNotFoundError("missing")

    def get_blob_client(self, name):
        container = self

        class Client:
            async def exists(self):
                return name in container.blobs
        return Client()


class FakeService:
    def __init__(self):
        self.containers = {}

    def get_container_client(self, name):
        return self.containers.setdefault(name, FakeContainer())


async def test_blob_store_round_trip_keeps_keys_and_content_type():
    service = FakeService()
    store = AzureBlobFileStore("https://acct.blob.core.windows.net", "documents", service_client=service)
    key = "airyatra/vault/u1/doc_1/licence.pdf"
    assert await store.put(key, b"%PDF", "application/pdf") == key
    assert service.containers["documents"].blobs[key] == (b"%PDF", "application/pdf")
    assert await store.get(key) == (b"%PDF", "application/pdf")
    assert await store.exists(key)
    assert await store.delete(key) is True
    assert await store.delete(key) is False
    with pytest.raises(FileNotFoundError):
        await store.get(key)
    with pytest.raises(InvalidKeyError):
        await store.put("../x", b"")


def test_provider_selects_backends(tmp_path):
    legacy = FileStorage("legacy", str(tmp_path))
    assert isinstance(legacy.area("objects"), EmergentObjectStore)
    assert isinstance(legacy.area("uploads"), LocalFileStore)
    assert legacy.area("kyc").root == tmp_path / "secure_uploads" / "kyc"
    assert legacy.area("uploads").root == tmp_path / "uploads"
    assert FileStorage("local", str(tmp_path)).area("objects").root == tmp_path / "object_store"
    azure = FileStorage("azure_blob", str(tmp_path), "https://acct.blob.core.windows.net")
    assert {azure.area(a).container.container_name for a in ("uploads", "kyc", "objects")} == {"uploads", "kyc", "documents"}


def test_provider_configuration_errors(tmp_path):
    with pytest.raises(ValueError, match="STORAGE_PROVIDER"):
        FileStorage("s3", str(tmp_path))
    with pytest.raises(ValueError, match="AZURE_STORAGE_ACCOUNT_URL"):
        FileStorage("azure_blob", str(tmp_path))
    with pytest.raises(ValueError):
        FileStorage("local", str(tmp_path)).area("public")


def test_legacy_paths_map_to_upload_keys():
    assert uploads_key_from_legacy_path("/app/uploads/village_documents/p1/noc.pdf") == "village_documents/p1/noc.pdf"
    assert uploads_key_from_legacy_path("/etc/passwd") is None
    assert uploads_key_from_legacy_path(None) is None


@pytest.fixture
def local_storage(tmp_path, monkeypatch):
    storage = FileStorage("local", str(tmp_path))
    monkeypatch.setattr(file_storage, "_storage", storage)
    return storage


async def test_object_storage_api_unchanged_on_new_backends(local_storage):
    stored = await storage_service.put_object("airyatra/exchange/exi-1.jpg", b"img", "image/jpeg")
    assert stored["path"] == "airyatra/exchange/exi-1.jpg"
    assert await storage_service.get_object(stored["path"]) == (b"img", "image/jpeg")


async def test_legacy_object_storage_still_calls_emergent(tmp_path, monkeypatch):
    calls = []

    async def fake_put(path, data, content_type):
        calls.append(path)
        return {"path": path, "url": "https://emergent.example/obj"}

    monkeypatch.setattr(file_storage, "_storage", FileStorage("legacy", str(tmp_path)))
    monkeypatch.setattr(storage_service.emergent_object_store, "put_object", fake_put)
    result = await storage_service.put_object("airyatra/vault/u/f/a.pdf", b"x", "application/pdf")
    assert calls == ["airyatra/vault/u/f/a.pdf"] and result["url"] == "https://emergent.example/obj"
