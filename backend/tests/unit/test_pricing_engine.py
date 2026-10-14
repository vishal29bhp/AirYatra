"""Unit tests for the helicopter pricing engine (services/pricing_engine.py).

Unless a test seeds its own configuration, the engine runs on its built-in defaults:
  operator rate ₹1,80,000/h, minimum 2 billable hours, commission 10%, convenience fee 5%,
  insurance 2%, GST 18% (CGST 9% + SGST 9% intra-state, IGST 18% inter-state).

Baseline trip used throughout: 2.5 h, Mumbai, Maharashtra → Pune, Maharashtra, personal.
  base          = 2.5 × 1,80,000          = 4,50,000
  commission    = 10% of 4,50,000         =   45,000
  convenience   = 5%  of 4,50,000         =   22,500
  insurance     = 2%  of 4,50,000         =    9,000
  taxable       = 4,50,000 + 45,000 + 22,500 + 9,000 = 5,26,500
  CGST = SGST   = 9% of 5,26,500          =   47,385   (total GST 94,770)
  final         = 5,26,500 + 94,770       = 6,21,270
  operator net  = 4,50,000 − 45,000       = 4,05,000
"""
import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from pricing_models import BookingPurpose, PriceCalculationRequest
from services import pricing_engine as pricing_module
from services.pricing_engine import (
    HelicopterPricingEngine,
    estimate_flight_hours,
    haversine_distance,
)

DEFAULT_ADMIN = {
    "is_active": True,
    "commission_type": "percentage",
    "commission_value": 10,
    "commission_overrides": {},
    "peak_season_enabled": True,
    "peak_surge_multiplier": 1.3,
    "peak_dates": [],
    "fuel_surcharge_enabled": True,
    "fuel_surcharge_percent": 5,
    "convenience_fee_percent": 5,
    "insurance_percent": 2,
    "insurance_enabled": True,
    "gst_percent": 18,
    "cgst_percent": 9,
    "sgst_percent": 9,
    "igst_percent": 18,
}

DEFAULT_CHARGES = {
    "night_halt_per_night": 25000,
    "crew_accommodation_included": False,
    "crew_accommodation_per_night": 5000,
    "crew_food_allowance_per_day": 1500,
    "waiting_free_minutes": 30,
    "waiting_charge_per_minute": 500,
    "waiting_charge_per_hour": 25000,
    "fuel_cost_type": "included",
    "fuel_surcharge_percent": 0,
    "round_trip_discount_percent": 10,
    "mandatory_return": False,
}


@pytest.fixture
def engine(mock_db, monkeypatch):
    monkeypatch.setattr(pricing_module, "get_database", lambda: mock_db)
    return HelicopterPricingEngine()


def make_request(**overrides) -> PriceCalculationRequest:
    data = {
        "pickup_city": "Mumbai, Maharashtra",
        "pickup_latitude": 19.9,
        "pickup_longitude": 72.8,
        "drop_city": "Pune, Maharashtra",
        "drop_latitude": 18.52,
        "drop_longitude": 73.85,
        "distance_km": 500,
        "departure_date": "2026-11-10",
        "departure_time": "10:00",
        "estimated_flight_hours": 2.5,
    }
    data.update(overrides)
    return PriceCalculationRequest(**data)


async def seed_admin(mock_db, **overrides):
    await mock_db.admin_pricing_controls.insert_one({**DEFAULT_ADMIN, **overrides})


async def seed_charges(mock_db, operator_id="default", **overrides):
    await mock_db.additional_charges.insert_one({"operator_id": operator_id, **DEFAULT_CHARGES, **overrides})


# ==================== utility functions ====================

def test_haversine_one_degree_of_latitude_is_about_111_km():
    # 6371 × π/180 = 111.19 km
    assert haversine_distance(19.0, 72.8, 20.0, 72.8) == pytest.approx(111.195, abs=0.01)


def test_haversine_same_point_is_zero():
    assert haversine_distance(19.07, 72.87, 19.07, 72.87) == 0


def test_estimate_flight_hours_uses_200_kmh_and_rounds_to_two_places():
    assert estimate_flight_hours(300) == 1.5
    assert estimate_flight_hours(100, avg_speed_kmh=150) == 0.67


