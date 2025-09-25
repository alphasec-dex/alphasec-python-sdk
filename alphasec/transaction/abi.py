
NATIVE_L1_ABI = [{
  "type": "function",
  "name": "depositEth",
  "inputs": [],
  "outputs": [
    {
      "name": "",
      "type": "uint256",
      "internalType": "uint256"
    }
  ],
  "stateMutability": "payable"
}]

L1_OUTBOX_ABI = [
  {
    "inputs": [{ "name": "", "type": "bytes32" }],
    "name": "roots",
    "outputs": [{ "name": "", "type": "bytes32" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [{ "name": "index", "type": "uint256" }],
    "name": "isSpent",
    "outputs": [{ "name": "", "type": "bool" }],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "name": "proof", "type": "bytes32[]" },
      { "name": "position", "type": "uint256" },
      { "name": "caller", "type": "address" },
      { "name": "destination", "type": "address" },
      { "name": "arbBlockNum", "type": "uint256" },
      { "name": "ethBlockNum", "type": "uint256" },
      { "name": "timestamp", "type": "uint256" },
      { "name": "callvalue", "type": "uint256" },
      { "name": "data", "type": "bytes" }
    ],
    "name": "executeTransaction",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
]

L2_SYSTEM_ABI = [{
    "inputs": [
      { "internalType": "address", "name": "destination", "type": "address" }
    ],
    "name": "withdrawEth",
    "outputs": [],
    "stateMutability": "payable",
    "type": "function"
  },
  {
    "inputs": [],
    "name": "sendMerkleTreeState",
    "outputs": [
      { "name": "size", "type": "uint256" },
      { "name": "root", "type": "bytes32" },
      { "name": "partials", "type": "bytes32[]" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "anonymous": False,
    "inputs": [
      { "indexed": False, "internalType": "address",  "name": "caller",     "type": "address" },
      { "indexed": True, "internalType": "address",  "name": "destination", "type": "address" },
      { "indexed": True,  "internalType": "uint256",  "name": "hash",       "type": "uint256" },
      { "indexed": True,  "internalType": "uint256",  "name": "position",   "type": "uint256" },
      { "indexed": False, "internalType": "uint256", "name": "arbBlockNum", "type": "uint256" },
      { "indexed": False, "internalType": "uint256", "name": "ethBlockNum", "type": "uint256" },
      { "indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256" },
      { "indexed": False, "internalType": "uint256", "name": "callvalue", "type": "uint256" },
      { "indexed": False, "internalType": "bytes", "name": "data", "type": "bytes" }
    ],
    "name": "L2ToL1Tx",
    "type": "event"
  }
]

ZK_INTERFACE_ABI = [{
  "inputs": [
    { "name": "size", "type": "uint64" },
    { "name": "leaf", "type": "uint64" }
  ],
  "name": "constructOutboxProof",
  "outputs": [
    { "name": "send", "type": "bytes32" },
    { "name": "root", "type": "bytes32" },
    { "name": "proof", "type": "bytes32[]" }
  ],
  "stateMutability": "view",
  "type": "function"
}]

ERC20_ABI = [
    {
      "inputs": [],
      "stateMutability": "nonpayable",
      "type": "constructor"
    },
    {
      "anonymous": False,
      "inputs": [
        {
          "indexed": True,
          "internalType": "address",
          "name": "owner",
          "type": "address"
        },
        {
          "indexed": True,
          "internalType": "address",
          "name": "spender",
          "type": "address"
        },
        {
          "indexed": False,
          "internalType": "uint256",
          "name": "value",
          "type": "uint256"
        }
      ],
      "name": "Approval",
      "type": "event"
    },
    {
      "anonymous": False,
      "inputs": [
        {
          "indexed": True,
          "internalType": "address",
          "name": "from",
          "type": "address"
        },
        {
          "indexed": True,
          "internalType": "address",
          "name": "to",
          "type": "address"
        },
        {
          "indexed": False,
          "internalType": "uint256",
          "name": "value",
          "type": "uint256"
        }
      ],
      "name": "Transfer",
      "type": "event"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "owner",
          "type": "address"
        },
        {
          "internalType": "address",
          "name": "spender",
          "type": "address"
        }
      ],
      "name": "allowance",
      "outputs": [
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "spender",
          "type": "address"
        },
        {
          "internalType": "uint256",
          "name": "amount",
          "type": "uint256"
        }
      ],
      "name": "approve",
      "outputs": [
        {
          "internalType": "bool",
          "name": "",
          "type": "bool"
        }
      ],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "account",
          "type": "address"
        }
      ],
      "name": "balanceOf",
      "outputs": [
        {
          "internalType": "uint256",
          "name": "",
          "type": "uint256"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "decimals",
      "outputs": [
        {
          "internalType": "uint8",
          "name": "",
          "type": "uint8"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "spender",
          "type": "address"
        },
        {
          "internalType": "uint256",
          "name": "addedValue",
          "type": "uint256"
        }
      ],
      "name": "increaseAllowance",
      "outputs": [
        {
          "internalType": "bool",
          "name": "",
          "type": "bool"
        }
      ],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "name",
      "outputs": [
        {
          "internalType": "string",
          "name": "",
          "type": "string"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "symbol",
      "outputs": [
        {
          "internalType": "string",
          "name": "",
          "type": "string"
        }
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {
      "inputs": [
        {
          "internalType": "address",
          "name": "to",
          "type": "address"
        },
        {
          "internalType": "uint256",
          "name": "amount",
          "type": "uint256"
        }
      ],
      "name": "transfer",
      "outputs": [
        {
          "internalType": "bool",
          "name": "",
          "type": "bool"
        }
      ],
      "stateMutability": "nonpayable",
      "type": "function"
    },
  ]

ERC20_ROUTER_ABI = [
    {
      "inputs": [
      { "internalType": "address", "name": "_l1Token", "type": "address" },
      { "internalType": "address", "name": "_to", "type": "address" },
      { "internalType": "uint256", "name": "_amount", "type": "uint256" },
      { "internalType": "uint256", "name": "_maxGas", "type": "uint256" },
      { "internalType": "uint256", "name": "_gasPriceBid", "type": "uint256" },
      { "internalType": "bytes", "name": "_data", "type": "bytes" }
      ],
      "name": "outboundTransfer",
      "outputs": [{ "internalType": "bytes", "name": "res", "type": "bytes" }],
      "stateMutability": "payable",
      "type": "function"
    },
    {
      "inputs": [
        { "internalType": "address", "name": "_l1Token", "type": "address" },
        { "internalType": "address", "name": "_refundTo", "type": "address" },
        { "internalType": "address", "name": "_to", "type": "address" },
        { "internalType": "uint256", "name": "_amount", "type": "uint256" },
        { "internalType": "uint256", "name": "_maxGas", "type": "uint256" },
        { "internalType": "uint256", "name": "_gasPriceBid", "type": "uint256" },
        { "internalType": "bytes", "name": "_data", "type": "bytes" }
      ],
      "name": "outboundTransferCustomRefund",
      "outputs": [{ "internalType": "bytes", "name": "res", "type": "bytes" }],
      "stateMutability": "payable",
      "type": "function"
    }
  ]

L2_ERC20_ROUTER_ABI = [
   {
      "inputs": [
        { "internalType": "address", "name": "_l1Token", "type": "address" },
        { "internalType": "address", "name": "_to", "type": "address" },
        { "internalType": "uint256", "name": "_amount", "type": "uint256" },
        { "internalType": "bytes", "name": "_data", "type": "bytes" }
      ],
      "name": "outboundTransfer",
      "outputs": [{ "internalType": "bytes", "name": "res", "type": "bytes" }],
      "stateMutability": "payable",
      "type": "function"
    }, 
]