import os


def is_raffle_enabled_for_org(org_id: str) -> bool:
    """Return True if the raffle feature is accessible for the given org.

    Controlled by two env vars:
      RAFFLE_FEATURE_ENABLED=true  — enables for all orgs
      RAFFLE_BETA_ORG_IDS=id1,id2  — enables for specific orgs (comma-separated)
    """
    if os.getenv("RAFFLE_FEATURE_ENABLED", "false").lower() == "true":
        return True
    allowlist = os.getenv("RAFFLE_BETA_ORG_IDS", "")
    return org_id in {x.strip() for x in allowlist.split(",") if x.strip()}
