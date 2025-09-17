"""
Basic example showing how to use the bridge (deposit/withdraw).
This example requires a signer (private key).
WARNING: These operations involve real blockchain transactions!
"""
import os
import sys

# Add parent directory to path to import alphasec
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from alphasec import Agent, load_config, AlphasecSigner

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(os.path.dirname(__file__)))
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    # Example values from tests
    print("=== Bridge Operations Examples ===")
    print("WARNING: These operations involve real blockchain transactions!")
    print()
    
    # Native token deposit example (like in tests)
    print("1. Native Token Deposit (KAIA):")
    print("   agent.deposit('KAIA', int(1e18))  # 1 KAIA")
    print()
    
    # ERC20 token deposit example (like in tests) 
    print("2. ERC20 Token Deposit (USDT):")
    print("   agent.deposit('USDT', int(1e18), '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')")
    print()
    
    # Native token withdraw example (like in tests)
    print("3. Native Token Withdraw (KAIA):")
    print("   agent.withdraw('KAIA', int(1e18))")
    print()
    
    # ERC20 token withdraw example (like in tests)
    print("4. ERC20 Token Withdraw (USDT):")
    print("   agent.withdraw('USDT', int(1e18), '0xac76d4a9985abA068dbae07bf5cC10be06A19f12')")
    print()
    
    print("SAFETY NOTE: All bridge operations are commented out.")
    print("Uncomment and modify the examples above to perform actual transactions.")
    print("Always test on testnet first!")
    
    # Example of how to actually call (commented out for safety):
    # result = agent.deposit("USDT", int(1e18), "0xac76d4a9985abA068dbae07bf5cC10be06A19f12")
    # print(f"Deposit result: {result}")
    
    # result = agent.withdraw("USDT", int(1e18), "0xac76d4a9985abA068dbae07bf5cC10be06A19f12")  
    # print(f"Withdraw result: {result}")

if __name__ == "__main__":
    main()
