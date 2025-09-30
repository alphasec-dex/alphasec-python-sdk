"""
Basic example showing how to withdraw native tokens.
This example requires a signer (private key).
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
    
    # Transfer 1 unit of USDT (like in tests)
    token_symbol = "USDT"
    value = 1
    
    print(f"=== Withdrawing {value} {token_symbol} ===")
    result = agent.withdraw(token_symbol, value)
    print(f"Withdraw result: {result}")
    
    if result:
        print(token_symbol, "withdraw completed successfully!")
    else:
        print(token_symbol, "withdraw failed")

if __name__ == "__main__":
    main()
