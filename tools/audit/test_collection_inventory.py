"""Unit tests for tools/audit/collection_inventory.py (synthetic snippets only)."""
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import collection_inventory as ci  # noqa: E402


def run(src: str):
    inv = ci.analyse_source(textwrap.dedent(src), "snippet.py")
    return inv.to_json("snippet")


def test_attribute_access_and_operations():
    out = run("""
        from database import get_database
        async def f():
            db = get_database()
            await db.bookings.find_one({"id": "x"})
            await db.bookings.insert_one({"id": "1"})
            await db.users.count_documents({})
    """)
    c = out["collections"]
    assert set(c) == {"bookings", "users"}
    assert c["bookings"]["operations"] == {"find_one": 1, "insert_one": 1}
    assert c["bookings"]["files"] == {"snippet.py": [5, 6]}


def test_subscript_get_collection_and_alias():
    out = run("""
        async def f(database):
            await database["audit_logs"].insert_one({"action": "login"})
            coll = database.get_collection("sessions")
            await coll.delete_many({"user_id": "u"})
        class Repo:
            def __init__(self, db):
                self.collection = db.call_logs
            async def get(self, sid):
                return await self.collection.find_one({"call_sid": sid})
    """)
    c = out["collections"]
    assert {"audit_logs", "sessions", "call_logs"} <= set(c)
    assert c["sessions"]["filter_keys"] == {"user_id": 1}
    assert c["call_logs"]["filter_keys"] == {"call_sid": 1}


def test_depends_get_database_root():
    out = run("""
        from fastapi import Depends
        async def route(conn=Depends(get_database)):
            return await conn.pilots.find({"status": "active"}).to_list(10)
    """)
    assert "pilots" in out["collections"]
    assert out["collections"]["pilots"]["fields"]["status"]["samples"] == ["active"]


def test_non_root_attributes_ignored():
    out = run("""
        import requests
        def g(session, db):
            session.items.find_one({})
            db.client.close()
            db.command("ping")
    """)
    assert out["collections"] == {}


def test_insert_value_kinds_iso_vs_datetime_uuid_float():
    out = run("""
        import uuid
        from datetime import datetime
        async def f(db, amount):
            now = datetime.utcnow()
            doc = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": now,
                "amount": float(amount),
                "status": "pending",
            }
            doc["currency"] = "INR"
            await db.payments.insert_one(doc)
    """)
    f = out["collections"]["payments"]["fields"]
    assert f["id"]["kinds"] == {"uuid_string": 1}
    assert f["created_at"]["kinds"] == {"iso_string": 1}
    assert f["updated_at"]["kinds"] == {"datetime": 1}
    assert f["amount"]["kinds"] == {"float": 1}
    assert f["status"]["samples"] == ["pending"]
    assert "currency" in f


def test_update_set_keys_and_operators():
    out = run("""
        async def f(db, bid):
            await db.bookings.update_one(
                {"id": bid, "$or": [{"status": "pending"}, {"status": {"$in": ["held", "draft"]}}]},
                {"$set": {"status": "confirmed", "paid_at": datetime.utcnow().isoformat()},
                 "$inc": {"version": 1}, "$push": {"history": {"x": 1}}},
            )
    """)
    c = out["collections"]["bookings"]
    assert c["set_keys"] == {"status": 1, "paid_at": 1}
    assert c["update_operators"] == {"$set": 1, "$inc": 1, "$push": 1}
    assert c["filter_keys"]["id"] == 1 and c["filter_keys"]["status"] == 2
    assert set(c["fields"]["status"]["samples"]) == {"pending", "held", "draft", "confirmed"}
    assert c["fields"]["version"]["sources"] == {"inc": 1}


def test_sort_keys_chain_and_kwarg():
    out = run("""
        async def f(db):
            await db.notifications.find({"user_id": 1}).skip(0).limit(5).sort("created_at", -1).to_list(5)
            await db.audit_logs.find({}).sort([("timestamp", -1), ("user_id", 1)]).to_list(5)
            await db.users.find_one({}, sort=[("created_at", -1)])
    """)
    c = out["collections"]
    assert c["notifications"]["sort_keys"] == {"created_at": 1}
    assert c["audit_logs"]["sort_keys"] == {"timestamp": 1, "user_id": 1}
    assert c["users"]["sort_keys"] == {"created_at": 1}


