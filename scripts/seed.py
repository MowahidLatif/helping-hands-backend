#!/usr/bin/env python3
"""
Seed database with test data.

Usage: poetry run python scripts/seed.py
Requires: migrations applied (poetry run alembic upgrade head)
"""
import os
import sys

# Ensure app is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from app.utils.db import get_db_connection


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed():
    with get_db_connection() as conn, conn.cursor() as cur:
        # Check if already seeded
        cur.execute("SELECT COUNT(*) FROM users WHERE email = 'demo@example.com'")
        if cur.fetchone()[0] > 0:
            print("Already seeded (demo@example.com exists). Use --force to re-seed.")
            return

        # 1. Demo user + org
        pw_hash = _hash("demo123456")
        cur.execute(
            """
            INSERT INTO users (email, password_hash, name)
            VALUES ('demo@example.com', %s, 'Demo User')
            RETURNING id
            """,
            (pw_hash,),
        )
        user_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO organizations (name, subdomain)
            VALUES ('Demo Org', 'demo')
            ON CONFLICT (subdomain) DO UPDATE SET name = 'Demo Org'
            RETURNING id
            """
        )
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM organizations WHERE subdomain = 'demo'")
            row = cur.fetchone()
        org_id = row[0]

        cur.execute(
            """
            INSERT INTO org_users (org_id, user_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT (org_id, user_id) DO NOTHING
            """,
            (org_id, user_id),
        )

        # 2. Test campaigns
        cur.execute(
            """
            INSERT INTO campaigns (org_id, title, slug, goal, status, custom_domain)
            VALUES
                (%s, 'Help Build the School', 'help-build-school', 10000, 'active', NULL),
                (%s, 'Community Garden', 'community-garden', 5000, 'draft', NULL),
                (%s, 'Emergency Relief Fund', 'emergency-relief', 25000, 'active', NULL)
            ON CONFLICT (org_id, slug) DO NOTHING
            RETURNING id, title, slug
            """,
            (org_id, org_id, org_id),
        )
        campaigns = cur.fetchall()

        # 3. Sample donations (if we have campaigns)
        if campaigns:
            camp_id = campaigns[0][0]
            cur.execute(
                """
                INSERT INTO donations (org_id, campaign_id, amount_cents, currency, donor_email, status)
                VALUES
                    (%s, %s, 2500, 'usd', 'donor1@example.com', 'succeeded'),
                    (%s, %s, 5000, 'usd', 'donor2@example.com', 'succeeded'),
                    (%s, %s, 1000, 'usd', 'donor3@example.com', 'succeeded')
                """,
                (org_id, camp_id, org_id, camp_id, org_id, camp_id),
            )

        conn.commit()
        print("Seeded successfully.")
        print("  Demo user: demo@example.com / demo123456")
        print("  Org subdomain: demo")
        print("  Campaigns: 3 (active, draft, active)")
        print("  Donations: 3 on first campaign")


def force_seed():
    """Clear test data and re-seed. Use with caution."""
    with get_db_connection() as conn, conn.cursor() as cur:
        # Delete giveaway_logs first (FK to donations)
        cur.execute(
            """
            DELETE FROM giveaway_logs
            WHERE winner_donation_id IN (
                SELECT id FROM donations WHERE donor_email LIKE '%%@example.com'
            )
            """
        )
        cur.execute("DELETE FROM donations WHERE donor_email LIKE '%%@example.com'")
        cur.execute("DELETE FROM campaign_media WHERE 1=1")
        cur.execute(
            "DELETE FROM campaigns WHERE org_id IN (SELECT id FROM organizations WHERE subdomain = 'demo')"
        )
        cur.execute(
            "DELETE FROM org_users WHERE org_id IN (SELECT id FROM organizations WHERE subdomain = 'demo')"
        )
        cur.execute("DELETE FROM organizations WHERE subdomain = 'demo'")
        cur.execute("DELETE FROM users WHERE email = 'demo@example.com'")
        conn.commit()
    print("Cleared test data. Seeding...")
    seed()


if __name__ == "__main__":
    if "--force" in sys.argv:
        force_seed()
    else:
        seed()