# ==================== configuration lookups ====================

async def test_initialize_uses_get_database_once(engine, mock_db):
    await engine.initialize()
    assert engine.db is mock_db
    assert engine._initialized is True


async def test_admin_controls_fall_back_to_defaults(engine):
    controls = await engine.get_admin_controls()
    assert controls["commission_value"] == 10
    assert controls["gst_percent"] == 18
    assert controls["cancellation_slabs"][0] == {"hours_before": 72, "charge_percent": 10}


async def test_active_admin_controls_override_defaults(engine, mock_db):
    await seed_admin(mock_db, commission_value=12)
    await mock_db.admin_pricing_controls.insert_one({**DEFAULT_ADMIN, "is_active": False, "commission_value": 99})
    controls = await engine.get_admin_controls()
    assert controls["commission_value"] == 12
    assert "_id" not in controls


async def test_operator_pricing_defaults_when_not_configured(engine):
    pricing = await engine.get_operator_pricing("op-unknown")
    assert pricing["price_per_hour"] == 180000
    assert pricing["min_billable_hours"] == 2
    assert pricing["purpose_multipliers"]["wedding"] == 1.3


async def test_operator_pricing_is_matched_by_helicopter(engine, mock_db):
    await mock_db.operator_pricing.insert_many([
        {"operator_id": "op-1", "helicopter_id": "h-1", "is_active": True, "price_per_hour": 150000},
        {"operator_id": "op-1", "helicopter_id": "h-2", "is_active": True, "price_per_hour": 250000},
    ])
    pricing = await engine.get_operator_pricing("op-1", "h-2")
    assert pricing["price_per_hour"] == 250000


async def test_dead_leg_and_additional_charge_defaults(engine):
    dead_leg = await engine.get_dead_leg_config("op-1", "h-1")
    charges = await engine.get_additional_charges("op-1", "h-1")
    assert dead_leg["rate_value"] == 500 and dead_leg["base_latitude"] is None
    assert charges["night_halt_per_night"] == 25000
    assert charges["round_trip_discount_percent"] == 10


async def test_route_pricing_matches_city_names_case_insensitively(engine, mock_db):
    await mock_db.route_pricing.insert_one(
        {"route_from": "Mumbai", "route_to": "Pune", "base_price": 300000, "is_active": True})
    assert (await engine.get_route_pricing("mumbai", "PUNE"))["base_price"] == 300000
    assert await engine.get_route_pricing("Delhi", "Pune") is None


async def test_landing_rent_by_landing_point_id_or_id(engine, mock_db):
    await mock_db.landing_points.insert_many([
        {"landing_point_id": "lp-1", "landing_point_name": "Juhu Helipad", "rent_per_landing": 15000},
        {"id": "lp-2", "name": "Pune Racecourse", "rent": 8000},
    ])
    assert await engine.get_landing_rent("lp-1") == {"rent": 15000, "name": "Juhu Helipad"}
    assert await engine.get_landing_rent("lp-2") == {"rent": 8000, "name": "Pune Racecourse"}
    assert await engine.get_landing_rent("missing") == {"rent": 0, "name": None}
    assert await engine.get_landing_rent(None) == {"rent": 0, "name": None}


# ==================== peak season ====================

async def test_peak_season_applies_inside_window_with_its_multiplier(engine, mock_db):
    await seed_admin(mock_db, peak_dates=[{"start": "2026-12-20", "end": "2026-12-31", "multiplier": 1.5}])
    assert await engine.check_peak_season("2026-12-25") == (True, 1.5)
    assert await engine.check_peak_season("2026-12-19") == (False, 1.0)


async def test_peak_window_without_multiplier_uses_admin_surge(engine, mock_db):
    await seed_admin(mock_db, peak_surge_multiplier=1.25, peak_dates=[{"start": "2026-12-20", "end": "2026-12-31"}])
    assert await engine.check_peak_season("2026-12-20") == (True, 1.25)


async def test_peak_window_limited_to_other_regions_is_ignored(engine, mock_db):
    await seed_admin(mock_db, peak_dates=[
        {"start": "2026-12-20", "end": "2026-12-31", "multiplier": 1.5, "regions": ["Goa"]}])
    assert await engine.check_peak_season("2026-12-25", "Mumbai") == (False, 1.0)
    assert await engine.check_peak_season("2026-12-25", "goa") == (True, 1.5)


