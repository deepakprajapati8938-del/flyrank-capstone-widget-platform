import os
import uuid
from datetime import datetime
from fastapi import FastAPI, Request, Response, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.database import (
    init_db,
    get_widget_by_id,
    insert_widget,
    get_tenant_widgets,
    delete_widget,
    insert_submission,
    get_tenant_submissions,
    get_tenant_analytics
)
from app.models import (
    WidgetCreate,
    WidgetResponse,
    WidgetConfigResponse,
    SubmissionCreate,
    SubmissionResponse
)
from app.auth import get_current_tenant
from app.rate_limiter import submission_rate_limiter
from app.geo import fetch_geolocation
from app.side_effects import trigger_safe_side_effects

# Initialize Database tables on module import
init_db()

app = FastAPI(
    title="Embeddable Widget & Lead-Capture Platform",
    description="Multi-tenant, abuse-resistant, embeddable widget and lead capture API.",
    version="1.0.0"
)

# ------------------------------------------------------------
# 1. CORS Middleware (Public Internet Gateway)
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows cross-origin requests from any customer site
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PUT"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# ------------------------------------------------------------
# 2. Oversized Payload Guard Dependency (Max 100KB)
# ------------------------------------------------------------
def guard_payload_size(request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 100_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": "Payload Too Large", "message": "Request payload exceeds 100KB limit"}
        )

# ------------------------------------------------------------
# 3. Clean Boundary Validation Error Handler (Never 500)
# ------------------------------------------------------------
@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Malformed payload submitted",
            "details": exc.errors()
        }
    )

# ------------------------------------------------------------
# 4. Public Widget Delivery (Cached, CDN-Ready)
# ------------------------------------------------------------
@app.get("/static/widget.js")
def serve_widget_script(response: Response):
    widget_js_path = os.path.join(os.path.dirname(__file__), "static", "widget.js")
    if not os.path.exists(widget_js_path):
        raise HTTPException(status_code=404, detail="Widget script bundle not found")
        
    # HTTP Caching Headers: Cache for 24h as a versioned bundle
    response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    response.headers["Content-Type"] = "application/javascript; charset=utf-8"
    with open(widget_js_path, "r", encoding="utf-8") as f:
        return Response(content=f.read(), media_type="application/javascript", headers=response.headers)

@app.get("/widgets/{widget_id}/config", response_model=WidgetConfigResponse)
def get_widget_config(widget_id: str, response: Response):
    widget = get_widget_by_id(widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "Widget does not exist"})
        
    # Short-lived cache header for dynamic configuration
    response.headers["Cache-Control"] = "public, max-age=60"
    return WidgetConfigResponse(
        id=widget["id"],
        type=widget["type"],
        title=widget["title"],
        description=widget["description"],
        button_text=widget["button_text"]
    )

# ------------------------------------------------------------
# 5. Public Hardened Submission Endpoint
# ------------------------------------------------------------
@app.post(
    "/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(guard_payload_size)]
)
def create_submission(request: Request, payload: SubmissionCreate):
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "127.0.0.1")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    # Abuse Defense 1: Rate Limiting (Burst & Sliding Window)
    submission_rate_limiter.check_rate_limit(f"ip:{client_ip}")

    # Abuse Defense 2: Honeypot Spam Check
    # If a bot automatically fills the invisible 'hp_company_field', reject or drop immediately
    if payload.hp_company_field and payload.hp_company_field.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Spam Detected", "message": "Honeypot field filled by automated agent."}
        )

    # Validate that widget exists
    widget = get_widget_by_id(payload.widget_id)
    if not widget:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "Invalid widget ID."})

    # Geolocation Fallback Chain (Provider A -> Provider B -> Graceful Degradation)
    country, city, geo_source = fetch_geolocation(client_ip)

    # Database Persistence
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    sub_data = {
        "id": sub_id,
        "widget_id": payload.widget_id,
        "tenant_id": widget["tenant_id"],
        "email": str(payload.email),
        "name": payload.name or "",
        "message": payload.message or "",
        "visitor_ip": client_ip,
        "country": country,
        "city": city,
        "user_agent": request.headers.get("user-agent", "Unknown"),
        "created_at": datetime.utcnow().isoformat()
    }
    insert_submission(sub_data)

    # Safe Secondary Side-Effect (Email notification / Webhook)
    # Even if this fails or throws an exception, the main 201 response succeeds!
    trigger_safe_side_effects(sub_data)

    return SubmissionResponse(
        id=sub_id,
        widget_id=payload.widget_id,
        email=str(payload.email),
        status="stored",
        country=country,
        city=city,
        created_at=sub_data["created_at"]
    )

# ------------------------------------------------------------
# 6. Authenticated Widget Management API (Multi-Tenant Isolated)
# ------------------------------------------------------------
@app.post("/api/v1/widgets", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
def create_new_widget(
    payload: WidgetCreate,
    current_tenant: dict = Depends(get_current_tenant)
):
    widget_id = f"w_{uuid.uuid4().hex[:10]}"
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    snippet = f'<script src="{base_url}/static/widget.js?id={widget_id}" async></script>'
    
    widget_data = {
        "id": widget_id,
        "tenant_id": current_tenant["id"],
        "type": payload.type,
        "title": payload.title,
        "description": payload.description,
        "button_text": payload.button_text,
        "allowed_origin": payload.allowed_origin or "*",
        "created_at": datetime.utcnow().isoformat()
    }
    insert_widget(widget_data)
    
    return WidgetResponse(
        **widget_data,
        embed_snippet=snippet
    )

@app.get("/api/v1/widgets")
def list_widgets(current_tenant: dict = Depends(get_current_tenant)):
    # Strictly filtered by authenticated tenant_id
    widgets = get_tenant_widgets(current_tenant["id"])
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    for w in widgets:
        w["embed_snippet"] = f'<script src="{base_url}/static/widget.js?id={w["id"]}" async></script>'
    return widgets

@app.get("/api/v1/widgets/{widget_id}", response_model=WidgetResponse)
def get_single_widget(
    widget_id: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    widget = get_widget_by_id(widget_id)
    if not widget or widget["tenant_id"] != current_tenant["id"]:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "Widget does not exist"})
        
    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    snippet = f'<script src="{base_url}/static/widget.js?id={widget["id"]}" async></script>'
    return WidgetResponse(**widget, embed_snippet=snippet)

@app.delete("/api/v1/widgets/{widget_id}")
def delete_existing_widget(
    widget_id: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    success = delete_widget(widget_id, current_tenant["id"])
    if not success:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "Widget not found or unauthorized"})
    return {"status": "success", "message": f"Widget {widget_id} deleted"}

# ------------------------------------------------------------
# 7. Authenticated Owner Dashboard & Analytics API
# ------------------------------------------------------------
@app.get("/api/v1/dashboard/submissions")
def get_submissions_list(
    widget_id: str = None,
    current_tenant: dict = Depends(get_current_tenant)
):
    return get_tenant_submissions(current_tenant["id"], widget_id)

@app.get("/api/v1/dashboard/stats")
def get_dashboard_statistics(current_tenant: dict = Depends(get_current_tenant)):
    return get_tenant_analytics(current_tenant["id"])
