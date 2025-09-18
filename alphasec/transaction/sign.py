import time
from eth_account import Account
from eth_account.messages import encode_typed_data
import json
import base64
from typing import Literal, Optional
from eth_utils.address import is_address
from web3 import Web3

from alphasec.api.constants import ALPHASEC_KAIROS_URL, ALPHASEC_MAINNET_URL, KAIROS_URL, MAINNET_URL

from .schemas import (
    StopOrderModel,
    ValueTransferModel,
    TokenTransferModel,
    OrderModel,
    TpslModel,
    CancelModel,
    CancelAllModel,
    ModifyModel,
    SessionContextModel,
)

from .constants import (
    ALPHASEC_GATEWAY_ROUTER_CONTRACT_ADDR,
    ALPHASEC_ORDER_CONTRACT_ADDR,
    ALPHASEC_SYSTEM_CONTRACT_ADDR,
    ALPHASEC_ZK_INTERFACE_CONTRACT_ADDR,
    ALPHASEC_NATIVE_TOKEN_ID,
    KAIROS_ERC20_GATEWAY_CONTRACT_ADDR,
    KAIROS_ERC20_ROUTER_CONTRACT_ADDR,
    KAIROS_INBOX_CONTRACT_ADDR,
    KAIROS_OUTBOX_CONTRACT_ADDR,
    MAINNET_ERC20_GATEWAY_CONTRACT_ADDR,
    MAINNET_ERC20_ROUTER_CONTRACT_ADDR,
    MAINNET_INBOX_CONTRACT_ADDR,
    MAINNET_OUTBOX_CONTRACT_ADDR,
    DexCommandSession,
    DexCommandTransfer,
    DexCommandTokenTransfer,
    DexCommandOrder,
    DexCommandCancel,
    DexCommandCancelAll,
    DexCommandModify,
    DexCommandStopOrder,
)

from .abi import (
    L2_ERC20_ROUTER_ABI,
    NATIVE_L1_ABI,
    L2_SYSTEM_ABI,
    ERC20_ABI,
    ERC20_ROUTER_ABI,
    ZK_INTERFACE_ABI,
    L1_OUTBOX_ABI,
)

def address_to_bytes(address):
    return bytes.fromhex(address[2:] if address.startswith("0x") else address)

def format_decimal(value: float, decimals: int = 3) -> str:
    """Format decimal value to string with specified decimal places precision.
    
    Args:
        value: Decimal value to format
        decimals: Number of decimal places (default: 3)
    
    Returns:
        String representation with specified decimal places
    """
    if not isinstance(value, (int, float)):
        raise ValueError("Value must be int or float")
    
    # Format to specified decimal places and return as string
    return f"{value:.{decimals}f}"

