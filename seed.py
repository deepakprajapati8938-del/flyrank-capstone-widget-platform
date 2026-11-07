import os
import sqlite3
from datetime import datetime, timedelta
from app.database import init_db, get_db

def seed_database():
    print("[*] Initializing Database Schema...")
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Clear previous seed data
    cursor.execute("DELETE FROM submissions;")
    cursor.execute("DELETE FROM widgets;")
    cursor.execute("DELETE FROM tenants;")

    print("[*] Seeding Multi-Tenant Test Data...")
    
    # 1. Seed Tenants
    tenants = [
        ("tenant_acme", "Acme Corporation", "acme_secret_key_123", "ops@acme.com", datetime.utcnow().isoformat()),
        ("tenant_globex", "Globex Global", "globex_secret_key_456", "admin@globex.com", datetime.utcnow().isoformat())
    ]
    cursor.executemany("INSERT INTO tenants (id, name, api_key, email, created_at) VALUES (?, ?, ?, ?, ?)", tenants)

    # 2. Seed Widgets
    widgets = [
        ("w_acme_contact", "tenant_acme", "contact", "Get in Touch with Sales", "Questions about our enterprise plan? Leave a message.", "Send Message", "*", datetime.utcnow().isoformat()),
        ("w_acme_newsletter", "tenant_acme", "signup", "Join Our Tech Newsletter", "Weekly engineering teardowns and architecture insights.", "Subscribe Now", "*", datetime.utcnow().isoformat()),
        ("w_globex_feedback", "tenant_globex", "cta", "Product Beta Feedback", "Tell us what feature you want us to build next.", "Submit Feedback", "*", datetime.utcnow().isoformat())
    ]
    cursor.executemany("INSERT INTO widgets (id, tenant_id, type, title, description, button_text, allowed_origin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", widgets)

    # 3. Seed Existing Submissions
    now = datetime.utcnow()
    submissions = [
        ("sub_demo_01", "w_acme_contact", "tenant_acme", "alex@startup.io", "Alex Chen", "Interested in your API enterprise pricing tier.", "103.21.244.2", "India", "Indore", "Mozilla/5.0", (now - timedelta(days=2)).isoformat()),
        ("sub_demo_02", "w_acme_contact", "tenant_acme", "sarah@techcorp.com", "Sarah Miller", "Can we schedule a 15-minute demo call?", "8.8.8.8", "United States", "Mountain View", "Mozilla/5.0", (now - timedelta(days=1)).isoformat()),
        ("sub_demo_03", "w_acme_newsletter", "tenant_acme", "david@developer.dev", "David Ross", "", "1.1.1.1", "Australia", "Sydney", "Mozilla/5.0", now.isoformat()),
        ("sub_demo_04", "w_globex_feedback", "tenant_globex", "elena@agency.co", "Elena Rostova", "Please add webhook notifications for Slack.", "185.220.101.5", "Germany", "Frankfurt", "Mozilla/5.0", now.isoformat())
    ]
    cursor.executemany("""
    INSERT INTO submissions (id, widget_id, tenant_id, email, name, message, visitor_ip, country, city, user_agent, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, submissions)

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("DEMO SEED DATA SUMMARY")
    print("=" * 60)
    print("Tenant A (Acme Corp):")
    print("  - API Key:  acme_secret_key_123")
    print("  - Widget 1: w_acme_contact  (Contact Form)")
    print("  - Widget 2: w_acme_newsletter  (Newsletter Signup)")
    print("  - Embed Snippet: <script src=\"http://localhost:8000/static/widget.js?id=w_acme_contact\" async></script>")
    print("\nTenant B (Globex Global - Isolated Tenant):")
    print("  - API Key:  globex_secret_key_456")
    print("  - Widget 3: w_globex_feedback  (Product Feedback)")
    print("=" * 60 + "\n")
    print("[*] Seed complete. You can now start the server and run tests.")

if __name__ == "__main__":
    seed_database()