def test_create_index_and_create_indexes():
    out = run("""
        from pymongo import IndexModel
        async def f(db):
            await db.users.create_index("email", unique=True)
            await db.bookings.create_index([("status", 1), ("created_at", -1)], name="sc")
            await db.sessions.create_indexes([IndexModel([("expires_at", 1)], expireAfterSeconds=0)])
    """)
    idx = {(i["collection"], i["call"]): i for i in out["indexes"]}
    assert idx[("users", "create_index")]["keys"] == [["email", 1]]
    assert idx[("users", "create_index")]["options"] == {"unique": "True"}
    assert idx[("bookings", "create_index")]["keys"] == [["status", "1"], ["created_at", "-1"]]
    assert idx[("sessions", "create_indexes")]["options"] == {"expireAfterSeconds": "0"}


def test_declared_index_table():
    out = run("""
        INDEXES = {
            "users": [{"keys": [("email", 1)], "unique": True, "name": "email_unique"}],
        }
    """)
    assert out["indexes"][0]["collection"] == "users"
    assert out["indexes"][0]["options"]["unique"] == "True"


def test_aggregate_match_sort_and_lookup():
    out = run("""
        async def f(db):
            await db.bookings.aggregate([
                {"$match": {"operator_id": "o"}},
                {"$lookup": {"from": "operators", "localField": "operator_id", "foreignField": "id", "as": "op"}},
                {"$sort": {"created_at": -1}},
            ]).to_list(None)
    """)
    c = out["collections"]
    assert c["bookings"]["filter_keys"] == {"operator_id": 1}
    assert c["bookings"]["sort_keys"] == {"created_at": 1}
    assert c["operators"]["operations"] == {"lookup_from": 1}


def test_model_hint_and_dynamic_access():
    out = run("""
        async def f(db, name, data: dict):
            booking = Booking(id="1")
            await db.bookings.insert_one(booking.dict())
            await db[name].find_one({})
            await db.users.find_one(data)
    """)
    assert out["collections"]["bookings"]["insert_model_hints"] == {"Booking": 1}
    assert out["dynamic_accesses"][0]["expr"] == "db[name]"
    assert out["suspicious_query_inputs"][0]["collection"] == "users"


def test_pydantic_models_and_tree(tmp_path):
    pkg = tmp_path / "backend"
    pkg.mkdir()
    (pkg / "models.py").write_text(textwrap.dedent("""
        from enum import Enum
        from pydantic import BaseModel
        class Status(str, Enum):
            PENDING = "pending"
        class Base(BaseModel):
            id: str
        class Booking(Base):
            amount: float = 0.0
        class NotAModel:
            x: int = 1
    """))
    (pkg / "broken.py").write_text("def x(:\n")
    out = ci.analyse_tree(str(pkg), base=str(tmp_path))
    assert {"Status", "Base", "Booking"} <= set(out["pydantic_models"])
    assert "NotAModel" not in out["pydantic_models"]
    assert out["pydantic_models"]["Booking"]["fields"]["amount"] == {"type": "float", "default": "0.0"}
    assert out["parse_errors"][0]["file"].endswith("broken.py")
    json.dumps(out)  # serialisable


def test_cli_writes_file(tmp_path):
    pkg = tmp_path / "backend"
    pkg.mkdir()
    (pkg / "a.py").write_text("async def f(db):\n    await db.x.find_one({})\n")
    target = tmp_path / "out.json"
    assert ci.main(["--root", str(pkg), "-o", str(target)]) == 0
    data = json.loads(target.read_text())
    assert "x" in data["collections"]


def test_insert_copy_dict_and_model_dump_hint():
    out = run("""
        async def register(db, user_data: UserCreate):
            user_dict = user_data.model_dump()
            user_dict["id"] = str(uuid.uuid4())
            user_dict["created_at"] = datetime.utcnow().isoformat()
            await db.users.insert_one(user_dict.copy())
            doc = {"a": 1}
            await db.logs.insert_one(dict(doc))
    """)
    u = out["collections"]["users"]
    assert set(u["fields"]) == {"id", "created_at"}
    assert u["insert_model_hints"] == {"UserCreate": 1}
    assert "a" in out["collections"]["logs"]["fields"]


def test_raw_param_dict_into_set_and_insert_is_flagged():
    out = run("""
        async def upd(db, ticket_id: str, update_data: dict):
            update_data["updated_at"] = "x"
            await db.tickets.update_one({"id": ticket_id}, {"$set": update_data})
            await db.leads.insert_one(update_data)
        async def safe(db, body: TicketUpdate):
            await db.tickets.update_one({"id": "1"}, {"$set": body.dict()})
    """)
    kinds = sorted((s["collection"], s["kind"]) for s in out["suspicious_query_inputs"])
    assert kinds == [("leads", "insert"), ("tickets", "$set")]