class AlphasecSigner:
    l1_address: str
    l1_wallet: Account
    l2_wallet: Account
    session_enabled: bool
    network: Literal["mainnet", "kairos"]
    alphasec_endpoint_url: str

    def __init__(self, config: dict):
        if not "l1_address" in config:
            raise ValueError("l1_address should be set")
        self.l1_address = config["l1_address"]
        if "l1_wallet" in config:
            self.l1_wallet = Account.from_key(config["l1_wallet"])
        if "l2_wallet" in config:
            self.l2_wallet = Account.from_key(config["l2_wallet"])
        if "session_enabled" in config:
            self.session_enabled = config["session_enabled"]
        if "network" in config:
            self.network = config["network"]


    def get_wallet(self):
        if self.session_enabled:
            return self.l2_wallet
        return self.l1_wallet

    def session_register_typed_data(self, session_addr: str, nonce: int, expiry: int):
        return {
            "domain": {
                "name": "DEXSignTransaction",
                "version": "1",
                "chainId": 1001,
                "verifyingContract": "0x0000000000000000000000000000000000000000",
            },
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "RegisterSessionWallet": [
                    {"name": "sessionWallet", "type": "address"},
                    {"name": "expiry", "type": "uint64"},
                    {"name": "nonce", "type": "uint64"},
                ],
            },
            "primaryType": "RegisterSessionWallet",
            "message": {
                "sessionWallet": session_addr,
                "expiry": str(int(expiry)),
                "nonce": str(int(nonce)),
            },
        }


    def create_session_data(self, cmd: int, session_addr: str, timestamp_ms: int, expires_at: int, metadata: bytes = b"") -> bytes:

        if self.session_enabled:
            raise ValueError("Session is already enabled")
        if self.get_wallet() is None:
            raise ValueError("Wallet is not set")

        # Build and sign EIP-712 typed data
        typed = self.session_register_typed_data(session_addr, timestamp_ms, expires_at)
        signable = encode_typed_data(full_message=typed)
        signed = self.get_wallet().sign_message(signable)
        signature_b64 = base64.b64encode(bytes(signed.signature)).decode("ascii")

        model = SessionContextModel(
            type=cmd,
            publickey=session_addr,
            expiresAt=expires_at,
            nonce=timestamp_ms,
            l1owner=self.get_wallet().address, # TODO: change to l1_address
            l1signature=signature_b64,
            metadata=metadata.decode("utf-8") if isinstance(metadata, (bytes, bytearray)) and metadata else None,
        )
        payload_bytes = json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")
        return bytes([DexCommandSession]) + payload_bytes


    def create_value_transfer_data(self, to: str, value: int) -> bytes:
        wallet = self.get_wallet()
        model = ValueTransferModel(l1owner=wallet.address, to=to, value=value) # TODO: change to l1_address
        return bytes([DexCommandTransfer]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_token_transfer_data(self, to: str, value: int, token: str) -> bytes:
        wallet = self.get_wallet()
        model = TokenTransferModel(l1owner=wallet.address, to=to, value=value, token=token) # TODO: change to l1_address
        return bytes([DexCommandTokenTransfer]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_order_data(
        self,
        base_token: str,
        quote_token: str,
        side: int,
        price: float,
        quantity: float,
        order_type: int,
        order_mode: int,
        tp_limit: Optional[float] = None,
        sl_trigger: Optional[float] = None,
        sl_limit: Optional[float] = None,
    ) -> bytes:
        # Format decimal values to strings with 3 decimal places precision
        price_str = format_decimal(price)
        quantity_str = format_decimal(quantity)
        
        tpsl_model = None
        if tp_limit is not None or sl_trigger is not None:
            tp_limit_str = format_decimal(tp_limit) if tp_limit is not None else None
            sl_trigger_str = format_decimal(sl_trigger) if sl_trigger is not None else None
            sl_limit_str = format_decimal(sl_limit) if sl_limit is not None else None
            tpsl_model = TpslModel(tp_limit=tp_limit_str, sl_trigger=sl_trigger_str, sl_limit=sl_limit_str)

        wallet = self.get_wallet()
        model = OrderModel(
            l1owner=wallet.address, # TODO: change to l1_address
            base_token=base_token,
            quote_token=quote_token,
            side=side,
            price=price_str,
            quantity=quantity_str,
            order_type=order_type,
            order_mode=order_mode,
            tpsl=tpsl_model,
        )
        return bytes([DexCommandOrder]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_cancel_data(self, order_id: str) -> bytes:
        wallet = self.get_wallet()
        model = CancelModel(l1owner=wallet.address, order_id=order_id) # TODO: change to l1_address
        return bytes([DexCommandCancel]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")
        

    def create_cancel_all_data(self) -> bytes:
        wallet = self.get_wallet()
        model = CancelAllModel(l1owner=wallet.address) # TODO: change to l1_address
        return bytes([DexCommandCancelAll]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")
        

    def create_modify_data(self, order_id: str, new_price: Optional[float], new_qty: Optional[float], order_mode: int) -> bytes:
        # Format decimal values to strings with 3 decimal places precision
        new_price_str = format_decimal(new_price) if new_price is not None else None
        new_qty_str = format_decimal(new_qty) if new_qty is not None else None
        
        wallet = self.get_wallet()
        model = ModifyModel(l1owner=wallet.address, order_id=order_id, new_price=new_price_str, new_qty=new_qty_str, order_mode=order_mode) # TODO: change to l1_address
        return bytes([DexCommandModify]) + json.dumps(model.to_wire(), separators=(",", ":")).encode("utf-8")


    def create_stop_order_data(self, base_token: str, quote_token: str, stop_price: float, price: float, quantity: float, side: int, order_type: int, order_mode: int) -> bytes:
        # Format decimal values to strings with 3 decimal places precision
        stop_price_str = format_decimal(stop_price)
        price_str = format_decimal(price)
        quantity_str = format_decimal(quantity)
        
        wallet = self.get_wallet()
        model = StopOrderModel(
            l1owner=wallet.address, # TODO: change to l1_address
            base_token=base_token,
            quote_token=quote_token,
            stop_price=stop_price_str,
            price=price_str,
            quantity=quantity_str,
            side=side,
            order_type=order_type,
            order_mode=order_mode,
        )
        payload = model.to_wire()
        return bytes([DexCommandStopOrder]) + json.dumps(payload, separators=(",", ":")).encode("utf-8")


    def generate_alphasec_transaction(self, timestamp_ms: int, data: bytes, wallet: Account = None) -> str:
        if wallet is None:
            wallet = self.get_wallet()

        tx = {
            "to": ALPHASEC_ORDER_CONTRACT_ADDR,
            "gas": 1000000,
            "maxFeePerGas": 0,
            "maxPriorityFeePerGas": 0,
            "value": 0,
            "nonce": timestamp_ms if timestamp_ms is not None else 0,
            "data": data,
            "chainId": 412346,
        }

        signed = wallet.sign_transaction(tx)
        raw = signed.raw_transaction
        return "0x" + raw.hex()

    def generate_deposit_transaction(self, l1_provider: Web3, token_id, value: int, token_l1_address: str = None) -> str:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, deposit is only available for l1 wallet")

        if token_id == ALPHASEC_NATIVE_TOKEN_ID:
            inbox_addr = MAINNET_INBOX_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_INBOX_CONTRACT_ADDR
            contract = l1_provider.eth.contract(address=inbox_addr, abi=NATIVE_L1_ABI)
            tx = contract.functions.depositEth().build_transaction({
                "value": value,
                "from": self.l1_address,
                "gas": 1000000,
                "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
            })
            signed = self.l1_wallet.sign_transaction(tx)
            return "0x" + signed.raw_transaction.hex()
        else:
            if token_l1_address is None or not is_address(token_l1_address):
                raise ValueError("token_l1_address is invalid")

            erc20_gateway_addr = MAINNET_ERC20_GATEWAY_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_ERC20_GATEWAY_CONTRACT_ADDR
            erc20_contract = l1_provider.eth.contract(address=token_l1_address, abi=ERC20_ABI)
            allowance = erc20_contract.functions.allowance(self.l1_address, erc20_gateway_addr).call()
            if allowance < value:
                tx = erc20_contract.functions.approve(erc20_gateway_addr, value).build_transaction({
                    "from": self.l1_address,
                    "gas": 1000000,
                    "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
                })
                signed = self.l1_wallet.sign_transaction(tx)
                try:
                    tx_hash = l1_provider.eth.send_raw_transaction(signed.raw_transaction)
                    l1_provider.eth.wait_for_transaction_receipt(tx_hash)
                except Exception as e:
                    raise ValueError("allowance approve failed")
            
            L2_GAS_LIMIT = 1000000
            L2_GAS_PRICE = 1000000
            MAX_SUBMISSION_COST = int(0.01 * 10**18)
            VALUE = int(0.02 * 10**18)
            data = l1_provider.codec.encode(['uint256', 'bytes'], [MAX_SUBMISSION_COST, '0x'])
            erc20_router_addr = MAINNET_ERC20_ROUTER_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_ERC20_ROUTER_CONTRACT_ADDR
            contract = l1_provider.eth.contract(address=erc20_router_addr, abi=ERC20_ROUTER_ABI)
            tx = contract.functions.outboundTransfer(token_l1_address, self.l1_address, value, L2_GAS_LIMIT, L2_GAS_PRICE, data).build_transaction({
                "from": self.l1_address,
                "value": VALUE,
                "gas": 1000000,
                "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
            })
            signed = self.l1_wallet.sign_transaction(tx)
            return "0x" + signed.raw_transaction.hex()

    def generate_withdraw_transaction(self, l2_provider: Web3, token_id: str, value: int, token_l1_address: str = None) -> str:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, withdraw is only available for l1 wallet")

        endpoint_url = ALPHASEC_MAINNET_URL if self.network == "mainnet" else ALPHASEC_KAIROS_URL
        if l2_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw is only available for l2 provider")

        try:
            balance = l2_provider.provider.make_request("debug_getTokenBalances", [self.l1_address, "latest"]).get("result")
            print(balance)
            if int(balance['available'][token_id]) < value:
                raise ValueError("balance is not enough")
        except Exception as e:
            raise ValueError("l2 provider is not ready")

        if token_id == ALPHASEC_NATIVE_TOKEN_ID:
            system_contract_addr = ALPHASEC_SYSTEM_CONTRACT_ADDR
            contract = l2_provider.eth.contract(address=system_contract_addr, abi=L2_SYSTEM_ABI)
            tx = contract.functions.withdrawEth(self.l1_address).build_transaction({
                "from": self.l1_address,
                "value": value,
                "gas": 1000000,
                "nonce": int(time.time() * 1000),
            })
        else:
            erc20_router_addr = ALPHASEC_GATEWAY_ROUTER_CONTRACT_ADDR
            contract = l2_provider.eth.contract(address=erc20_router_addr, abi=L2_ERC20_ROUTER_ABI)
            tx = contract.functions.outboundTransfer(token_l1_address, self.l1_address, value, '0x').build_transaction({
                "from": self.l1_address,
                "gas": 1000000,
                "nonce": int(time.time() * 1000),
            })

        signed = self.l1_wallet.sign_transaction(tx)
        return "0x" + signed.raw_transaction.hex()

    ## only for testing
    def get_withdraw_info_on_l2(self, l2_provider: Web3, block_num_on_l2: int) -> tuple[int, bytes, list[str], dict[str, any]]:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, withdraw is only available for l1 wallet")

        endpoint_url = ALPHASEC_MAINNET_URL if self.network == "mainnet" else ALPHASEC_KAIROS_URL
        if l2_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw is only available for l2 provider")

        l2_system_contract = l2_provider.eth.contract(address=ALPHASEC_SYSTEM_CONTRACT_ADDR, abi=L2_SYSTEM_ABI)
        logs = l2_system_contract.events.L2ToL1Tx().get_logs(from_block=block_num_on_l2, to_block=block_num_on_l2)
        l2_to_l1_event = None
        for log in logs:
            if log.args.destination == MAINNET_ERC20_GATEWAY_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_ERC20_GATEWAY_CONTRACT_ADDR or \
                log.args.destination == self.l1_address:
                l2_to_l1_event = log.args
                break

        if l2_to_l1_event is None:
            raise ValueError("l2 to l1 event for withdraw is not found")

        system_contract = l2_provider.eth.contract(address=ALPHASEC_SYSTEM_CONTRACT_ADDR, abi=L2_SYSTEM_ABI)
        merkle_tree_state = system_contract.functions.sendMerkleTreeState().call(block_identifier=block_num_on_l2)

        zk_interface_contract = l2_provider.eth.contract(address=ALPHASEC_ZK_INTERFACE_CONTRACT_ADDR, abi=ZK_INTERFACE_ABI)
        proof_data = zk_interface_contract.functions.constructOutboxProof(merkle_tree_state[0], l2_to_l1_event.position).call()

        return proof_data[0], proof_data[1], proof_data[2], l2_to_l1_event

    ## only for testing
    def is_withdraw_proof_registered(self, l1_provider: Web3, root: bytes) -> bool:
        endpoint_url = MAINNET_URL if self.network == "mainnet" else KAIROS_URL
        if l1_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw proof registration should be executed on the l1 provider")

        outbox_addr = MAINNET_OUTBOX_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_OUTBOX_CONTRACT_ADDR
        contract = l1_provider.eth.contract(address=outbox_addr, abi=L1_OUTBOX_ABI)
        roots = contract.functions.roots(root).call()
        print(roots)
        return roots.hex() != "0000000000000000000000000000000000000000000000000000000000000000"

    ## only for testing
    def generate_withdraw_transaction_on_l1(self, l1_provider: Web3, proof: list[str], l2_to_l1_event: dict[str, any]) -> str:
        if self.l1_wallet is None:
            raise ValueError("l1_wallet is not set, withdraw is only available for l1 wallet")

        endpoint_url = MAINNET_URL if self.network == "mainnet" else KAIROS_URL
        if l1_provider.provider.endpoint_uri != endpoint_url:
            raise ValueError("withdraw on l1 should be executed on the l1 provider")

        # check the proof is spent
        outbox_addr = MAINNET_OUTBOX_CONTRACT_ADDR if self.network == "mainnet" else KAIROS_OUTBOX_CONTRACT_ADDR
        contract = l1_provider.eth.contract(address=outbox_addr, abi=L1_OUTBOX_ABI)
        is_spent = contract.functions.isSpent(l2_to_l1_event.position).call()
        if is_spent:
            raise ValueError("withdraw proof is already spent")

        tx = contract.functions.executeTransaction(proof, l2_to_l1_event.position, l2_to_l1_event.caller, l2_to_l1_event.destination, l2_to_l1_event.arbBlockNum, l2_to_l1_event.ethBlockNum, l2_to_l1_event.timestamp, l2_to_l1_event.callvalue, l2_to_l1_event.data).build_transaction({
            "from": self.l1_address,
            "nonce": l1_provider.eth.get_transaction_count(self.l1_address),
            "gas": 1000000,
        })
        signed = self.l1_wallet.sign_transaction(tx)
        return "0x" + signed.raw_transaction.hex()