async def test_peak_season_disabled_or_bad_dates_mean_no_surge(engine, mock_db):
    await seed_admin(mock_db, peak_season_enabled=False,
                     peak_dates=[{"start": "2026-12-20", "end": "2026-12-31", "multiplier": 1.5}])
    assert await engine.check_peak_season("2026-12-25") == (False, 1.0)


async def test_unparseable_booking_or_peak_dates_are_skipped(engine, mock_db):
    await seed_admin(mock_db, peak_dates=[{"start": "not-a-date", "end": "2026-12-31", "multiplier": 2},
                                          {"start": "2026-12-20", "end": "2026-12-31", "multiplier": 1.5}])
    assert await engine.check_peak_season("25/12/2026") == (False, 1.0)
    assert await engine.check_peak_season("2026-12-25") == (True, 1.5)


# ==================== contract lookup ====================

async def test_contract_lookup_by_id_customer_and_email_domain(engine, mock_db):
    await mock_db.corporate_contracts.insert_one({
        "contract_id": "c-1", "is_active": True, "discount_percent": 4,
        "tagged_customer_ids": ["cust-9"], "tagged_email_domains": ["tata.com"],
    })
    assert (await engine.get_contract_pricing(contract_id="c-1"))["contract_id"] == "c-1"
    assert (await engine.get_contract_pricing(customer_id="cust-9"))["contract_id"] == "c-1"
    assert (await engine.get_contract_pricing(customer_email="ceo@tata.com"))["contract_id"] == "c-1"
    assert await engine.get_contract_pricing(customer_id="cust-x", customer_email="me@gmail.com") is None
    assert await engine.get_contract_pricing(customer_email="no-at-sign") is None


async def test_inactive_contract_is_not_applied(engine, mock_db):
    await mock_db.corporate_contracts.insert_one({"contract_id": "c-2", "is_active": False})
    assert await engine.get_contract_pricing(contract_id="c-2") is None


# ==================== calculate_price ====================

async def test_baseline_intra_state_price_with_cgst_and_sgst(engine):
    result = await engine.calculate_price(make_request())
    b = result.price_breakdown
    assert b.pricing_type_used == "hourly"
    assert b.base_flight_cost == 450000
    assert b.mdg_adjustment == 0
    assert b.operator_gross_cost == 450000
    assert b.platform_commission == 45000
    assert b.convenience_fee == 22500
    assert b.insurance == 9000
    assert b.taxable_amount == 526500
    assert b.gst_type == "intra_state"
    assert (b.cgst, b.sgst, b.igst) == (47385, 47385, 0)
    assert b.total_gst == 94770
    assert b.final_customer_price == 621270
    assert b.operator_net_payout == 405000
    assert b.platform_earnings == 67500  # 45,000 commission + 22,500 convenience fee


async def test_inter_state_trip_charges_igst_instead(engine):
    result = await engine.calculate_price(make_request(drop_city="Panaji, Goa"))
    b = result.price_breakdown
    assert b.gst_type == "inter_state"
    assert (b.cgst, b.sgst, b.igst) == (0, 0, 94770)  # 18% of 5,26,500
    assert b.final_customer_price == 621270


async def test_cities_without_state_are_treated_as_intra_state(engine):
    result = await engine.calculate_price(make_request(pickup_city="Mumbai", drop_city="Panaji, Goa"))
    assert result.price_breakdown.gst_type == "intra_state"


async def test_minimum_billable_hours_adds_mdg_adjustment(engine):
    # 1.5 h flown, 2 h minimum: MDG = 0.5 × 1,80,000 = 90,000; gross = 2,70,000 + 90,000 = 3,60,000
    result = await engine.calculate_price(make_request(estimated_flight_hours=1.5))
    b = result.price_breakdown
    assert b.base_flight_cost == 270000
    assert b.mdg_adjustment == 90000
    assert b.operator_gross_cost == 360000
    assert "Minimum 2 hours billing applied" in b.notes


