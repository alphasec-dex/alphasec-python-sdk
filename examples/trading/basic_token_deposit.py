"""
Basic example showing how to deposit native tokens.
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
    
    print(f"=== Depositing {value} {token_symbol} ===")
    result = agent.deposit(token_symbol, value)
    print(f"Deposit result: {result}")
    
    if result:
        print(token_symbol, "deposit completed successfully!")
    else:
        print(token_symbol, "deposit failed")

if __name__ == "__main__":
    main()
