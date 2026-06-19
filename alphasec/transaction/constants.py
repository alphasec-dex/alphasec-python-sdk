ALPHASEC_ORDER_CONTRACT_ADDR = "0x00000000000000000000000000000000000000cc"
ALPHASEC_SYSTEM_CONTRACT_ADDR = "0x0000000000000000000000000000000000000064"
ALPHASEC_ZK_INTERFACE_CONTRACT_ADDR = "0x00000000000000000000000000000000000000C8"
ALPHASEC_GATEWAY_ROUTER_CONTRACT_ADDR = "0xD2b30f9548DEE14093CF903ec70866469EFff97A"
ALPHASEC_ERC20_GATEWAY_CONTRACT_ADDR = "0x71E210Eb76ce6541BCA48dccA04cF127ee629Ae9"

MAINNET_INBOX_CONTRACT_ADDR = "0xA0E8dbC168c41B349C164681b3184Bbea7C9c4d6"
MAINNET_OUTBOX_CONTRACT_ADDR = "0x94F41d7F6eFD109A6EFde7613d6Fc3d6894e2CEC"
MAINNET_ERC20_GATEWAY_CONTRACT_ADDR = "0xec5cD95184124Ee2cc4C90fb7f74E3b717160d51"
MAINNET_ERC20_ROUTER_CONTRACT_ADDR = "0x6c1f5fef508715b6E1a541594046DB2831f0F6CE"

KAIROS_INBOX_CONTRACT_ADDR = "0xA0E8dbC168c41B349C164681b3184Bbea7C9c4d6"
KAIROS_OUTBOX_CONTRACT_ADDR = "0x94F41d7F6eFD109A6EFde7613d6Fc3d6894e2CEC"
KAIROS_ERC20_GATEWAY_CONTRACT_ADDR = "0xec5cD95184124Ee2cc4C90fb7f74E3b717160d51"
KAIROS_ERC20_ROUTER_CONTRACT_ADDR = "0x6c1f5fef508715b6E1a541594046DB2831f0F6CE"

ALPHASEC_NATIVE_TOKEN_ID = '1'
ALPHASEC_MAINNET_CHAIN_ID = 48217
ALPHASEC_TESTNET_CHAIN_ID = 41001

DexCommandSessionCreate = 0x01
DexCommandSessionUpdate = 0x02
DexCommandSessionDelete = 0x03

DexCommandSession       = 0x01
DexCommandTransfer      = 0x02
DexCommandTokenTransfer = 0x11
DexCommandOrder         = 0x21
DexCommandCancel        = 0x22
DexCommandCancelAll     = 0x23
DexCommandModify        = 0x24
DexCommandStopOrder     = 0x25

# Perp (perpetual futures) command bytes.
# Source of truth: alphasec-rust-sdk src/types/constants.rs dex_commands.
DexCommandPerpDeposit            = 0x12  # implemented (Spot -> Perp)
DexCommandPerpOrder              = 0x41  # implemented
DexCommandPerpCancel             = 0x42  # implemented
DexCommandPerpCancelAll          = 0x43  # implemented
DexCommandPerpWithdraw           = 0x44  # implemented (Perp -> Spot)
DexCommandPerpSetLeverage        = 0x45  # implemented
DexCommandPerpSetMarginType      = 0x46  # constant only (not implemented)
DexCommandPerpUpdateIsolatedMargin = 0x47  # constant only (not implemented)
DexCommandPerpTriggerOrder       = 0x48  # constant only (not implemented)
DexCommandPerpTriggerBatch       = 0x49  # constant only (not implemented)
DexCommandPerpModify             = 0x4A  # implemented
DexCommandPerpPositionTpsl       = 0x4B  # constant only (not implemented)
