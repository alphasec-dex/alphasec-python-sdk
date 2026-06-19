"""Integer enum mappings for perp (perpetual futures) operations.

Plain module-level integers, matching the spot ``alphasec/api/constants.py`` style.
Values are the wire contract (see alphasec-rust-sdk src/perp/types.rs).
"""

# Order side
BUY = 0
SELL = 1

# Time in force
GTC = 0     # Good-till-cancelled
IOC = 1     # Immediate-or-cancel
POST = 2    # Post-only
MARKET = 3  # Market order (server ignores price)

# Transfer direction between Spot and Perp wallets
SPOT_TO_PERP = 0  # deposit (0x12)
PERP_TO_SPOT = 1  # withdraw (0x44)
