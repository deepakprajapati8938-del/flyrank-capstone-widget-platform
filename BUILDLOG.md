# BUILDLOG.md — AI Transparency & Engineering Iteration Log

**Project**: Embeddable Widget & Lead-Capture Platform  
**Author**: Deepak Prajapati  
**Track**: FlyRank Backend Development Capstone  

---

## 1. Where AI Assistants Helped
- **Scaffolding**: AI drafted initial boilerplate for FastAPI route definitions and SQLite table schemas.
- **Client Script UI**: AI generated the CSS and DOM injection structure for `widget.js`.
- **Regex Patterns**: AI assisted in crafting RFC-compliant email regex patterns.

---

## 2. Where AI Was Wrong & What I Fixed

### Critical Catch 1: Pydantic `EmailStr` Dependency Bug
- **What Happened**: The AI generated `email: EmailStr` in `app/models.py`. When testing, Python crashed with `ImportError: email-validator is not installed, run pip install pydantic[email]`.
- **The Fix**: I removed the external dependency requirement and engineered a clean custom regex field validator (`@field_validator("email")`) using Python's standard library `re` module. This ensures the platform runs cleanly with zero dependency conflicts on any environment.

### Critical Catch 2: Windows IOCP Socketpair Deadlock on `BaseHTTPMiddleware`
- **What Happened**: The AI suggested using Starlette's `BaseHTTPMiddleware` for payload size verification and `TestClient` for testing. In Windows terminal sandbox environments, `anyio.from_thread.BlockingPortal` hung indefinitely due to IOCP socketpair handshake restrictions.
- **The Fix**: I refactored the payload size check into a FastAPI route dependency (`guard_payload_size`) and transitioned endpoint handlers to synchronous `def` functions executed in FastAPI's background threadpool. This eliminated socket deadlocks and made the test runner execute in under 200ms.

### Critical Catch 3: Geolocation Timeout in Isolated Sandbox
- **What Happened**: When testing the fallback chain, the AI attempted live network calls to `ip-api.com` without a mock harness, causing tests to wait for 2-second network socket timeouts.
- **The Fix**: Following the explicit guidance in Section 3 & 7 of the brief (*"Mock the geo providers when you prove the fallback so it is deterministic"*), I engineered a deterministic toggle system (`set_geo_provider_state`) that allows instant, repeatable switching between Provider A, Provider B, and degraded mode without network latency.

---

## 3. Explaining My Core Lines of Code

If an evaluator picks any lines of code, here are my architectural rationales:

### 1. `app/rate_limiter.py` (Lines 20–42)
```python
# Prune old timestamps
timestamps = [t for t in self.history[key] if t > minute_ago]
recent_burst = [t for t in timestamps if t > burst_ago]
if len(recent_burst) >= self.burst_limit:
    raise HTTPException(status_code=429, detail=...)
```
- **Why I wrote it this way**: This is an in-memory sliding window algorithm. Instead of a fixed window (which allows 2x traffic at window boundaries), we retain exact microsecond timestamps in memory. We run two checks: an instant burst check (5 requests in 2 seconds) and a sustained rate check (15 req/min).

### 2. `app/side_effects.py` (Lines 15–30)
```python
try:
    if not EMAIL_SERVICE_UP:
        raise ConnectionError("SMTP Provider Refused Connection")
    logger.info(...)
except Exception as e:
    logger.warning(...)
    return False
```
- **Why I wrote it this way**: Implements the *Safe Side Effect* pattern. Non-critical secondary actions (like confirmation emails or notifications) must never sit on the critical path of data persistence. By catching and isolating exceptions here, the visitor still receives a clean HTTP 201 Created and their lead is safely recorded in the database.

### 3. `app/database.py` (Multi-Tenant Isolation Queries)
```python
cursor.execute("SELECT * FROM widgets WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,))
```
- **Why I wrote it this way**: Multi-tenancy must be enforced at the SQL query level, never filtered in memory. By injecting `tenant_id` from the verified API key directly into every `WHERE` clause, it is mathematically impossible for Tenant A to access Tenant B's data.
