"""
Per-campaign media upload quotas.
"""

from __future__ import annotations

import os

MAX_CAMPAIGN_IMAGES = int(os.getenv("MAX_CAMPAIGN_IMAGES", "50"))
MAX_CAMPAIGN_VIDEOS = int(os.getenv("MAX_CAMPAIGN_VIDEOS", "10"))
MAX_CAMPAIGN_DOCS = int(os.getenv("MAX_CAMPAIGN_DOCS", "25"))
