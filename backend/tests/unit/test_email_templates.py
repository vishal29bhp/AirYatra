"""E-mail bodies are HTML: user-supplied values must be escaped (bandit B701). Subjects stay plain text."""
from services.email_service import EmailService


def test_user_values_are_html_escaped_in_bodies():
    html = EmailService()._render_template("<p>Hello {{ customer_name }}</p>", {"customer_name": "<img src=x onerror=alert(1)>"})
    assert "<img" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_template_markup_itself_is_kept():
    assert EmailService()._render_template("<b>{{ amount }}</b>", {"amount": "₹1,000"}) == "<b>₹1,000</b>"


def test_subjects_are_not_html_escaped():
    subject = EmailService()._render_template("Booking for {{ customer_name }}", {"customer_name": "D'Souza & Co"}, html=False)
    assert subject == "Booking for D'Souza & Co"
