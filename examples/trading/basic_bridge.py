"""
Basic example showing how to use the bridge (deposit/withdraw).
This example requires a signer (private key).
WARNING: These operations involve real blockchain transactions!
"""
import os

from alphasec import Agent, load_config, AlphasecSigner

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    print("=== Bridge Operations (LIVE) ===")
    print("WARNING: These operations involve real blockchain transactions!")
    print("Make sure your config has a valid private key and correct network.")
    print()

    # 1) Native token deposit (e.g., 1.0 KAIA)
    try:
        print("1. Native Token Deposit (KAIA): amount 1.0 ...")
        deposit_native = agent.deposit('KAIA', 1.0)
        print(f"   Result: {deposit_native}")
    except Exception as e:
        print(f"   Deposit KAIA failed: {e}")
    print()

    # 2) ERC20 token deposit (USDT) using token L1 contract address
    try:
        print("2. ERC20 Token Deposit (USDT): amount 1.0 ...")
        deposit_usdt = agent.deposit('USDT', 1.0, '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')
        print(f"   Result: {deposit_usdt}")
    except Exception as e:
        print(f"   Deposit USDT failed: {e}")
    print()

    # 3) Native token withdraw (KAIA)
    try:
        print("3. Native Token Withdraw (KAIA): amount 1.0 ...")
        withdraw_native = agent.withdraw('KAIA', 1.0)
        print(f"   Result: {withdraw_native}")
    except Exception as e:
        print(f"   Withdraw KAIA failed: {e}")
    print()

    # 4) ERC20 token withdraw (USDT) back to L1 address
    try:
        print("4. ERC20 Token Withdraw (USDT): amount 1.0 ...")
        withdraw_usdt = agent.withdraw('USDT', 1.0, '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')
        print(f"   Result: {withdraw_usdt}")
    except Exception as e:
        print(f"   Withdraw USDT failed: {e}")

if __name__ == "__main__":
    main()