async def test_flight_hours_estimated_from_distance_when_missing(engine):
    # 300 km / 200 km/h = 1.5 h
    result = await engine.calculate_price(make_request(estimated_flight_hours=None, distance_km=300))
    assert result.price_breakdown.flight_hours == 1.5
    assert result.price_breakdown.base_flight_cost == 270000


async def test_short_wait_is_billed_per_minute_after_free_minutes(engine):
    # 50 min − 30 free = 20 min × ₹500 = 10,000
    b = (await engine.calculate_price(make_request(waiting_time_minutes=50))).price_breakdown
    assert b.waiting_billable_minutes == 20
    assert b.waiting_charges == 10000
    assert b.operator_gross_cost == 460000


async def test_long_wait_is_billed_per_hour(engine):
    # 120 min − 30 free = 90 min = 1.5 h × ₹25,000 = 37,500
    b = (await engine.calculate_price(make_request(waiting_time_minutes=120))).price_breakdown
    assert b.waiting_charges == 37500


async def test_wait_within_free_minutes_is_free(engine):
    b = (await engine.calculate_price(make_request(waiting_time_minutes=30))).price_breakdown
    assert b.waiting_charges == 0


async def test_night_halts_add_halt_and_crew_costs(engine):
    # 2 nights × 25,000 = 50,000; crew 2 × (5,000 + 1,500) = 13,000
    b = (await engine.calculate_price(make_request(night_halts=2))).price_breakdown
    assert b.night_halt_cost == 50000
    assert b.crew_charges == 13000
    assert b.operator_gross_cost == 513000


async def test_crew_cost_skipped_when_accommodation_included(engine, mock_db):
    await seed_charges(mock_db, crew_accommodation_included=True)
    b = (await engine.calculate_price(make_request(night_halts=2))).price_breakdown
    assert b.night_halt_cost == 50000
    assert b.crew_charges == 0


async def test_excluded_fuel_adds_admin_fuel_surcharge(engine, mock_db):
    # 5% of 4,50,000 = 22,500
    await seed_charges(mock_db, fuel_cost_type="excluded")
    b = (await engine.calculate_price(make_request())).price_breakdown
    assert b.fuel_surcharge == 22500
    assert b.operator_gross_cost == 472500


async def test_fuel_surcharge_not_applied_when_admin_disables_it(engine, mock_db):
    await seed_admin(mock_db, fuel_surcharge_enabled=False)
    await seed_charges(mock_db, fuel_cost_type="surcharge")
    b = (await engine.calculate_price(make_request())).price_breakdown
    assert b.fuel_surcharge == 0


async def test_landing_rent_is_added_for_pickup_and_drop(engine, mock_db):
    await mock_db.landing_points.insert_many([
        {"landing_point_id": "lp-1", "landing_point_name": "Juhu Helipad", "rent_per_landing": 15000},
        {"id": "lp-2", "name": "Pune Racecourse", "rent": 8000},
    ])
    result = await engine.calculate_price(
        make_request(pickup_landing_point_id="lp-1", drop_landing_point_id="lp-2"))
    b = result.price_breakdown
    assert b.total_landing_rent == 23000
    assert (b.pickup_landing_name, b.drop_landing_name) == ("Juhu Helipad", "Pune Racecourse")
    assert b.operator_gross_cost == 473000
    assert result.customer_view["landing_charges"] == 23000


async def test_wedding_purpose_multiplier_raises_base(engine):
    # wedding 1.3×: adjustment = 4,50,000 × 0.3 = 1,35,000
    b = (await engine.calculate_price(make_request(booking_purpose=BookingPurpose.WEDDING))).price_breakdown
    assert b.purpose == "wedding"
    assert b.purpose_adjustment == 135000
    assert b.operator_gross_cost == 585000


async def test_medical_purpose_multiplier_discounts_base(engine):
    # medical 0.9×: adjustment = 4,50,000 × −0.1 = −45,000
    b = (await engine.calculate_price(make_request(booking_purpose=BookingPurpose.MEDICAL))).price_breakdown
    assert b.purpose_adjustment == -45000
    assert b.operator_gross_cost == 405000


