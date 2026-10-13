"""Uploads go through the storage adapter: KYC files are encrypted at rest, public uploads keep their URLs."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services import file_storage
from services.file_storage import FileStorage

USER = {"id": "user-1", "email": "c@example.com", "roles": ["customer"]}
PDF = b"%PDF-1.7 aadhaar scan"


@pytest.fixture
def storage(tmp_path, monkeypatch):
    storage = FileStorage("local", str(tmp_path))
    monkeypatch.setattr(file_storage, "_storage", storage)
    return storage


@pytest.fixture
def kyc_client(storage, mock_db, monkeypatch):
    from middleware import get_current_user
    from routes import customer_kyc_routes

    monkeypatch.setattr(customer_kyc_routes, "get_database", lambda: mock_db)
    app = FastAPI()
    app.include_router(customer_kyc_routes.router)
    app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app), mock_db


async def test_kyc_upload_download_delete_round_trip(kyc_client, storage):
    client, db = kyc_client
    response = client.post("/customer/kyc-documents/upload",
                           files={"file": ("aadhaar.pdf", PDF, "application/pdf")},
                           data={"document_type": "AADHAR", "document_number": "1234 5678 9012"})
    assert response.status_code == 200, response.text

    doc = await db.customer_kyc_documents.find_one({"user_id": "user-1"})
    stored_name = doc["stored_filename"]
    assert stored_name.startswith("AADHAR_user-1_") and stored_name.endswith(".pdf.enc")
    on_disk = (storage.upload_root / "secure_uploads" / "kyc" / stored_name).read_bytes()
    assert PDF not in on_disk  # encrypted at rest

    download = client.get(f"/customer/kyc-documents/download/{doc['id']}")
    assert download.status_code == 200 and download.content == PDF

    assert client.delete(f"/customer/kyc-documents/{doc['id']}").status_code == 200
    assert not await storage.area("kyc").exists(stored_name)


async def test_kyc_download_of_missing_file_is_404(kyc_client):
    client, db = kyc_client
    await db.customer_kyc_documents.insert_one({"id": "kyc_1", "user_id": "user-1", "stored_filename": "../../etc/passwd"})
    assert client.get("/customer/kyc-documents/download/kyc_1").status_code == 404


async def test_public_uploads_served_from_storage_with_same_urls(server, storage):
    await storage.area("uploads").put("profile_photos/user-1_ab.jpg", b"jpeg-bytes")
    client = TestClient(server.app)
    response = client.get("/api/uploads/profile_photos/user-1_ab.jpg")
    assert response.status_code == 200
    assert response.content == b"jpeg-bytes" and response.headers["content-type"] == "image/jpeg"
    assert client.get("/api/uploads/profile_photos/nope.jpg").status_code == 404


async def test_public_uploads_never_serve_kyc_files(server, storage):
    await storage.area("kyc").put("PAN_user-1_x.pdf.enc", b"secret")
    client = TestClient(server.app)
    for path in ("/api/uploads/../secure_uploads/kyc/PAN_user-1_x.pdf.enc",
                 "/api/uploads/%2e%2e/secure_uploads/kyc/PAN_user-1_x.pdf.enc"):
        assert client.get(path).status_code == 404
