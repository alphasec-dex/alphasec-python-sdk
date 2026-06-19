"""Perp (perpetual futures) support for the AlphaSec SDK."""

from .constants import BUY, SELL, GTC, IOC, POST, MARKET, SPOT_TO_PERP, PERP_TO_SPOT
from .agent import PerpAgent
from .async_agent import AsyncPerpAgent
from .ws import decode_perp_event, PerpEvent

__all__ = [
    "BUY",
    "SELL",
    "GTC",
    "IOC",
    "POST",
    "MARKET",
    "SPOT_TO_PERP",
    "PERP_TO_SPOT",
    "PerpAgent",
    "AsyncPerpAgent",
    "decode_perp_event",
    "PerpEvent",
]
