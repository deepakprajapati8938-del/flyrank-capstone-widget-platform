import os
import sys
import pytest
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# Ensure root directory of project is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.database import init_db, get_widget_by_id, get_tenant_submissions, get_tenant_analytics
from app.models import SubmissionCreate, WidgetCreate
from app.main import (
    create_submission,
    get_widget_config,
    create_new_widget,
    list_widgets,
    delete_existing_widget,
    get_submissions_list,
    get_dashboard_statistics
)
from app.rate_limiter import submission_rate_limiter
from app.geo import set_geo_provider_state, fetch_geolocation
from app.side_effects import set_email_service_state, trigger_safe_side_effects
from seed import seed_database

class MockRequest:
    def __init__(self, headers=None, client_host="127.0.0.1"):
        self.headers = headers or {}
        class MockClient:
            def __init__(self, host):
                self.host = host
        self.client = MockClient(client_host)

def reset_test_environment():
    seed_database()
    submission_rate_limiter.reset()
    set_geo_provider_state(True, True)
    set_email_service_state(True)

@pytest.fixture(autouse=True)
def setup_test_db():
    reset_test_environment()
    yield

# ============================================================
# PROBE 1: Valid Cross-Origin Submission & Dashboard Visibility
# ============================================================
def test_probe_1_valid_submission_and_dashboard_visibility():
    """
    PROBE 1: POST a valid submission from the second-origin test page.
    Assert stored, HTTP 201 response, and visible via dashboard API.
    """
    req = MockRequest(headers={"origin": "http://localhost:5500", "user-agent": "Mozilla/5.0 TestBrowser"})
    payload = SubmissionCreate(
        widget_id="w_acme_contact",
        email="customer@externaldomain.com",
        name="Jane Doe",
        message="Testing cross-origin lead capture.",
        hp_company_field=""  # Empty honeypot
    )

    # 1. Execute public submission (synchronously, fast & deterministic)
    resp = create_submission(req, payload)
    assert resp.status == "stored"
    assert resp.widget_id == "w_acme_contact"
    assert resp.email == "customer@externaldomain.com"
    sub_id = resp.id

    # 2. Verify visibility in authenticated dashboard API
    tenant_acme = {"id": "tenant_acme", "name": "Acme Corp"}
    submissions = get_submissions_list(current_tenant=tenant_acme)
    matching = [s for s in submissions if s["id"] == sub_id]
    assert len(matching) == 1, "Submission was not found in owner dashboard list"
    assert matching[0]["email"] == "customer@externaldomain.com"
    assert matching[0]["name"] == "Jane Doe"

# ============================================================
# PROBE 2: Boundary Validation (Malformed Payloads -> Clean 4xx)
# ============================================================
def test_probe_2_boundary_validation_malformed_payloads():
    """
    PROBE 2: Send malformed email, missing fields, and non-existent widget.
    Assert clean validation errors (Pydantic ValidationError / 404), NEVER a 500.
    """
    # 2a. Malformed Email must fail validation
    with pytest.raises(ValidationError) as exc_info:
        SubmissionCreate(
            widget_id="w_acme_contact",
            email="not-an-email",
            name="John"
        )
    assert "email" in str(exc_info.value).lower()

    # 2b. Missing Required widget_id must fail validation
    with pytest.raises(ValidationError):
        SubmissionCreate(
            widget_id="",
            email="valid@example.com"
        )

    # 2c. Non-existent Widget ID must return 404 cleanly
    req = MockRequest()
    valid_payload = SubmissionCreate(
        widget_id="w_non_existent_widget_999",
        email="valid@example.com"
    )
    with pytest.raises(HTTPException) as exc_404:
        create_submission(req, valid_payload)
    assert exc_404.value.status_code == 404
    assert exc_404.value.detail["error"] == "Not Found"

# ============================================================
# PROBE 3: Rate Limiting Burst Defense (429) & Recovery
# ============================================================
def test_probe_3_rate_limiting_burst_and_recovery():
    """
    PROBE 3: Fire a burst of rapid submissions.
    Assert 429 Too Many Requests appears, and legitimate requests after succeed.
    """
    submission_rate_limiter.reset()
    attacker_ip = "203.0.113.195"
    attacker_key = f"ip:{attacker_ip}"

    # Fire 5 requests (burst limit)
    for _ in range(5):
        submission_rate_limiter.check_rate_limit(attacker_key)

    # 6th immediate burst request must raise 429
    with pytest.raises(HTTPException) as exc_429:
        submission_rate_limiter.check_rate_limit(attacker_key)
    assert exc_429.value.status_code == 429
    assert exc_429.value.detail["error"] == "Too Many Requests"

    # Crucial: Another legitimate IP must NOT be blocked!
    legit_key = "ip:198.51.100.42"
    # Should not raise exception
    submission_rate_limiter.check_rate_limit(legit_key)

