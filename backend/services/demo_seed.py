"""Dev-only demo data so every role's dashboard has something to show a client.

Seeds about 25 records per area: customers and their trips, operators with aircraft, pilots and
inquiries, bookings, settlements, landing permissions and finance entries. The names are made up.

Every seeded document has an id that starts with "demo-", and the demo logins are marked
created_by="demo_seed", so `remove_demo_data` takes exactly these out again and nothing else.
Seeding runs once (it stops if the demo customer already exists) and never in production.

It links to two logins when they exist:
- customer@airyatra.co.in gets the demo customer's 25 trips (created when missing, with the
  BOOTSTRAP_STAFF_PASSWORD, so it signs in like the staff logins).
- operator@airyatra.co.in becomes the owner of the first demo operator, with its fleet and inquiries.
  If that login already has an operator profile, the demo fleet and inquiries are added to it instead.
"""
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from config import PRODUCTION_ENVS

logger = logging.getLogger(__name__)

PREFIX = "demo-"
CREATED_BY = "demo_seed"
DEMO_CUSTOMER_EMAIL = "customer@airyatra.co.in"
DEMO_OPERATOR_EMAIL = "operator@airyatra.co.in"
COUNT = 25
COLLECTIONS = ["users", "operators", "aircraft", "pilots", "bookings", "inquiries", "settlements",
               "landing_permissions", "pilot_documents", "aircraft_documents", "payment_transactions",
               "vendor_bills", "approval_requests", "tds_entries", "salary_runs", "loyalty_profiles"]

FIRST = ["Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Sneha", "Aditya", "Kavya", "Siddharth", "Isha",
         "Omkar", "Neha", "Rahul", "Pooja", "Kunal", "Shruti", "Amit", "Rutuja", "Nikhil", "Sayali",
         "Tejas", "Meera", "Harsh", "Gauri", "Varun"]
LAST = ["Patil", "Deshmukh", "Kulkarni", "Joshi", "Shinde", "Pawar", "Jadhav", "Gokhale", "Bhosale", "Sawant",
        "Kale", "Mehta", "Shah", "Rao", "Naik", "Desai", "Chavan", "More", "Gaikwad", "Apte",
        "Karandikar", "Phadke", "Thakur", "Wagh", "Salunkhe"]
COMPANIES = ["Sahyadri Heli Charters", "Deccan Rotors", "Konkan Air Services", "Godavari Aviation",
             "Western Ghats Heli", "Vidarbha Air Taxi", "Marathwada Wings", "Sinhagad Aero",
             "Arabian Coast Helicopters", "Lonavala Skyways", "Shirdi Air Link", "Kolhapur Heli Services",
             "Nashik Valley Aviation", "Mahabaleshwar Air", "Pune Executive Jets", "Juhu Rotorcraft",
             "Aurangabad Heritage Air", "Nagpur Central Aviation", "Ratnagiri Coastal Air", "Satara Heli Works",
             "Alibaug Sea Air", "Raigad Fort Flyers", "Tadoba Wildlife Air", "Ajanta Air Charters",
             "Matheran Hill Heli"]
CITIES = ["Mumbai", "Pune", "Nashik", "Aurangabad", "Nagpur", "Kolhapur", "Shirdi"]
BASES = {"Mumbai": "Juhu", "Pune": "Pune", "Nashik": "Ozar", "Aurangabad": "Chikalthana",
         "Nagpur": "Nagpur", "Kolhapur": "Kolhapur", "Shirdi": "Shirdi"}
ROUTES = [("Mumbai", "Shirdi"), ("Pune", "Mahabaleshwar"), ("Mumbai", "Lonavala"), ("Mumbai", "Nashik"),
          ("Nagpur", "Mumbai"), ("Pune", "Shirdi"), ("Mumbai", "Alibaug"), ("Aurangabad", "Ajanta"),
          ("Mumbai", "Pune"), ("Kolhapur", "Pune"), ("Nashik", "Trimbakeshwar"), ("Nagpur", "Tadoba")]