async def test_round_trip_discount_is_taken_off_base(engine):
    # 10% of 4,50,000 = 45,000 → gross 4,05,000
    result = await engine.calculate_price(make_request(is_round_trip=True))
    b = result.price_breakdown
    assert b.round_trip_discount_percent == 10
    assert b.round_trip_discount == 45000
    assert b.operator_gross_cost == 405000
    assert result.customer_view["discount"] == 45000


async def test_route_pricing_takes_priority_over_hourly(engine, mock_db):
    # route 3,00,000; +10% 30,000 +5% 15,000 +2% 6,000 = 3,51,000; GST 2 × 31,590 = 63,180
    await mock_db.route_pricing.insert_one(
        {"route_from": "Mumbai", "route_to": "Pune", "base_price": 300000, "is_active": True})
    b = (await engine.calculate_price(make_request(pickup_city="Mumbai", drop_city="Pune"))).price_breakdown
    assert b.pricing_type_used == "route"
    assert b.base_flight_cost == 300000
    assert b.mdg_adjustment == 0
    assert b.final_customer_price == 414180


async def test_operator_specific_rate_and_minimum_hours(engine, mock_db):
    # 2.5 h × 2,00,000 = 5,00,000, minimum 3 h → MDG 0.5 × 2,00,000 = 1,00,000
    await mock_db.operator_pricing.insert_one({
        "operator_id": "op-1", "is_active": True, "price_per_hour": 200000,
        "min_billable_hours": 3, "purpose_multipliers": {"personal": 1.0},
    })
    b = (await engine.calculate_price(make_request(operator_id="op-1"))).price_breakdown
    assert b.rate_per_hour == 200000
    assert b.mdg_adjustment == 100000
    assert b.operator_gross_cost == 600000


@pytest.mark.parametrize("rate_type, rate_value, expected_cost", [
    ("per_km", 500, 45038),     # (100.075 km − 10 free) = 90.075 km × ₹500 = 45,037.7 → 45,038
    ("per_hour", 60000, 27000),  # 90.075 km / 200 = 0.45 h × ₹60,000
    ("percentage", 10, 45000),   # 10% of 4,50,000
    ("fixed", 20000, 20000),
])
async def test_dead_leg_cost_by_rate_type(engine, mock_db, rate_type, rate_value, expected_cost):
    # Base at (19.0, 72.8); pickup at (19.9, 72.8) is 0.9° of latitude = 6371 × 0.9π/180 = 100.075 km away.
    await mock_db.dead_leg_pricing.insert_one({
        "operator_id": "op-1", "enabled": True, "rate_type": rate_type, "rate_value": rate_value,
        "free_positioning_km": 10, "base_latitude": 19.0, "base_longitude": 72.8,
    })
    b = (await engine.calculate_price(make_request(operator_id="op-1"))).price_breakdown
    assert b.dead_leg_enabled is True
    assert b.dead_leg_distance_km == 90.08
    assert b.dead_leg_cost == expected_cost
    assert b.operator_gross_cost == 450000 + expected_cost


async def test_no_dead_leg_charge_inside_free_radius(engine, mock_db):
    await mock_db.dead_leg_pricing.insert_one({
        "operator_id": "op-1", "enabled": True, "rate_type": "per_km", "rate_value": 500,
        "free_positioning_km": 200, "base_latitude": 19.0, "base_longitude": 72.8,
    })
    b = (await engine.calculate_price(make_request(operator_id="op-1"))).price_breakdown
    assert b.dead_leg_enabled is False
    assert b.dead_leg_cost == 0


async def test_commission_override_by_operator(engine, mock_db):
    # 8% of 4,50,000 = 36,000
    await seed_admin(mock_db, commission_overrides={"by_operator": {"op-1": 8}, "by_purpose": {"personal": 15}})
    b = (await engine.calculate_price(make_request(operator_id="op-1"))).price_breakdown
    assert b.platform_commission_percent == 8
    assert b.platform_commission == 36000
    assert b.operator_net_payout == 414000


async def test_commission_override_by_purpose(engine, mock_db):
    # 15% of 4,50,000 = 67,500
    await seed_admin(mock_db, commission_overrides={"by_purpose": {"personal": 15}})
    b = (await engine.calculate_price(make_request())).price_breakdown
    assert b.platform_commission == 67500


