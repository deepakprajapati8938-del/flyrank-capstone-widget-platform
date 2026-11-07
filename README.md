# Embeddable Widget & Lead-Capture Platform

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063.svg)](https://docs.pydantic.dev/)
[![Probes](https://img.shields.io/badge/Acceptance%20Probes-7%2F7%20Passed%20(100%25)-success.svg)](EVIDENCE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-grade, multi-tenant backend platform that lets customers create customizable lead-capture widgets, embed them on external websites with a single `<script>` line, and safely ingest public cross-origin submissions protected by boundary validation, sliding-window rate limiting, honeypot spam traps, and geolocation fallback chains.

---

## 1. What It Does and For Whom

- **The Problem**: Lead capture forms are notoriously fragile: receiving unvetted public traffic from external websites exposes APIs to cross-origin CORS errors, malicious payload floods, bot spam, and upstream service outages.
- **The Solution**: An all-in-one embeddable platform:
  1. **Multi-Tenant Admin API**: Customers authenticate, create, and manage isolated widgets.
  2. **1-Line Embed Snippet**: Generates `<script src=".../widget.js?id=..."></script>` for one-click installation on any external website.
  3. **Cached Asset Delivery**: Serves versioned JavaScript (`widget.js`) with 24-hour immutable cache headers and dynamic configurations with short-lived cache headers.
  4. **Hardened Public Ingestion**: Handles CORS preflight (`OPTIONS`), validates boundaries via Pydantic, blocks bot spam via invisible honeypots, rate-limits bursts (`HTTP 429`), enriches IP with a multi-provider fallback chain, and isolates side effects (email failures never break submissions).
- **For Whom**: SaaS businesses, marketing platforms, and web developers who need to capture leads on third-party domains without building form backends from scratch.

---

## 2. Architecture Overview

```mermaid
flowchart TD
    subgraph Owner["1. Widget Owner (Authenticated)"]
        A["Dashboard / API Client"] -->|"CRUD Requests<br/>(X-API-Key)"| B["FastAPI Admin Endpoints"]
        B --> C[("SQLite Database<br/>Tenant Isolated")]
        B -->|Generates| D["Embed Snippet<br/>&lt;script src='.../widget.js?id=...'&gt;"]
    end

    subgraph ClientSite["2. External Website (Origin: localhost:5500)"]
        D -->|Pasted on Page| E["Browser Loads widget.js"]
        E -->|"GET /widgets/:id/config<br/>(Cache-Control: 60s)"| F["FastAPI Config Endpoint"]
        F -->|JSON Response| G["Dynamically Renders Lead Form"]
    end

    subgraph PublicBackend["3. Hardened Public Ingestion (Origin: localhost:8000)"]
        G -->|"POST /submissions<br/>(Cross-Origin)"| H{"1. CORS & Preflight (OPTIONS)"}
        H --> I{"2. Boundary Validation<br/>(Email format, Payload &lt; 100KB)"}
        I -->|Invalid| J["Clean HTTP 4xx JSON Error"]
        I -->|Valid| K{"3. Abuse Defense"}
        K -->|Burst > 5 req / 2s| L["HTTP 429 Too Many Requests"]
        K -->|Honeypot Filled (Bot)| M["HTTP 400 Spam Detected"]
        K -->|Legitimate| N{"4. Geo Fallback Chain"}
        
        N -->|Provider A (ip-api.com)| O["Enriched (Country, City)"]
        N -->|Provider A Fails -> Provider B| O
        N -->|Both Down| P["Degrade Gracefully (Country=None)"]
        
        O --> Q[("Store in Database")]
        P --> Q
        
        Q --> R["5. Safe Side Effect (Confirmation Email)"]
        R -->|Throws ConnectionError| S["Isolated in Log (Non-Blocking)"]
        R -->|Success| T["Email Dispatched"]
        
        Q --> U["HTTP 201 Created Response"]
    end
```

---

## 3. Quick Setup & Run Instructions

Follow these exact steps to run the platform locally on a clean machine.

### Prerequisites
- Python 3.10 or higher
- Git

### Step 1: Clone and Navigate
```bash
git clone https://github.com/deepakprajapati8938-del/flyrank-capstone-widget-platform.git
cd flyrank-capstone-widget-platform
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Seed Demo Data
Initialize the database and populate sample tenants, widgets, and submissions:
```bash
python seed.py
```
*Output Summary*:
- **Tenant A (Acme Corp)**: API Key `acme_secret_key_123` | Widget `w_acme_contact`
- **Tenant B (Globex Global)**: API Key `globex_secret_key_456` | Widget `w_globex_feedback`

### Step 4: Boot the API Server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The server will start at `http://127.0.0.1:8000`. Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

### Step 5: Run the Acceptance Probes Test Suite
Execute the deterministic automated test suite verifying all 7 core criteria:
```bash
python run_probes.py
```
*Result*: `PROBE AUDIT RESULT: 7 / 7 Tests Passed (100.0%)`.

---

## 4. Testing the Second-Origin Customer Website

To see cross-origin embedding working live between two distinct local origins:

1. **Keep API Server running** on port 8000.
2. In a second terminal, start an HTTP server in `test_customer_site` on **port 5500**:
   ```bash
   python -m http.server 5500 --directory test_customer_site
   ```
3. Open `http://localhost:5500` in your web browser.
4. You will see the widget form loaded dynamically via `<script>` tag from `localhost:8000` into `localhost:5500`. Fill out the form and submit: it executes a real cross-origin POST request with CORS preflight and displays the success notification!

---

## 5. API Reference & cURL Transcripts

### Public Submission Endpoint
```bash
curl -X POST "http://127.0.0.1:8000/submissions" \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5500" \
  -d '{
    "widget_id": "w_acme_contact",
    "name": "Jane Doe",
    "email": "jane@example.com",
    "message": "Interested in enterprise pricing tier.",
    "hp_company_field": ""
  }'
```
**Response (HTTP 201 Created)**:
```json
{
  "id": "sub_a98f12c3e456",
  "widget_id": "w_acme_contact",
  "email": "jane@example.com",
  "status": "stored",
  "country": "India",
  "city": "Indore",
  "created_at": "2026-11-07T08:14:25.079994"
}
```

### Authenticated Owner Dashboard Stats
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/dashboard/stats" \
  -H "X-API-Key: acme_secret_key_123"
```
**Response (HTTP 200 OK)**:
```json
{
  "total_submissions": 4,
  "per_widget_stats": [
    {"title": "Get in Touch with Sales", "id": "w_acme_contact", "count": 3},
    {"title": "Join Our Tech Newsletter", "id": "w_acme_newsletter", "count": 1}
  ],
  "geo_breakdown": [
    {"country": "India", "count": 2},
    {"country": "United States", "count": 1},
    {"country": "Australia", "count": 1}
  ]
}
```

---

## 6. Honest Limitations & Production Considerations

1. **In-Memory Rate Limiting**:
   - The sliding-window rate limiter stores timestamps in application memory. In a distributed multi-node cluster, rate limits must be backed by a shared Redis cluster (`redis-py` or Token Bucket in Dragonfly).
2. **Synchronous Email Side-Effect**:
   - Although failures are completely isolated and never break responses, the email dispatch currently runs synchronously inside the request lifecycle. In high-throughput production setups, this should be offloaded to Inngest or Celery background job queues.
3. **Shadow DOM Encapsulation**:
   - The widget CSS currently injects a `.flyrank-widget-card` class into the host page. While styles are scoped, aggressive host page CSS resets can occasionally alter typography. Encapsulating the widget inside a `ShadowRoot` (`element.attachShadow({mode: 'open'})`) would provide 100% style isolation.

---

## 7. Submission Deliverables Checklist
- [x] **DESIGN.md**: Committed 1-page design doc with ER diagram, data contracts, and non-goals.
- [x] **capstone.yaml**: Machine-readable evaluator manifest.
- [x] **EVIDENCE.md**: Pasted execution transcripts proving all 6 requirements.
- [x] **BUILDLOG.md**: AI usage disclosure, critical catches, and code line explanations.
- [x] **test_customer_site/index.html**: Second-origin test page verifying CORS.
- [x] **tests/test_probes.py & run_probes.py**: Automated acceptance probe suite passing 100%.

#   f l y r a n k - c a p s t o n e - w i d g e t - p l a t f o r m  
 