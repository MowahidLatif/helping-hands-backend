"""
Locust load tests for the Donations API.

Install: pip install locust
Run: locust -f locustfile.py --host=http://127.0.0.1:5050

For headless: locust -f locustfile.py --host=http://127.0.0.1:5050 \
    --users 10 --spawn-rate 2 --run-time 1m --headless
"""

import os
from locust import HttpUser, task, between


class DonationsAPIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Optional: login to get token for authenticated endpoints."""
        self.token = None
        # Skip auth if no test credentials
        if os.getenv("LOCUST_AUTH_EMAIL") and os.getenv("LOCUST_AUTH_PASSWORD"):
            r = self.client.post(
                "/api/auth/login",
                json={
                    "email": os.getenv("LOCUST_AUTH_EMAIL"),
                    "password": os.getenv("LOCUST_AUTH_PASSWORD"),
                },
            )
            if r.status_code == 200 and "access_token" in r.json():
                self.token = r.json()["access_token"]

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    @task(10)
    def ping(self):
        self.client.get("/__ping")

    @task(8)
    def root(self):
        self.client.get("/")

    @task(5)
    def metrics(self):
        self.client.get("/admin/metrics")

    @task(3)
    def campaign_progress(self):
        # Use a placeholder UUID; replace with real campaign_id for meaningful test
        cid = os.getenv("LOCUST_CAMPAIGN_ID", "00000000-0000-0000-0000-000000000001")
        self.client.get(f"/api/campaigns/{cid}/progress")

    @task(2)
    def campaign_media(self):
        cid = os.getenv("LOCUST_CAMPAIGN_ID", "00000000-0000-0000-0000-000000000001")
        self.client.get(f"/api/campaigns/{cid}/media")

    @task(1)
    def public_org_home(self):
        sub = os.getenv("LOCUST_ORG_SUBDOMAIN", "demo")
        self.client.get("/", headers={"Host": f"{sub}.helpinghands.local:5050"})