AIRCRAFT = [("Bell 407", 6, 95000), ("Airbus H125", 5, 110000), ("AgustaWestland AW109", 6, 160000),
            ("Bell 412", 12, 210000), ("Robinson R66", 4, 60000), ("Beechcraft King Air C90", 7, 140000),
            ("Airbus H130", 7, 125000)]
VENDORS = ["Shell Aviation Fuel", "Mahindra Ground Handling", "Juhu Aerodrome Services", "Sky Catering Co",
           "AeroTech MRO", "Deccan Insurance Brokers", "Pune Hangar Rentals"]

# Trip statuses in roughly the mix a running business would show.
STATUS_MIX = (["completed"] * 10 + ["confirmed"] * 4 + ["pilot_assigned"] * 2 + ["pending_quotes"] * 4
              + ["quotes_received"] * 3 + ["cancelled"] * 2)
FUTURE = {"confirmed", "pilot_assigned", "pending_quotes", "quotes_received"}


def _id(kind: str, n: int) -> str:
    return f"{PREFIX}{kind}-{n:02d}"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def build_demo_data(now: datetime, password_hash: str, customer_user_id: Optional[str] = None,
                    operator_user_id: Optional[str] = None, operator_id: Optional[str] = None) -> Dict[str, List[dict]]:
    """Every demo document, keyed by collection. Same input gives the same data."""
    rnd = random.Random(42)
    naive = now.astimezone(timezone.utc).replace(tzinfo=None)  # booking code stores naive UTC strings
    data: Dict[str, List[dict]] = {c: [] for c in COLLECTIONS}
    unusable_hash = "!demo-no-password"

    # Customers: the first one is the customer@ login.
    customers = []
    for i in range(COUNT):
        n = i + 1
        name = f"{FIRST[i]} {LAST[i]}"
        uid = customer_user_id if (n == 1 and customer_user_id) else _id("customer", n)
        email = DEMO_CUSTOMER_EMAIL if n == 1 else f"{FIRST[i].lower()}.{LAST[i].lower()}@example.com"
        customers.append(uid)
        if uid.startswith(PREFIX):
            data["users"].append({
                "id": uid, "email": email, "password_hash": password_hash if n == 1 else unusable_hash,
                "full_name": "Rahul Patil" if n == 1 else name, "phone": f"98{rnd.randint(10000000, 99999999)}",
                "role": "customer", "roles": ["customer"], "region": "Maharashtra", "is_verified": True,
                "is_active": True, "created_by": CREATED_BY,
                "created_at": _iso(now - timedelta(days=rnd.randint(20, 400))), "updated_at": _iso(now)})

    # Operators: 20 approved, 3 waiting for verification, 2 suspended.
    operators = []
    for i in range(COUNT):
        n = i + 1
        city = CITIES[i % len(CITIES)]
        oid = operator_id if (n == 1 and operator_id) else _id("operator", n)
        operators.append(oid)
        if not oid.startswith(PREFIX):
            continue
        owner = operator_user_id if (n == 1 and operator_user_id) else _id("opuser", n)
        if owner.startswith(PREFIX):
            data["users"].append({
                "id": owner, "email": f"ops{n:02d}@example.com", "password_hash": unusable_hash,
                "full_name": f"{FIRST[-1 - i]} {LAST[-1 - i]}", "phone": f"97{rnd.randint(10000000, 99999999)}",
                "role": "operator", "roles": ["operator"], "region": "Maharashtra", "is_verified": True,
                "is_active": True, "created_by": CREATED_BY, "created_at": _iso(now - timedelta(days=300)),
                "updated_at": _iso(now)})
        status, verification = ("active", "approved")
        if n in (22, 23, 24):
            status, verification = ("pending", "pending")
        elif n in (20, 21):
            status, verification = ("suspended", "approved")
        data["operators"].append({
            "id": oid, "user_id": owner, "company_name": COMPANIES[i], "base_city": city,
            "contact_person": f"{FIRST[-1 - i]} {LAST[-1 - i]}", "contact_phone": f"02{rnd.randint(10000000, 99999999)}",
            "contact_email": f"ops{n:02d}@example.com", "gstin": f"27AAB{rnd.randint(1000, 9999)}C1Z{n % 10}",
            "status": status, "verification_status": verification, "region": "Maharashtra",
            "documents": [], "commission_rate": 10.0, "average_rating": round(rnd.uniform(4.1, 4.9), 1),
            "created_at": _iso(naive - timedelta(days=rnd.randint(30, 500))), "updated_at": _iso(naive)})

    # Aircraft and pilots: the first operator gets six aircraft and five pilots, the rest one each.
    fleet_owner = [operators[0]] * 6 + operators[1:20]
    aircraft_ids = []
    for i in range(COUNT):
        n = i + 1
        model, seats, rate = AIRCRAFT[i % len(AIRCRAFT)]
        owner = fleet_owner[i]
        city = CITIES[i % len(CITIES)]
        aid = _id("aircraft", n)
        aircraft_ids.append((aid, owner, model))
        maintenance = "scheduled_maintenance" if n in (4, 15) else "operational"
        data["aircraft"].append({
            "id": aid, "operator_id": owner, "aircraft_type": model, "registration_number": f"VT-D{chr(65 + i % 26)}{chr(75 + i % 15)}",
            "capacity": seats, "base_location": BASES[city], "hourly_rate": rate,
            "is_available": maintenance == "operational" and n % 5 != 0, "maintenance_status": maintenance,
            "documents": [], "created_at": _iso(naive - timedelta(days=200)), "updated_at": _iso(naive)})
        if n <= 6:
            data["aircraft_documents"].append({
                "id": _id("aircraft-doc", n), "aircraft_id": aid, "operator_id": owner,
                "document_type": ["airworthiness", "insurance", "registration"][n % 3], "status": "completed",
                "expiry_date": _iso(now + timedelta(days=[12, 25, 90, 180, 21, 300][n - 1])),
                "created_at": _iso(now - timedelta(days=100))})
    pilot_owner = [operators[0]] * 5 + operators[1:21]
    pilot_ids = []
    for i in range(COUNT):
        n = i + 1
        pid = _id("pilot", n)
        pilot_ids.append((pid, pilot_owner[i]))
        name = f"Capt. {FIRST[(i + 7) % COUNT]} {LAST[(i + 3) % COUNT]}"
        data["pilots"].append({
            "id": pid, "operator_id": pilot_owner[i], "full_name": name, "name": name,
            "license_number": f"CPL-H-{4100 + n}", "phone": f"99{rnd.randint(10000000, 99999999)}",
            "email": f"pilot{n:02d}@example.com", "experience_years": rnd.randint(4, 22),
            "is_available": n % 4 != 0, "documents": [], "created_at": _iso(naive - timedelta(days=180)),
            "updated_at": _iso(naive)})
        if n <= 5:
            data["pilot_documents"].append({
                "id": _id("pilot-doc", n), "pilot_id": pid, "operator_id": pilot_owner[i],
                "document_type": ["medical", "license", "type_rating"][n % 3], "status": "completed",
                "expiry_date": _iso(now + timedelta(days=[9, 28, 120, 200, 18][n - 1])),
                "created_at": _iso(now - timedelta(days=90))})

    # Bookings: 25 for the demo customer, 50 more across the other customers.
    # The first operator flies 25 of them; the rest go to the other approved operators.
    first_fleet = [a for a in aircraft_ids if a[1] == operators[0]]
    first_pilots = [p for p in pilot_ids if p[1] == operators[0]]
    for i in range(COUNT * 3):
        n = i + 1
        status = STATUS_MIX[i % len(STATUS_MIX)]
        customer = customers[0] if i < COUNT else customers[1 + (i % (COUNT - 1))]
        frm, to = ROUTES[(i * 7 + i // 5) % len(ROUTES)]
        if status in FUTURE:
            departure = now + timedelta(days=1 + (i * 3) % 40, hours=(i * 5) % 9)
        else:
            departure = now - timedelta(days=2 + (i * 4) % 160)
        created = min(departure, now) - timedelta(days=3 + i % 10)
        if i % 9 == 0:
            created = now - timedelta(hours=1 + i % 6)  # a few booked today
        priced = status not in {"pending_quotes", "quotes_received"}
        on_first = i % 3 == 0
        operator = operators[0] if on_first else operators[1 + (i % 19)]
        if on_first:
            aircraft_id, _, model = first_fleet[i % len(first_fleet)]
            pilot_id = first_pilots[i % len(first_pilots)][0]
        else:
            aircraft_id, _, model = aircraft_ids[6 + (i % 19)]
            pilot_id = pilot_ids[5 + (i % 20)][0]
        amount = float(rnd.randrange(60000, 420000, 2500)) if priced else 0.0
        data["bookings"].append({
            "id": _id("booking", n), "booking_number": f"AY-{2300 + n}", "customer_id": customer,
            "operator_id": operator if priced else None, "aircraft_id": aircraft_id if priced else None,
            "pilot_id": pilot_id if status in {"pilot_assigned", "completed"} else None,
            "from_location": frm, "to_location": to, "trip_type": "round_trip" if i % 4 == 0 else "one_way",
            "departure_date": _iso(departure.astimezone(timezone.utc).replace(tzinfo=None)),
            "passengers": 2 + i % 5, "status": status, "quote_ids": [], "accepted_quote_id": None,
            "total_amount": amount, "commission_amount": round(amount * 0.10, 2),
            "region": "Maharashtra", "landing_permissions": [],
            "special_requirements": "Temple darshan timing" if to == "Shirdi" else None,
            "created_at": _iso(created.astimezone(timezone.utc).replace(tzinfo=None)),
            "updated_at": _iso(naive)})

    # Inquiries sent to the first operator: open ones need a quote, the rest were answered.
    open_bookings = [b for b in data["bookings"] if b["status"] in {"pending_quotes", "quotes_received"}]
    for i in range(COUNT):
        n = i + 1
        booking = open_bookings[i % len(open_bookings)] if i < 8 else data["bookings"][i * 3]
        data["inquiries"].append({
            "id": _id("inquiry", n), "booking_id": booking["id"], "operator_id": operators[0],
            "status": "pending" if i < 8 else ("quoted" if i < 16 else "accepted"),
            "created_at": _iso(now - timedelta(hours=1 + i * 5))})

    # Settlements: payouts for completed trips, newest still to be paid.
    completed = [b for b in data["bookings"] if b["status"] == "completed"]
    for i in range(COUNT):
        n = i + 1
        group = completed[i:i + 2] or completed[:2]
        total = sum(b["total_amount"] for b in group)
        commission = sum(b["commission_amount"] for b in group)
        status = "pending" if i < 6 else ("approved" if i < 10 else "paid")
        data["settlements"].append({
            "id": _id("settlement", n), "settlement_number": f"SET{(now - timedelta(days=i * 4)):%Y%m%d}DM{n:02d}",
            "operator_id": group[0]["operator_id"], "booking_ids": [b["id"] for b in group],
            "total_booking_amount": total, "commission_amount": commission, "payout_amount": total - commission,
            "status": status, "created_by": CREATED_BY, "created_at": _iso(naive - timedelta(days=i * 4))})

    # Landing permissions for helipads and villages, five waiting for admin.
    places = ["Shirdi helipad", "Mahabaleshwar ground", "Ajanta village field", "Trimbakeshwar helipad",
              "Alibaug beach pad", "Tadoba gate helipad", "Lonavala school ground"]
    for i in range(COUNT):
        n = i + 1
        booking = data["bookings"][i * 2]
        data["landing_permissions"].append({
            "id": _id("landing", n), "booking_id": booking["id"], "customer_id": booking["customer_id"],
            "location": places[i % len(places)], "noc_type": "district_collector" if i % 2 else "private_owner",
            "document_url": "", "approval_status": "pending" if i < 5 else ("rejected" if i == 5 else "approved"),
            "created_at": _iso(naive - timedelta(days=i))})

    # Finance: today's collections, vendor bills, approvals, TDS and salary runs.
    for i in range(COUNT):
        n = i + 1
        amount = float(rnd.randrange(15000, 380000, 500))
        data["payment_transactions"].append({
            "id": _id("txn", n), "transaction_type": "booking_payment" if i % 3 else "vendor_payment",
            "reference": f"AY-{2300 + n}", "gross_amount": amount, "deductions": 0, "net_amount": amount,
            "payment_mode": ["upi", "neft", "card", "imps"][i % 4], "utr_number": f"UTR{rnd.randint(10 ** 9, 10 ** 10 - 1)}",
            "status": "completed" if i % 6 else "processing",
            "initiated_at": _iso(now - timedelta(minutes=20 + i * 35) if i < 5 else now - timedelta(days=i)),
            "completed_at": _iso(now - timedelta(days=i))})
        gross = float(rnd.randrange(8000, 240000, 500))
        tds = round(gross * 0.02, 2)
        bill_status = "approved" if i < 8 else ("pending" if i < 12 else "paid")
        data["vendor_bills"].append({
            "id": _id("bill", n), "bill_number": f"BILL-DM{n:03d}", "vendor_name": VENDORS[i % len(VENDORS)],
            "vendor_code": f"VEN{100 + i % len(VENDORS)}", "invoice_number": f"INV/{now:%y}/{4000 + n}",
            "invoice_date": _iso(now - timedelta(days=10 + i)), "due_date": _iso(now + timedelta(days=15 - i)),
            "description": ["Jet A-1 fuel", "Ground handling", "Parking and landing", "Crew catering",
                            "Scheduled maintenance", "Hull insurance", "Hangar rent"][i % 7],
            "category": "operations", "gross_amount": gross, "gst_amount": round(gross * 0.18, 2),
            "tds_applicable": True, "tds_section": "194C", "tds_rate": 2, "tds_amount": tds,
            "net_payable": round(gross - tds, 2), "status": bill_status,
            "payment_status": "paid" if bill_status == "paid" else "unpaid",
            "created_at": _iso(now - timedelta(days=10 + i)), "created_by": CREATED_BY})
        approval_status = ["pending_finance", "pending_admin", "pending_hr"][i % 3] if i < 7 else "approved"
        data["approval_requests"].append({
            "id": _id("approval", n), "request_number": f"APR-DM-{n:03d}",
            "type": ["vendor_payment", "salary_payment", "refund", "expense"][i % 4],
            "reference_id": _id("bill", n), "amount": gross, "requestor_id": CREATED_BY,
            "requestor_name": f"{FIRST[i]} {LAST[i]}", "status": approval_status,
            "requires_hr": i % 4 == 1, "requires_finance": True, "requires_admin": gross > 100000,
            "hr_approval": None, "finance_approval": None, "admin_approval": None,
            "details": {"description": data["vendor_bills"][-1]["description"]}, "notes": [],
            "created_at": _iso(now - timedelta(days=i)), "updated_at": _iso(now - timedelta(days=i)),
            "completed_at": None})

    quarter = f"Q{((now.month - 1) // 3) + 1}"
    fy = f"{now.year}-{now.year + 1}" if now.month >= 4 else f"{now.year - 1}-{now.year}"
    for n in range(1, 5):
        data["tds_entries"].append({
            "id": _id("tds", n), "batch_id": None, "quarter": quarter if n <= 2 else f"Q{((now.month - 4) // 3) % 4 + 1}",
            "financial_year": fy, "total_tds": float(rnd.randrange(6000, 22000, 100)), "vendor_count": 3 + n,
            "entries": [], "created_at": _iso(now - timedelta(days=n * 20))})
    for n in range(1, 7):
        month_start = (now.replace(day=1) - timedelta(days=28 * (n - 1))).replace(day=1)
        staff = 18 + n % 3
        data["salary_runs"].append({
            "id": _id("salary", n), "run_number": f"SALRUN-{month_start:%Y%m}-DM{n:02d}",
            "month": month_start.month, "year": month_start.year, "employee_count": staff,
            "total_gross": staff * 68000.0, "total_deductions": staff * 9200.0, "total_net": staff * 58800.0,
            "gateway": "mock", "payment_mode": "neft", "status": "pending_approval" if n == 1 else "completed",
            "approval_id": None, "created_by": CREATED_BY, "created_at": _iso(month_start + timedelta(days=27))})

    # VIP points for the demo customer (Gold tier starts at 15,000 lifetime points).
    data["loyalty_profiles"].append({
        "id": _id("loyalty", 1), "user_id": customers[0], "total_points": 18420, "available_points": 4820,
        "lifetime_points": 18420, "tier": "gold", "total_bookings": 10, "total_spent": 1842000,
        "joined_at": _iso(now - timedelta(days=400))})
    return data


async def _find_id(db, collection: str, query: dict) -> Optional[str]:
    doc = await db[collection].find_one(query, {"_id": 0, "id": 1})
    return doc["id"] if doc else None


async def seed_demo_data(db, app_env: str, password_hash: str, now: Optional[datetime] = None) -> Dict[str, int]:
    """Insert the demo data once. Returns how many documents went into each collection."""
    if app_env in PRODUCTION_ENVS:
        logger.warning("Demo data is never seeded in %s", app_env)
        return {}
    if await db.bookings.find_one({"id": _id("booking", 1)}):
        return {}  # already seeded
    now = now or datetime.now(timezone.utc)

    customer_user_id = await _find_id(db, "users", {"email": DEMO_CUSTOMER_EMAIL})
    operator_user_id = await _find_id(db, "users", {"email": DEMO_OPERATOR_EMAIL})
    operator_id = await _find_id(db, "operators", {"user_id": operator_user_id}) if operator_user_id else None

    data = build_demo_data(now, password_hash, customer_user_id, operator_user_id, operator_id)
    if customer_user_id and await db.loyalty_profiles.find_one({"user_id": customer_user_id}):
        data["loyalty_profiles"] = []  # never touch a real customer's points
    counts = {}
    for collection, docs in data.items():
        if docs:
            await db[collection].insert_many([dict(d) for d in docs])
            counts[collection] = len(docs)
    logger.info("Seeded demo data: %s", counts)
    return counts


async def remove_demo_data(db) -> Dict[str, int]:
    """Delete every document the seeder created (ids starting with demo-, logins it created)."""
    removed = {}
    for collection in COLLECTIONS:
        query = {"id": {"$regex": f"^{PREFIX}"}}
        if collection == "users":
            query = {"$or": [query, {"created_by": CREATED_BY}]}
        result = await db[collection].delete_many(query)
        if result.deleted_count:
            removed[collection] = result.deleted_count
    logger.info("Removed demo data: %s", removed)
    return removed


async def run_from_env(db, app_env: str, mode: str, password: str) -> Dict[str, int]:
    """DEMO_DATA=seed (default in dev) seeds once, DEMO_DATA=remove deletes it, DEMO_DATA=off does nothing."""
    from auth import get_password_hash

    mode = (mode or "seed").strip().lower()
    if mode == "remove":
        return await remove_demo_data(db)
    if mode != "seed":
        return {}
    # The demo customer signs in with the same dev password as the staff logins; without one it cannot sign in.
    password_hash = get_password_hash(password) if len(password or "") >= 12 else "!demo-no-password-" + uuid4().hex
    return await seed_demo_data(db, app_env, password_hash)
