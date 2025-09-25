"""
Basic example showing how to transfer native value (KAIA).
This example requires a signer (private key).
"""
import os

from alphasec import Agent, AlphasecSigner, load_config

def main():
    # Load config using alphasec's load_config function
    config = load_config(os.path.dirname(__file__) + "/../config")
    
    # Create signer with config
    signer = AlphasecSigner(config)
    
    # Initialize agent with signer for trading operations
    agent = Agent(config['api_url'], signer=signer)
    
    # Use recipient address from tests
    recipient = "0x4D3cF56fB96c287387606862df55005d52FEa89b"
    
    # Transfer 1 wei (like in tests)
    value_wei = 1
    
    print(f"=== Transferring {value_wei} wei to {recipient} ===")
    result = agent.value_transfer(recipient, value_wei)
    print(f"Transfer result: {result}")
    
    if result:
        print("Value transfer completed successfully!")
    else:
        print("Value transfer failed")

if __name__ == "__main__":
    main()