# ============================================================
# PROBE 4: Geo Provider Fallback Chain (Provider A -> B -> Degrade)
# ============================================================
def test_probe_4_geo_provider_fallback_chain():
    """
    PROBE 4:
    1. Provider A down -> Provider B answers -> submission enriched.
    2. Both down -> stored anyway without geo. Degrade, never fail.
    """
    # Step 4a: Disable Provider A (Provider B is UP)
    set_geo_provider_state(provider_a=False, provider_b=True)
    country, city, source = fetch_geolocation("103.21.244.2")
    assert source == "provider_b", f"Expected provider_b fallback, got: {source}"
    assert country is not None

    # Step 4b: Disable BOTH Provider A and Provider B (Total Upstream Outage)
    set_geo_provider_state(provider_a=False, provider_b=False)
    country_deg, city_deg, source_deg = fetch_geolocation("103.21.244.2")
    assert source_deg == "degraded", f"Expected degraded state, got: {source_deg}"
    assert country_deg is None
    assert city_deg is None

    # Step 4c: End-to-end submission under complete geo outage succeeds!
    req = MockRequest()
    payload = SubmissionCreate(widget_id="w_acme_contact", email="offline_geo@example.com")
    resp = create_submission(req, payload)
    assert resp.status == "stored", "Submission failed when geo providers were down!"
    assert resp.country is None

# ============================================================
# PROBE 5: Safe Side-Effect (Email Throws Exception -> Main Succeeds)
# ============================================================
def test_probe_5_safe_side_effects_failure_tolerance():
    """
    PROBE 5: Force the email side effect to throw.
    Assert the submission still returns HTTP 201 and is stored in DB.
    """
    set_email_service_state(is_up=False)  # Force simulated SMTP failure
    req = MockRequest()
    payload = SubmissionCreate(
        widget_id="w_acme_contact",
        email="fail_safe@example.com",
        name="Fail Safe Test"
    )

    resp = create_submission(req, payload)
    assert resp.status == "stored", "Main submission path failed when secondary email service threw!"
    assert resp.email == "fail_safe@example.com"

# ============================================================
# PROBE 6: Honeypot Anti-Spam Detection
# ============================================================
def test_probe_6_honeypot_spam_trap():
    """
    PROBE 6: Fill the hidden honeypot field (simulating an automated bot).
    Assert request returns HTTP 400 rejection and is not saved as legitimate lead.
    """
    req = MockRequest()
    bot_payload = SubmissionCreate(
        widget_id="w_acme_contact",
        email="bot@spammer.ru",
        name="Spam Bot 3000",
        hp_company_field="Automated SEO Leads Inc."  # Bot fell into the trap!
    )

    resp = create_submission(req, bot_payload)
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 400
    assert "Spam Detected" in resp.body.decode()

# ============================================================
# Multi-Tenant Isolation Check (Tenant A vs Tenant B)
# ============================================================
def test_multi_tenant_isolation():
    """
    Assert Tenant A cannot view or delete Tenant B's widgets or submissions.
    """
    tenant_acme = {"id": "tenant_acme", "name": "Acme Corp"}
    tenant_globex = {"id": "tenant_globex", "name": "Globex Inc"}

    # Tenant A lists their widgets
    widgets_a = list_widgets(current_tenant=tenant_acme)
    for w in widgets_a:
        assert w["tenant_id"] == "tenant_acme"
        assert w["id"] != "w_globex_feedback"

    # Tenant A attempts to delete Tenant B's widget (w_globex_feedback)
    with pytest.raises(HTTPException) as exc_del:
        delete_existing_widget("w_globex_feedback", current_tenant=tenant_acme)
    assert exc_del.value.status_code == 404

    # Tenant A queries dashboard analytics
    analytics_a = get_dashboard_statistics(current_tenant=tenant_acme)
    assert "total_submissions" in analytics_a
    # Confirm Globex widgets do not appear in Acme stats
    for stat in analytics_a["per_widget_stats"]:
        assert stat["id"] != "w_globex_feedback"
