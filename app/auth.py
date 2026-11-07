from fastapi import Header, HTTPException
from typing import Optional, Dict, Any
from app.database import get_tenant_by_api_key

def get_current_tenant(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    api_key = x_api_key
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization.split(" ")[1]
        else:
            api_key = authorization
            
    if not api_key:
        raise HTTPException(
            status_code=401, 
            detail={"error": "Unauthorized", "message": "Missing API key. Provide via 'X-API-Key' header."}
        )
        
    tenant = get_tenant_by_api_key(api_key)
    if not tenant:
        raise HTTPException(
            status_code=401, 
            detail={"error": "Unauthorized", "message": "Invalid API key provided."}
        )
        
    return tenant
