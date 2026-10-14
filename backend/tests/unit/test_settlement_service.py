"""Unit tests for operator settlement automation (services/settlement_service.py).

Settlement = gross bookings − commission − 18% GST on commission.
Reference period: bookings worth ₹1,00,000 + ₹50,000 = ₹1,50,000 gross.
  commission 10%        = 15,000
  GST on commission 18% =  2,700
  net payable           = 1,50,000 − 15,000 − 2,700 = 1,32,300
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import settlement_service as settlement_module
from services.settlement_service import SettlementAutomationService

START = "2026-10-01T00:00:00+00:00"
END = "2026-10-07T23:59:59+00:00"


@pytest.fixture
def service():
    return SettlementAutomationService()


async def seed_bookings(db, operator_id="op-1", inside="2026-10-03T10:00:00+00:00"):
    await db.bookings.insert_many([
        {"id": "bk-1", "operator_id": operator_id, "status": "completed", "completed_at": inside, "total_amount": 100000},
        # No total_amount: falls back to estimated_price
        {"id": "bk-2", "operator_id": operator_id, "status": "completed", "completed_at": inside, "estimated_price": 50000},
        # Excluded: not completed, outside the period, other operator
        {"id": "bk-3", "operator_id": operator_id, "status": "confirmed", "completed_at": inside, "total_amount": 999999},
        {"id": "bk-4", "operator_id": operator_id, "status": "completed",
         "completed_at": "2026-09-30T10:00:00+00:00", "total_amount": 999999},
        {"id": "bk-5", "operator_id": "op-other", "status": "completed", "completed_at": inside, "total_amount": 999999},
    ])


async def seed_operator(db, operator_id="op-1", **extra):
    await db.operators.insert_one({
        "id": operator_id, "user_id": f"user-{operator_id}", "company_name": "Sky Rides Pvt Ltd",
        "bank_account": {"account_number": "123456789", "ifsc": "HDFC0001234"},
        "contact_email": "ops@skyrides.example", "status": "active", **extra,
    })


# ==================== calculate_operator_settlement ====================

async def test_settlement_uses_default_ten_percent_commission(service, mock_db):
    await seed_bookings(mock_db)
    result = await service.calculate_operator_settlement(mock_db, "op-1", START, END)
    assert result["total_bookings"] == 2
    assert sorted(result["booking_ids"]) == ["bk-1", "bk-2"]
    assert result["gross_amount"] == 150000
    assert result["commission_rate"] == 10
    assert result["commission_amount"] == 15000
    assert result["gst_on_commission"] == 2700
    assert result["net_payable"] == 132300


async def test_settlement_uses_configured_commission_rate(service, mock_db):
    # 12%: commission 18,000; GST 3,240; net 1,50,000 − 18,000 − 3,240 = 1,28,760
    await mock_db.platform_settings.insert_one({"type": "commission", "commission_rate": 12})
    await seed_bookings(mock_db)
    result = await service.calculate_operator_settlement(mock_db, "op-1", START, END)
    assert result["commission_amount"] == 18000
    assert result["gst_on_commission"] == 3240
    assert result["net_payable"] == 128760


async def test_settlement_rounds_to_paise(service, mock_db):
    # 999.99 gross: commission 99.999 → 100.0; GST 17.99982 → 18.0; net 999.99 − 99.999 − 17.99982 = 881.99118 → 881.99
    await mock_db.bookings.insert_one({"id": "bk-x", "operator_id": "op-1", "status": "completed",
                                       "completed_at": "2026-10-02T00:00:00+00:00", "total_amount": 999.99})
    result = await service.calculate_operator_settlement(mock_db, "op-1", START, END)
    assert result["commission_amount"] == 100.0
    assert result["gst_on_commission"] == 18.0
    assert result["net_payable"] == 881.99


async def test_no_completed_bookings_gives_zero_settlement(service, mock_db):
    result = await service.calculate_operator_settlement(mock_db, "op-1", START, END)
    assert result["total_bookings"] == 0
    assert result["net_payable"] == 0
    assert result["booking_ids"] == []


# ==================== create_settlement_record ====================

async def _calculated(service, db):
    await seed_bookings(db)
    return await service.calculate_operator_settlement(db, "op-1", START, END)


async def test_settlement_record_is_created_pending_with_operator_details(service, mock_db):
    await seed_operator(mock_db)
    data = await _calculated(service, mock_db)
    result = await service.create_settlement_record(mock_db, data)
    assert result["status"] == "created"
    stored = await mock_db.settlements.find_one({"id": result["settlement"]["id"]})
    assert stored["status"] == "pending"
    assert stored["net_payable"] == 132300
    assert stored["operator_name"] == "Sky Rides Pvt Ltd"
    assert stored["bank_details"]["ifsc"] == "HDFC0001234"
    assert stored["settlement_number"].startswith("STL-")
    assert stored["paid_at"] is None
    note = await mock_db.in_app_notifications.find_one({"type": "settlement_created"})
    assert note["message"] == "Settlement of ₹132,300.00 is ready for processing"
    assert note["data"] == {"settlement_id": stored["id"]}


async def test_settlement_created_notification_is_addressed_to_operator_user(service, mock_db):
    await seed_operator(mock_db)
    data = await _calculated(service, mock_db)
    await service.create_settlement_record(mock_db, data)
    note = await mock_db.in_app_notifications.find_one({"type": "settlement_created"})
    assert note["user_id"] == "user-op-1"


async def test_duplicate_settlement_for_same_period_is_not_created(service, mock_db):
    await seed_operator(mock_db)
    data = await _calculated(service, mock_db)
    first = await service.create_settlement_record(mock_db, data)
    second = await service.create_settlement_record(mock_db, dict(data))
    assert second["status"] == "exists"
    assert second["settlement"]["id"] == first["settlement"]["id"]
    assert await mock_db.settlements.count_documents({}) == 1


async def test_settlement_for_unknown_operator_has_no_notification(service, mock_db):
    data = await _calculated(service, mock_db)
    result = await service.create_settlement_record(mock_db, data)
    assert result["settlement"]["operator_name"] == "Unknown"
    assert result["settlement"]["bank_details"] is None
    assert await mock_db.in_app_notifications.count_documents({}) == 0


# ==================== manual settlement ====================

async def test_manual_settlement_without_bookings_fails(service, mock_db):
    result = await service.process_manual_settlement(mock_db, "op-1", START, END)
    assert result["success"] is False
    assert result["settlement_data"]["total_bookings"] == 0
    assert await mock_db.settlements.count_documents({}) == 0


async def test_manual_settlement_creates_record(service, mock_db):
    await seed_operator(mock_db)
    await seed_bookings(mock_db)
    result = await service.process_manual_settlement(mock_db, "op-1", START, END)
    assert result["success"] is True
    assert result["message"] == "Settlement created for ₹132,300.00"
    assert result["settlement"]["net_payable"] == 132300


# ==================== mark_settlement_paid ====================

async def test_mark_paid_unknown_settlement(service, mock_db):
    result = await service.mark_settlement_paid(mock_db, "nope", "UTR1", "admin-1")
    assert result == {"success": False, "message": "Settlement not found"}


async def test_mark_paid_completes_settlement_and_notifies_operator(service, mock_db):
    await seed_operator(mock_db)
    await mock_db.settlements.insert_one(
        {"id": "st-1", "operator_id": "op-1", "status": "pending", "net_payable": 132300})
    result = await service.mark_settlement_paid(mock_db, "st-1", "UTR123", "admin-1")
    assert result["success"] is True
    stored = await mock_db.settlements.find_one({"id": "st-1"})
    assert stored["status"] == "completed"
    assert stored["payment_reference"] == "UTR123"
    assert stored["paid_by"] == "admin-1"
    assert stored["paid_at"]
    note = await mock_db.in_app_notifications.find_one({"type": "settlement_paid"})
    assert note["user_id"] == "user-op-1"
    assert "₹132,300.00" in note["message"] and "UTR123" in note["message"]


async def test_mark_paid_twice_is_rejected(service, mock_db):
    await mock_db.settlements.insert_one(
        {"id": "st-1", "operator_id": "op-1", "status": "completed", "payment_reference": "UTR-OLD",
         "net_payable": 100})
    result = await service.mark_settlement_paid(mock_db, "st-1", "UTR-NEW", "admin-1")
    assert result["success"] is False
    assert (await mock_db.settlements.find_one({"id": "st-1"}))["payment_reference"] == "UTR-OLD"


async def test_mark_paid_without_operator_skips_notification(service, mock_db):
    await mock_db.settlements.insert_one({"id": "st-1", "operator_id": "gone", "status": "pending", "net_payable": 1})
    assert (await service.mark_settlement_paid(mock_db, "st-1", "UTR1", "admin"))["success"] is True
    assert await mock_db.in_app_notifications.count_documents({}) == 0


# ==================== pending list ====================

async def test_pending_settlements_newest_first_and_limited(service, mock_db):
    await mock_db.settlements.insert_many([
        {"id": "a", "status": "pending", "created_at": "2026-10-01"},
        {"id": "b", "status": "processing", "created_at": "2026-10-03"},
        {"id": "c", "status": "completed", "created_at": "2026-10-04"},
        {"id": "d", "status": "pending", "created_at": "2026-10-02"},
    ])
    assert [s["id"] for s in await service.get_pending_settlements(mock_db)] == ["b", "d", "a"]
    assert [s["id"] for s in await service.get_pending_settlements(mock_db, limit=1)] == ["b"]


# ==================== weekly run ====================

class FixedDatetime(datetime):
    """Wednesday 2026-10-14 09:30 UTC → period is Mon 2026-10-05 to Mon 2026-10-12."""
    current = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current


@pytest.fixture
def frozen_time(monkeypatch):
    monkeypatch.setattr(settlement_module, "datetime", FixedDatetime)
    return FixedDatetime


async def test_weekly_run_settles_active_operators_for_previous_week(service, mock_db, frozen_time):
    await seed_operator(mock_db, "op-1")
    await seed_operator(mock_db, "op-2")                      # active, no bookings → skipped
    await seed_operator(mock_db, "op-3", status="suspended")  # not active → ignored
    await seed_bookings(mock_db, "op-1", inside="2026-10-08T12:00:00+00:00")
    await seed_bookings(mock_db, "op-3", inside="2026-10-08T12:00:00+00:00")

    results = await service.process_weekly_settlements(mock_db)

    assert results["period_start"] == "2026-10-05T00:00:00+00:00"
    assert results["period_end"] == "2026-10-12T00:00:00+00:00"
    assert results["processed_count"] == 1
    assert results["skipped_count"] == 1
    assert results["total_amount"] == 132300
    assert results["settlements"] == [{"operator_name": "Sky Rides Pvt Ltd", "amount": 132300, "bookings": 2}]
    assert await mock_db.settlements.count_documents({"operator_id": "op-1"}) == 1
    assert await mock_db.settlements.count_documents({"operator_id": "op-3"}) == 0
    run = await mock_db.settlement_runs.find_one({"run_type": "weekly_auto"})
    assert run["results"]["processed_count"] == 1


async def test_weekly_run_twice_does_not_double_settle(service, mock_db, frozen_time):
    await seed_operator(mock_db, "op-1")
    await seed_bookings(mock_db, "op-1", inside="2026-10-08T12:00:00+00:00")
    await service.process_weekly_settlements(mock_db)
    second = await service.process_weekly_settlements(mock_db)
    assert second["processed_count"] == 0
    assert second["skipped_count"] == 1
    assert await mock_db.settlements.count_documents({}) == 1


async def test_weekly_run_continues_after_one_operator_fails(service, mock_db, frozen_time, monkeypatch):
    await seed_operator(mock_db, "op-bad")
    await seed_operator(mock_db, "op-1")
    await seed_bookings(mock_db, "op-1", inside="2026-10-08T12:00:00+00:00")
    real = service.calculate_operator_settlement

    async def flaky(db, operator_id, start, end):
        if operator_id == "op-bad":
            raise RuntimeError("boom")
        return await real(db, operator_id, start, end)

    monkeypatch.setattr(service, "calculate_operator_settlement", flaky)
    results = await service.process_weekly_settlements(mock_db)
    assert results["processed_count"] == 1
    assert results["skipped_count"] == 1


# ==================== scheduler ====================

async def test_scheduler_runs_weekly_job_on_monday_6am_then_stops(service, mock_db, frozen_time, monkeypatch):
    monkeypatch.setattr(frozen_time, "current", datetime(2026, 10, 12, 6, 15, tzinfo=timezone.utc))  # Monday
    weekly = AsyncMock()
    monkeypatch.setattr(service, "process_weekly_settlements", weekly)
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        service.stop_scheduler()

    monkeypatch.setattr(settlement_module, "asyncio", SimpleNamespace(sleep=fake_sleep))
    await service.run_scheduler(mock_db)
    weekly.assert_awaited_once_with(mock_db)
    assert service.last_run == datetime(2026, 10, 12, 6, 15, tzinfo=timezone.utc)
    assert sleeps == [3600]
    assert service.is_running is False


async def test_scheduler_does_nothing_outside_monday_6am(service, mock_db, frozen_time, monkeypatch):
    weekly = AsyncMock()
    monkeypatch.setattr(service, "process_weekly_settlements", weekly)

    async def fake_sleep(seconds):
        service.stop_scheduler()

    monkeypatch.setattr(settlement_module, "asyncio", SimpleNamespace(sleep=fake_sleep))
    await service.run_scheduler(mock_db)
    weekly.assert_not_awaited()


async def test_scheduler_backs_off_one_minute_after_error(service, mock_db, frozen_time, monkeypatch):
    monkeypatch.setattr(frozen_time, "current", datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(service, "process_weekly_settlements", AsyncMock(side_effect=RuntimeError("db down")))
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        service.stop_scheduler()

    monkeypatch.setattr(settlement_module, "asyncio", SimpleNamespace(sleep=fake_sleep))
    await service.run_scheduler(mock_db)
    assert sleeps == [60]
    assert service.last_run is None
