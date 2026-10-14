"""What the website chat assistant knows and may say.

AirYatra currently flies within Maharashtra only. Until the pricing and routes knowledge base is
added, the assistant must not quote fares: it sends people to the quote and booking flow instead.
"""
from typing import Dict, List, Optional

SERVICE_STATE = "Maharashtra"
SERVICE_CITIES = (
    "Mumbai", "Pune", "Nashik", "Shirdi", "Aurangabad (Chhatrapati Sambhajinagar)", "Nagpur",
    "Kolhapur", "Lonavala", "Mahabaleshwar", "Alibag", "Ratnagiri", "Solapur",
)
MAX_MESSAGE_CHARS = 2000
HISTORY_MESSAGES = 10


def chat_owner(user: Optional[dict]) -> str:
    """Whose conversation this is: the user's id, or 'guest' for visitors who are not signed in."""
    return user["id"] if user else "guest"


def history_text(messages: List[Dict]) -> str:
    """The last HISTORY_MESSAGES turns as 'Customer:' / 'Assistant:' lines."""
    lines = []
    for m in messages[-HISTORY_MESSAGES:]:
        role = "Customer" if m.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {m.get('content', '')}")
    return "\n".join(lines)


def system_prompt(customer_name: str, history: str) -> str:
    return f"""You are the AirYatra assistant, the helpful guide for AirYatra, a helicopter and private charter booking service.

Service area: AirYatra currently operates only within {SERVICE_STATE}, India. Popular places include {", ".join(SERVICE_CITIES)}.
- If someone asks about a trip that starts or ends outside {SERVICE_STATE}, say politely that AirYatra flies only within {SERVICE_STATE} for now and offer the nearest {SERVICE_STATE} option.
- Do not quote prices, fares, flight times or availability. Say that the exact fare depends on the route, aircraft and date, and ask them to use "Get a quote" or "Book a flight" on the website, or sign in to see live quotes from operators.
- You can explain how booking works, what to expect on the day, luggage and passenger basics, BLACK membership (Silver, Gold and Platinum tiers with member discounts), loyalty points, the document vault and corporate travel.
- If you do not know something, say so and suggest contacting AirYatra support. Never invent routes, operators or policies.

Customer name: {customer_name}
Reply in the language the customer writes in (English, Hindi, Marathi or Hinglish). Keep replies under 120 words, warm and professional.

Previous conversation:
{history}"""
