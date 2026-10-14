"""Unit tests for payout gateways (services/payment_gateway_service.py).

httpx.AsyncClient is replaced with a MagicMock in every "configured" test, so no request leaves the
process; the credentials used are fake strings.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from services import payment_gateway_service as pgs
from services.payment_gateway_service import (
    CashfreeGateway,
    MockBankGateway,
    PaymentGatewayManager,
    RazorpayXGateway,
)

EMPLOYEE = {
    "employee_id": "EMP-7", "name": "Asha Rao", "email": "asha@example.com", "phone": "9999999999",
    "account_number": "123456789012", "ifsc_code": "HDFC0001234",
}


def response(status_code=200, json_body=None, text=""):
    return MagicMock(status_code=status_code, json=MagicMock(return_value=json_body or {}), text=text)


@pytest.fixture
def http(monkeypatch):
    """Fake httpx.AsyncClient; configure client.post / client.get return values per test."""
    client = MagicMock()
    client.post = AsyncMock(return_value=response())
    client.get = AsyncMock(return_value=response())
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(pgs.httpx, "AsyncClient", MagicMock(return_value=context))
    return client


@pytest.fixture
def razorpayx():
    gw = RazorpayXGateway()
    gw.api_key, gw.api_secret, gw.account_number = "rzp_test_fakeX", "fake_secret", "2323230000000000"
    gw.is_configured = True
    return gw


@pytest.fixture
def razorpayx_demo():
    gw = RazorpayXGateway()
    gw.is_configured = False
    return gw


@pytest.fixture
def cashfree():
    gw = CashfreeGateway()
    gw.client_id, gw.client_secret, gw.is_configured = "CF_FAKE_ID", "cf_fake_secret", True
    return gw


@pytest.fixture
def cashfree_demo():
    gw = CashfreeGateway()
    gw.is_configured = False
    return gw


# ==================== RazorpayX (configured) ====================

async def test_razorpayx_create_contact_posts_contact(razorpayx, http):
    http.post.return_value = response(json_body={"id": "cont_1", "name": "Asha Rao"})
    result = await razorpayx.create_contact("Asha Rao", "asha@example.com", "9999999999", reference_id="EMP-7")
    url = http.post.call_args.args[0]
    kwargs = http.post.call_args.kwargs
    assert url == "https://api.razorpay.com/v1/contacts"
    assert kwargs["auth"] == ("rzp_test_fakeX", "fake_secret")
    assert kwargs["json"]["contact"] == "9999999999"
    assert kwargs["json"]["reference_id"] == "EMP-7"
    assert result["id"] == "cont_1"


async def test_razorpayx_create_contact_error_raises(razorpayx, http):
    http.post.return_value = response(400, text="invalid email")
    with pytest.raises(Exception, match="Failed to create contact: invalid email"):
        await razorpayx.create_contact("A", "bad", "1")


async def test_razorpayx_create_fund_account(razorpayx, http):
    http.post.return_value = response(json_body={"id": "fa_1"})
    result = await razorpayx.create_fund_account("cont_1", "123456789012", "HDFC0001234", "Asha Rao")
    sent = http.post.call_args.kwargs["json"]
    assert sent == {"contact_id": "cont_1", "account_type": "bank_account", "bank_account": {
        "name": "Asha Rao", "ifsc": "HDFC0001234", "account_number": "123456789012"}}
    assert result == {"id": "fa_1"}


async def test_razorpayx_create_fund_account_error_raises(razorpayx, http):
    http.post.return_value = response(400, text="bad ifsc")
    with pytest.raises(Exception, match="bad ifsc"):
        await razorpayx.create_fund_account("cont_1", "1", "X", "A")


async def test_razorpayx_payout_converts_rupees_to_paise(razorpayx, http):
    http.post.return_value = response(json_body={"id": "pout_1", "status": "processing", "utr": None})
    result = await razorpayx.create_payout("fa_1", 45250.50, "NEFT", "salary", "SAL_1",
                                           narration="Salary for October 2026 - Asha Rao")
    sent = http.post.call_args.kwargs["json"]
    assert sent["amount"] == 4525050  # ₹45,250.50
    assert sent["account_number"] == "2323230000000000"
    assert sent["narration"] == "Salary for October 2026 - Asha"  # truncated to 30 chars
    assert len(sent["narration"]) == 30
    assert sent["queue_if_low_balance"] is True
    assert result == {"payout_id": "pout_1", "status": "processing", "utr": None, "gateway": "razorpayx",
                      "amount": 45250.50, "mode": "NEFT", "reference_id": "SAL_1"}


async def test_razorpayx_payout_paise_conversion_does_not_lose_a_paisa(razorpayx, http):
    http.post.return_value = response(json_body={"id": "pout_2", "status": "processing"})
    await razorpayx.create_payout("fa_1", 1.15, "IMPS", "salary", "SAL_2")
    assert http.post.call_args.kwargs["json"]["amount"] == 115


async def test_razorpayx_payout_error_raises(razorpayx, http):
    http.post.return_value = response(400, text="insufficient balance")
    with pytest.raises(Exception, match="Failed to create payout"):
        await razorpayx.create_payout("fa_1", 10, "NEFT", "salary", "SAL_3")


async def test_razorpayx_bulk_payout_counts_successes_and_failures(razorpayx, http):
    http.post.side_effect = [
        response(json_body={"id": "pout_a", "status": "processing"}),
        response(422, text="fund account inactive"),
    ]
    result = await razorpayx.bulk_payout([
        {"fund_account_id": "fa_a", "amount": 1000, "reference_id": "R1"},
        {"fund_account_id": "fa_b", "amount": 2000, "reference_id": "R2", "mode": "IMPS"},
    ])
    assert (result["total"], result["successful"], result["failed"]) == (2, 1, 1)
    assert result["results"][0]["payout_id"] == "pout_a"
    assert result["results"][1]["reference_id"] == "R2"
    assert "fund account inactive" in result["results"][1]["error"]
    assert http.post.call_args_list[1].kwargs["json"]["mode"] == "IMPS"


async def test_razorpayx_status_and_cancel(razorpayx, http):
    http.get.return_value = response(json_body={"id": "pout_1", "status": "processed"})
    http.post.return_value = response(json_body={"id": "pout_1", "status": "cancelled"})
    assert (await razorpayx.get_payout_status("pout_1"))["status"] == "processed"
    assert http.get.call_args.args[0] == "https://api.razorpay.com/v1/payouts/pout_1"
    assert (await razorpayx.cancel_payout("pout_1"))["status"] == "cancelled"
    assert http.post.call_args.args[0] == "https://api.razorpay.com/v1/payouts/pout_1/cancel"


async def test_razorpayx_status_and_cancel_errors_raise(razorpayx, http):
    http.get.return_value = response(404, text="not found")
    http.post.return_value = response(400, text="not queued")
    with pytest.raises(Exception, match="Failed to get payout status"):
        await razorpayx.get_payout_status("pout_x")
    with pytest.raises(Exception, match="Failed to cancel payout"):
        await razorpayx.cancel_payout("pout_x")


# ==================== RazorpayX (demo mode) ====================

async def test_razorpayx_demo_mode_never_calls_http(razorpayx_demo, monkeypatch):
    monkeypatch.setattr(pgs.httpx, "AsyncClient", MagicMock(side_effect=AssertionError("network used")))
    contact = await razorpayx_demo.create_contact("Asha", "a@x.com", "1")
    fund = await razorpayx_demo.create_fund_account(contact["id"], "123456789012", "HDFC0001234", "Asha")
    payout = await razorpayx_demo.create_payout(fund["id"], 500, "NEFT", "salary", "R1")
    assert contact["mock"] is True and contact["id"].startswith("cont_")
    assert fund["bank_account"]["account_number"] == "********9012"
    assert payout["mock"] is True and payout["status"] == "processing" and payout["amount"] == 500
    assert (await razorpayx_demo.get_payout_status("p"))["status"] == "processed"
    assert await razorpayx_demo.cancel_payout("p") == {"status": "cancelled", "payout_id": "p"}


# ==================== Cashfree ====================

def test_cashfree_sandbox_and_production_urls(monkeypatch):
    monkeypatch.setenv("CASHFREE_SANDBOX", "true")
    assert CashfreeGateway().base_url == "https://payout-gamma.cashfree.com"
    monkeypatch.setenv("CASHFREE_SANDBOX", "false")
    assert CashfreeGateway().base_url == "https://payout-api.cashfree.com"


async def test_cashfree_add_beneficiary(cashfree, http):
    result = await cashfree.create_contact("Asha", "a@x.com", "999", beneficiary_id="BENE_1",
                                           account_number="123456789012", ifsc="HDFC0001234")
    url = http.post.call_args.args[0]
    kwargs = http.post.call_args.kwargs
    assert url.endswith("/payout/v1/addBeneficiary")
    assert kwargs["headers"]["X-Client-Id"] == "CF_FAKE_ID"
    assert kwargs["json"]["bankAccount"] == "123456789012"
    assert kwargs["json"]["ifsc"] == "HDFC0001234"
    assert result == {"id": "BENE_1", "name": "Asha", "email": "a@x.com", "phone": "999", "gateway": "cashfree"}


async def test_cashfree_add_beneficiary_error_raises(cashfree, http):
    http.post.return_value = response(409, text="beneficiary exists")
    with pytest.raises(Exception, match="Failed to create beneficiary"):
        await cashfree.create_contact("Asha", "a@x.com", "999")


async def test_cashfree_fund_account_masks_account_number(cashfree):
    result = await cashfree.create_fund_account("BENE_1", "123456789012", "HDFC0001234", "Asha")
    assert result["id"] == "BENE_1"
    assert result["account_number"] == "********9012"


async def test_cashfree_transfer_sends_rupees_as_string(cashfree, http):
    http.post.return_value = response(json_body={"status": "SUCCESS", "data": {"referenceId": "CF123", "utr": "UTR9"}})
    result = await cashfree.create_payout("BENE_1", 45250.5, "IMPS", "salary", "SAL_1")
    sent = http.post.call_args.kwargs["json"]
    assert sent == {"beneId": "BENE_1", "amount": "45250.5", "transferId": "SAL_1",
                    "transferMode": "IMPS", "remarks": "salary"}
    assert result["payout_id"] == "CF123"
    assert result["utr"] == "UTR9"
    assert result["status"] == "SUCCESS"


async def test_cashfree_transfer_defaults_when_response_has_no_data(cashfree, http):
    http.post.return_value = response(json_body={})
    result = await cashfree.create_payout("BENE_1", 10, "IMPS", "salary", "SAL_2", narration="Oct salary")
    assert http.post.call_args.kwargs["json"]["remarks"] == "Oct salary"
    assert result["payout_id"] == "SAL_2"
    assert result["status"] == "PENDING"


async def test_cashfree_transfer_error_raises(cashfree, http):
    http.post.return_value = response(400, text="low balance")
    with pytest.raises(Exception, match="Failed to create transfer"):
        await cashfree.create_payout("BENE_1", 10, "IMPS", "salary", "SAL_3")


async def test_cashfree_bulk_payout(cashfree, http):
    http.post.side_effect = [response(json_body={"status": "SUCCESS"}), response(500, text="down")]
    result = await cashfree.bulk_payout([
        {"fund_account_id": "B1", "amount": 100, "reference_id": "R1"},
        {"fund_account_id": "B2", "amount": 200, "reference_id": "R2"},
    ])
    assert result["batch_id"].startswith("BATCH_")
    assert (result["successful"], result["failed"]) == (1, 1)
    assert http.post.call_args_list[0].kwargs["json"]["transferMode"] == "IMPS"


async def test_cashfree_transfer_status(cashfree, http):
    http.get.return_value = response(json_body={"status": "SUCCESS"})
    assert await cashfree.get_payout_status("SAL_1") == {"status": "SUCCESS"}
    assert http.get.call_args.kwargs["params"] == {"transferId": "SAL_1"}
    http.get.return_value = response(404, text="unknown")
    with pytest.raises(Exception, match="Failed to get transfer status"):
        await cashfree.get_payout_status("SAL_X")


async def test_cashfree_cannot_cancel(cashfree):
    assert (await cashfree.cancel_payout("x"))["status"] == "not_supported"


async def test_cashfree_demo_mode(cashfree_demo):
    contact = await cashfree_demo.create_contact("Asha", "a@x.com", "1")
    payout = await cashfree_demo.create_payout("B", 99, "IMPS", "salary", "R")
    bulk = await cashfree_demo.bulk_payout([{"fund_account_id": "B", "amount": 5, "reference_id": "R1"}])
    assert contact["mock"] is True and contact["id"].startswith("BENE_")
    assert payout["status"] == "PENDING" and payout["amount"] == 99
    assert bulk["mock"] is True and bulk["successful"] == 1 and bulk["results"][0]["mode"] == "IMPS"
    assert (await cashfree_demo.get_payout_status("R"))["status"] == "SUCCESS"


# ==================== Mock bank gateway ====================

async def test_mock_bank_gateway_flow():
    gw = MockBankGateway("icici")
    contact = await gw.create_contact("Asha", "a@x.com", "1")
    fund = await gw.create_fund_account(contact["id"], "123456789012", "ICIC0000001", "Asha")
    payout = await gw.create_payout(fund["id"], 1234.5, "RTGS", "salary", "R1")
    assert contact["id"].startswith("ICICI_")
    assert fund["account_number"] == "********9012"
    assert payout["gateway"] == "icici" and payout["amount"] == 1234.5 and payout["mode"] == "RTGS"
    status = await gw.get_payout_status(payout["payout_id"])
    assert status["status"] == "completed" and status["payout_id"] == payout["payout_id"]
    assert (await gw.cancel_payout("p"))["status"] == "cancelled"


async def test_mock_bank_bulk_payout():
    result = await MockBankGateway("axis").bulk_payout([
        {"fund_account_id": "F1", "amount": 100, "reference_id": "R1"},
        {"fund_account_id": "F2", "amount": 200, "reference_id": "R2", "mode": "IMPS"},
    ])
    assert (result["total"], result["successful"], result["failed"]) == (2, 2, 0)
    assert [r["mode"] for r in result["results"]] == ["NEFT", "IMPS"]


# ==================== PaymentGatewayManager ====================

@pytest.fixture
def manager():
    mgr = PaymentGatewayManager()
    mgr.gateways["razorpayx"].is_configured = False
    mgr.gateways["cashfree"].is_configured = False
    return mgr


def test_unknown_gateway_falls_back_to_razorpayx(manager):
    assert manager.get_gateway("paypal") is manager.gateways["razorpayx"]
    assert manager.get_gateway(None) is manager.gateways["razorpayx"]
    assert manager.get_gateway("idfc") is manager.gateways["idfc"]


def test_available_gateways_flag_unconfigured_as_mock(manager):
    manager.gateways["cashfree"].is_configured = True
    by_name = {g["name"]: g for g in manager.get_available_gateways()}
    assert set(by_name) == {"razorpayx", "cashfree", "icici", "idfc", "axis", "mock"}
    assert by_name["razorpayx"] == {"name": "razorpayx", "display_name": "Razorpayx",
                                    "is_configured": False, "is_mock": True}
    assert by_name["cashfree"]["is_mock"] is False
    assert by_name["mock"]["is_mock"] is True
    assert by_name["icici"]["is_mock"] is False


async def test_salary_payout_creates_contact_fund_account_and_payout(manager):
    result = await manager.process_salary_payout("mock", EMPLOYEE, 45000, mode="IMPS", reference_id="SAL_OCT_7")
    assert result["success"] is True
    assert result["amount"] == 45000
    assert result["mode"] == "IMPS"
    assert result["reference_id"] == "SAL_OCT_7"
    assert result["contact_id"].startswith("MOCK_")
    assert result["fund_account_id"].startswith("FA_MOCK_")


async def test_salary_payout_missing_bank_details_fails_cleanly(manager):
    employee = {k: v for k, v in EMPLOYEE.items() if k != "ifsc_code"}
    result = await manager.process_salary_payout("mock", employee, 45000)
    assert result["success"] is False
    assert result["error"] == "'ifsc_code'"
    assert result["reference_id"].startswith("SAL_")


async def test_salary_payout_via_configured_razorpayx(manager, http):
    gw = manager.gateways["razorpayx"]
    gw.api_key, gw.api_secret, gw.is_configured = "rzp_test_fakeX", "fake_secret", True
    http.post.side_effect = [
        response(json_body={"id": "cont_1"}),
        response(json_body={"id": "fa_1"}),
        response(json_body={"id": "pout_1", "status": "queued"}),
    ]
    result = await manager.process_salary_payout("razorpayx", EMPLOYEE, 30000.25, reference_id="SAL_1")
    payout_json = http.post.call_args_list[2].kwargs["json"]
    assert payout_json["fund_account_id"] == "fa_1"
    assert payout_json["amount"] == 3000025
    assert payout_json["purpose"] == "salary"
    assert result["success"] is True and result["payout_id"] == "pout_1" and result["status"] == "queued"


async def test_cashfree_salary_payout_registers_beneficiary_bank_account(manager, http):
    gw = manager.gateways["cashfree"]
    gw.client_id, gw.client_secret, gw.is_configured = "CF_FAKE_ID", "cf_fake_secret", True
    http.post.return_value = response(json_body={"status": "SUCCESS"})
    await manager.process_salary_payout("cashfree", EMPLOYEE, 45000)
    beneficiary = http.post.call_args_list[0].kwargs["json"]
    assert beneficiary["bankAccount"] == "123456789012"
    assert beneficiary["ifsc"] == "HDFC0001234"


async def test_bulk_salary_reports_preparation_errors(manager):
    employees = [
        {**EMPLOYEE, "amount": 45000},
        {**EMPLOYEE, "employee_id": "EMP-8", "name": "Ravi", "amount": 38000},
        {"employee_id": "EMP-9", "name": "No Bank", "amount": 1000},
    ]
    result = await manager.process_bulk_salary("axis", employees, mode="RTGS")
    assert (result["total"], result["successful"]) == (2, 2)
    assert [r["amount"] for r in result["results"]] == [45000, 38000]
    assert all(r["mode"] == "RTGS" for r in result["results"])
    assert result["results"][0]["reference_id"].startswith("SAL_EMP-7_")
    assert result["preparation_errors"] == [
        {"employee_id": "EMP-9", "employee_name": "No Bank", "error": "'account_number'"}]


async def test_bulk_salary_with_no_valid_employees(manager):
    result = await manager.process_bulk_salary("mock", [{"employee_id": "E1", "name": "X", "amount": 1}])
    assert result["total"] == 0
    assert result["failed"] == 1
    assert result["results"] == []


async def test_vendor_payment_pays_net_of_tds(manager):
    # ₹1,00,000 invoice − ₹10,000 TDS (10%) = ₹90,000 paid
    vendor = {"vendor_id": "V-1", "name": "Hangar Services", "account_number": "998877665544",
              "ifsc_code": "ICIC0000001"}
    result = await manager.process_vendor_payment("icici", vendor, 100000, 10000, reference_id="VEN_1")
    assert result["success"] is True
    assert result["gross_amount"] == 100000
    assert result["tds_deducted"] == 10000
    assert result["net_paid"] == 90000
    assert result["amount"] == 90000
    assert result["reference_id"] == "VEN_1"


async def test_vendor_payment_failure_is_reported(manager):
    result = await manager.process_vendor_payment("icici", {"name": "No Bank"}, 100, 10)
    assert result["success"] is False
    assert result["reference_id"].startswith("VEN_")