async def test_insurance_skipped_when_disabled(engine, mock_db):
    # taxable 4,50,000 + 45,000 + 22,500 = 5,17,500; GST 2 × 46,575 = 93,150
    await seed_admin(mock_db, insurance_enabled=False)
    b = (await engine.calculate_price(make_request())).price_breakdown
    assert b.insurance == 0
    assert b.taxable_amount == 517500
    assert b.final_customer_price == 610650


async def test_peak_surge_applies_to_subtotal_before_gst(engine, mock_db):
    # surge 20% of 5,26,500 = 1,05,300; taxable 6,31,800; GST 2 × 56,862 = 1,13,724; final 7,45,524
    await seed_admin(mock_db, peak_dates=[{"start": "2026-12-20", "end": "2026-12-31", "multiplier": 1.2}])
    b = (await engine.calculate_price(make_request(departure_date="2026-12-25"))).price_breakdown
    assert b.peak_surge_applied is True
    assert b.peak_surge_amount == 105300
    assert b.taxable_amount == 631800
    assert b.final_customer_price == 745524
    assert "Peak season pricing applied (1.2x)" in b.notes


async def test_contract_discount_reduces_taxable_amount(engine, mock_db):
    # 4% of (4,50,000 + 45,000) = 19,800; taxable 5,06,700; GST 2 × 45,603 = 91,206; final 5,97,906
    await mock_db.corporate_contracts.insert_one(
        {"contract_id": "c-1", "is_active": True, "discount_percent": 4, "tagged_email_domains": ["tata.com"]})
    result = await engine.calculate_price(make_request(customer_email="ceo@tata.com"))
    b = result.price_breakdown
    assert b.contract_applied is True
    assert b.contract_discount == 19800
    assert b.taxable_amount == 506700
    assert b.final_customer_price == 597906
    assert result.customer_view["discount"] == 19800


async def test_contract_fixed_hourly_rate_lowers_final_price(engine, mock_db):
    # 2.5 h × 1,50,000 = 3,75,000; +37,500 +18,750 +7,500 = 4,38,750; GST 2 × round(39,487.5) = 2 × 39,488 = 78,976; final 5,17,726
    await mock_db.corporate_contracts.insert_one(
        {"contract_id": "c-9", "is_active": True, "discount_percent": 0, "fixed_rate_per_hour": 150000})
    b = (await engine.calculate_price(make_request(contract_id="c-9"))).price_breakdown
    assert b.base_flight_cost == 375000
    assert b.operator_gross_cost == 375000
    assert b.final_customer_price == 517726


async def test_views_are_consistent_with_breakdown(engine):
    result = await engine.calculate_price(make_request(waiting_time_minutes=50, night_halts=1))
    b = result.price_breakdown
    assert result.success is True
    assert result.customer_view["total"] == b.final_customer_price
    assert result.customer_view["gst"] == b.total_gst
    assert result.customer_view["night_halt_charges"] == 25000 + 6500
    assert result.operator_view["net_payout"] == b.operator_gross_cost - b.platform_commission
    assert result.admin_view["gst_collected"] == b.total_gst
    assert result.booking_summary["route"] == "Mumbai, Maharashtra → Pune, Maharashtra"
    assert any("FINAL CUSTOMER PRICE" in line for line in result.audit_log)


async def test_calculation_is_stored_for_audit(engine, mock_db):
    result = await engine.calculate_price(make_request())
    stored = await mock_db.price_calculations.find_one({"calculation_id": result.calculation_id})
    assert stored["response_summary"] == {
        "final_price": 621270, "operator_payout": 405000, "platform_earnings": 67500}
    assert stored["request"]["pickup_city"] == "Mumbai, Maharashtra"


async def test_failure_to_store_calculation_is_swallowed(engine):
    engine.db = MagicMock()
    engine.db.price_calculations.insert_one = AsyncMock(side_effect=RuntimeError("db down"))
    await engine.store_calculation("calc-1", make_request(), MagicMock())  # must not raise
    engine.db.price_calculations.insert_one.assert_awaited_once()


async def test_dead_leg_distance_matches_haversine():
    # Guard for the hand-computed figure used in the dead-leg tests above.
    assert haversine_distance(19.0, 72.8, 19.9, 72.8) == pytest.approx(6371 * math.radians(0.9))
