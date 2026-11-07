import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "widget_platform.db"))

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Tenants Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        api_key TEXT UNIQUE NOT NULL,
        email TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # 2. Widgets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS widgets (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        button_text TEXT NOT NULL,
        allowed_origin TEXT DEFAULT '*',
        created_at TEXT NOT NULL,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );
    """)

    # 3. Submissions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id TEXT PRIMARY KEY,
        widget_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        email TEXT NOT NULL,
        name TEXT,
        message TEXT,
        visitor_ip TEXT,
        country TEXT,
        city TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (widget_id) REFERENCES widgets(id),
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    );
    """)

    # Indexes for high performance & multi-tenant isolation
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_widget_tenant ON widgets(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_tenant_widget ON submissions(tenant_id, widget_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_created ON submissions(created_at);")

    conn.commit()
    conn.close()

# Database Helper Functions
def get_tenant_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenants WHERE api_key = ?", (api_key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_widget_by_id(widget_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM widgets WHERE id = ?", (widget_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_tenant_widgets(tenant_id: str) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM widgets WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_widget(widget_data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO widgets (id, tenant_id, type, title, description, button_text, allowed_origin, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        widget_data["id"],
        widget_data["tenant_id"],
        widget_data["type"],
        widget_data["title"],
        widget_data["description"],
        widget_data["button_text"],
        widget_data.get("allowed_origin", "*"),
        widget_data.get("created_at", datetime.utcnow().isoformat())
    ))
    conn.commit()
    conn.close()
    return widget_data

def delete_widget(widget_id: str, tenant_id: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM widgets WHERE id = ? AND tenant_id = ?", (widget_id, tenant_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def insert_submission(sub_data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO submissions (id, widget_id, tenant_id, email, name, message, visitor_ip, country, city, user_agent, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sub_data["id"],
        sub_data["widget_id"],
        sub_data["tenant_id"],
        sub_data["email"],
        sub_data.get("name"),
        sub_data.get("message"),
        sub_data.get("visitor_ip"),
        sub_data.get("country"),
        sub_data.get("city"),
        sub_data.get("user_agent"),
        sub_data.get("created_at", datetime.utcnow().isoformat())
    ))
    conn.commit()
    conn.close()
    return sub_data

def get_tenant_submissions(tenant_id: str, widget_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    if widget_id:
        cursor.execute("SELECT * FROM submissions WHERE tenant_id = ? AND widget_id = ? ORDER BY created_at DESC", (tenant_id, widget_id))
    else:
        cursor.execute("SELECT * FROM submissions WHERE tenant_id = ? ORDER BY created_at DESC", (tenant_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_tenant_analytics(tenant_id: str) -> Dict[str, Any]:
    conn = get_db()
    cursor = conn.cursor()
    
    # Total count
    cursor.execute("SELECT COUNT(*) as total FROM submissions WHERE tenant_id = ?", (tenant_id,))
    total = cursor.fetchone()["total"]
    
    # Per-widget breakdown
    cursor.execute("""
    SELECT w.title, w.id, COUNT(s.id) as count 
    FROM widgets w 
    LEFT JOIN submissions s ON w.id = s.widget_id 
    WHERE w.tenant_id = ? 
    GROUP BY w.id
    """, (tenant_id,))
    per_widget = [dict(r) for r in cursor.fetchall()]
    
    # Geo breakdown
    cursor.execute("""
    SELECT COALESCE(country, 'Unknown') as country, COUNT(*) as count 
    FROM submissions 
    WHERE tenant_id = ? 
    GROUP BY country 
    ORDER BY count DESC
    """, (tenant_id,))
    geo_breakdown = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return {
        "total_submissions": total,
        "per_widget_stats": per_widget,
        "geo_breakdown": geo_breakdown
    }
