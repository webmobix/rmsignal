"""A short fingerprint of what a market outlook says, so an instrument outlook can tell whether it changed."""

import hashlib
import json

from .contracts import MarketOutlook


def market_digest(o: MarketOutlook) -> str:
    views = [[v.segment, v.direction, v.horizon, v.confidence] for v in o.views]
    return hashlib.sha256(json.dumps(views, separators=(",", ":")).encode()).hexdigest()[:16]
