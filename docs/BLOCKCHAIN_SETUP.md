# Blockchain RPC Setup Guide

Complete guide for configuring blockchain RPC endpoints, wallet generation, and secure key management for the Law Discord Bot's cryptocurrency escrow system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Variable Configuration](#environment-variable-configuration)
3. [Wallet Generation Workflow](#wallet-generation-workflow)
4. [Security Best Practices](#security-best-practices)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Commands Reference](#commands-reference)

---

## Prerequisites

### RPC Endpoint Requirements

The blockchain system requires RPC (Remote Procedure Call) endpoints for four supported networks. These endpoints allow the bot to query blockchain state, monitor transactions, and validate payments.

#### Supported Networks

| Network | Symbol | Type | Use Case |
|---------|--------|------|----------|
| **Ethereum** | ETH | EVM | Smart contracts, token transfers, DeFi |
| **Bitcoin** | BTC | UTXO | Native cryptocurrency, settlement layer |
| **Solana** | SOL | Solana | High-speed transactions, NFTs |
| **Litecoin** | LTC | UTXO | Fast payments, alternative to Bitcoin |

### RPC Endpoint Options

#### 1. **Ethereum RPC Endpoints**

**Public (Free, Rate-Limited):**
```
https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
https://mainnet.infura.io/v3/YOUR_INFURA_KEY
https://eth.llamarpc.com
```

**Recommended Providers:**
- **Alchemy** (https://www.alchemy.com/) — Free tier: 300M compute units/month
- **Infura** (https://infura.io/) — Free tier: 100k requests/day
- **QuickNode** (https://www.quicknode.com/) — Free tier: 50k requests/day
- **Ankr** (https://www.ankr.com/) — Free tier: unlimited requests

**Production Setup:**
```
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY
```

#### 2. **Bitcoin RPC Endpoints**

**Public (Free):**
```
https://api.blockcypher.com/v1/btc/main
https://blockstream.info/api
```

**Self-Hosted (Recommended for Production):**
- Run a Bitcoin Core node (requires 500GB+ disk space)
- Configure RPC authentication in `bitcoin.conf`

**Recommended Providers:**
- **BlockCypher** (https://www.blockcypher.com/) — Free tier: 200 requests/hour
- **Blockchair** (https://blockchair.com/) — Free tier: 100 requests/minute
- **Blockchain.com** (https://www.blockchain.com/api) — Free tier: 1 request/second

**Production Setup:**
```
BTC_RPC_URL=https://api.blockcypher.com/v1/btc/main
```

#### 3. **Solana RPC Endpoints**

**Public (Free):**
```
https://api.mainnet-beta.solana.com
https://solana-api.projectserum.com
```

**Recommended Providers:**
- **Solana Foundation** (https://api.mainnet-beta.solana.com) — Official, rate-limited
- **QuickNode** (https://www.quicknode.com/) — Free tier: 50k requests/day
- **Helius** (https://www.helius.dev/) — Free tier: 1M requests/month

**Production Setup:**
```
SOL_RPC_URL=https://api.mainnet-beta.solana.com
```

#### 4. **Litecoin RPC Endpoints**

**Public (Free):**
```
https://api.blockcypher.com/v1/ltc/main
https://blockchair.com/litecoin/api
```

**Self-Hosted (Recommended for Production):**
- Run a Litecoin Core node (requires 100GB+ disk space)

**Recommended Providers:**
- **BlockCypher** (https://www.blockcypher.com/) — Free tier: 200 requests/hour
- **Blockchair** (https://blockchair.com/) — Free tier: 100 requests/minute

**Production Setup:**
```
LTC_RPC_URL=https://api.blockcypher.com/v1/ltc/main
```

### System Requirements

- **Python 3.8+** — Required for bot runtime
- **aiohttp** — Async HTTP client for RPC requests
- **cryptography** — For wallet key encryption
- **web3.py** — Ethereum wallet generation
- **bitcoinlib** — Bitcoin/Litecoin wallet generation
- **solders** — Solana wallet generation
- **python-dotenv** — Environment variable management

**Install dependencies:**
```bash
pip install -r requirements.txt
```

---

## Environment Variable Configuration

### Setting Up .env File

Create a `.env` file in your project root with the following blockchain configuration:

```bash
# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKCHAIN RPC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# Ethereum RPC endpoint (EVM-compatible)
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY

# Bitcoin RPC endpoint (UTXO-based)
BTC_RPC_URL=https://api.blockcypher.com/v1/btc/main

# Solana RPC endpoint (Solana-specific)
SOL_RPC_URL=https://api.mainnet-beta.solana.com

# Litecoin RPC endpoint (UTXO-based)
LTC_RPC_URL=https://api.blockcypher.com/v1/ltc/main

# ═══════════════════════════════════════════════════════════════════════════════
# WALLET ENCRYPTION & SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

# Fernet encryption key for private key storage (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
WALLET_ENCRYPTION_KEY=your_fernet_key_here

# Enable wallet encryption (recommended: True)
WALLET_ENCRYPTION_ENABLED=True

# ═══════════════════════════════════════════════════════════════════════════════
# RPC CLIENT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Request timeout in seconds (default: 10)
RPC_TIMEOUT=10

# Maximum retry attempts for failed requests (default: 3)
RPC_MAX_RETRIES=3

# Exponential backoff multiplier (default: 2.0)
RPC_BACKOFF_FACTOR=2.0

# Health check timeout in seconds (default: 2)
RPC_HEALTH_CHECK_TIMEOUT=2
```

### Generating Encryption Key

Generate a secure Fernet encryption key for wallet private key storage:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Output example:**
```
gAAAAABl_example_key_string_here_1234567890abcdefghijklmnop
```

Copy this key to your `.env` file as `WALLET_ENCRYPTION_KEY`.

### Validating Configuration

Verify your environment variables are loaded correctly:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Check RPC endpoints
print(f"ETH RPC: {os.getenv('ETH_RPC_URL')}")
print(f"BTC RPC: {os.getenv('BTC_RPC_URL')}")
print(f"SOL RPC: {os.getenv('SOL_RPC_URL')}")
print(f"LTC RPC: {os.getenv('LTC_RPC_URL')}")

# Check encryption key
print(f"Encryption Key Set: {bool(os.getenv('WALLET_ENCRYPTION_KEY'))}")
```

### config.py Integration

The `config.py` file contains blockchain network definitions that reference your environment variables:

```python
BLOCKCHAIN_NETWORKS = [
    {
        "name": "Ethereum",
        "symbol": "ETH",
        "chain_id": 1,
        "rpc_endpoint": "https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY",
        "enabled": True,
        "confirmations_required": 12,
    },
    {
        "name": "Bitcoin",
        "symbol": "BTC",
        "chain_id": None,
        "rpc_endpoint": "https://api.blockcypher.com/v1/btc/main",
        "enabled": True,
        "confirmations_required": 3,
    },
    {
        "name": "Solana",
        "symbol": "SOL",
        "chain_id": None,
        "rpc_endpoint": "https://api.mainnet-beta.solana.com",
        "enabled": True,
        "confirmations_required": 32,
    },
    {
        "name": "Litecoin",
        "symbol": "LTC",
        "chain_id": None,
        "rpc_endpoint": "https://api.blockcypher.com/v1/ltc/main",
        "enabled": True,
        "confirmations_required": 6,
    },
]

WALLET_CONFIG = {
    "encryption_algorithm": "Fernet",
    "key_derivation": "PBKDF2",
    "key_rotation_days": 90,
    "backup_enabled": True,
    "backup_location": "./backups/wallets/",
}
```

---

## Wallet Generation Workflow

### Overview

The wallet generation system creates deterministic, encrypted wallets for each blockchain network. Wallets are associated with trade IDs and stored securely in `bot_data.json`.

### Wallet Generation Process

#### Step 1: Initialize WalletManager

```python
from blockchain.wallet_manager import WalletManager

# Initialize with default encryption key from environment
manager = WalletManager(data_file='bot_data.json')
```

#### Step 2: Create Wallets for a Trade

Create wallets for all supported networks:

```python
# Create wallets for a specific trade
trade_id = "TRADE_12345"

# Single network
eth_wallet = manager.create_wallet('ETH', trade_id)
print(f"ETH Address: {eth_wallet['address']}")

# Or create all networks at once
from blockchain.wallet_manager import create_wallets_for_trade

wallets = create_wallets_for_trade(
    trade_id=trade_id,
    networks=['ETH', 'BTC', 'SOL', 'LTC']
)

for network, wallet_info in wallets.items():
    print(f"{network}: {wallet_info['address']}")
```

#### Step 3: Retrieve Wallet Information

**Get wallet address:**
```python
address = manager.get_wallet_address(trade_id='TRADE_12345', network='ETH')
print(f"Ethereum Address: {address}")
```

**Get all wallets for a trade:**
```python
wallets = manager.list_wallets_by_trade_id(trade_id='TRADE_12345')
for network, wallet_data in wallets.items():
    print(f"{network}: {wallet_data['address']}")
```

**Get wallet metadata (without private key):**
```python
metadata = manager.get_wallet_metadata(trade_id='TRADE_12345', network='ETH')
print(metadata)
# Output: {
#     'network': 'ETH',
#     'address': '0x...',
#     'created_at': '2024-01-15T10:30:00',
#     'trade_id': 'TRADE_12345',
#     'public_key': '0x...'
# }
```

### Wallet Data Structure

Each wallet is stored with the following structure:

```json
{
  "network": "ETH",
  "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f42bE",
  "private_key_encrypted": "gAAAAABl_encrypted_key_...",
  "trade_id": "TRADE_12345",
  "created_at": "2024-01-15T10:30:00.123456",
  "public_key": "0x742d35Cc6634C0532925a3b844Bc9e7595f42bE"
}
```

### Network-Specific Details

#### Ethereum (ETH)

- **Type:** EVM (Ethereum Virtual Machine)
- **Address Format:** 0x-prefixed hex string (42 characters)
- **Key Format:** Hex-encoded private key
- **Generation:** Web3.py account creation

```python
wallet = manager.generate_eth_wallet(trade_id='TRADE_12345')
# Address: 0x742d35Cc6634C0532925a3b844Bc9e7595f42bE
```

#### Bitcoin (BTC)

- **Type:** UTXO (Unspent Transaction Output)
- **Address Format:** P2PKH (1...), P2SH (3...), or Bech32 (bc1...)
- **Key Format:** WIF (Wallet Import Format)
- **Generation:** bitcoinlib key generation

```python
wallet = manager.generate_btc_wallet(trade_id='TRADE_12345')
# Address: 1A1z7agoat5SFpjCGAsicQrdchBSSA83i
```

#### Solana (SOL)

- **Type:** Account-based
- **Address Format:** Base58-encoded public key (44 characters)
- **Key Format:** Base58-encoded keypair
- **Generation:** solders keypair generation

```python
wallet = manager.generate_sol_wallet(trade_id='TRADE_12345')
# Address: 9B5X4b23xwYvCKSLF93PFxZzYGMoEt7xNFcKE7K5Qwj
```

#### Litecoin (LTC)

- **Type:** UTXO (similar to Bitcoin)
- **Address Format:** L-prefixed (P2PKH) or M-prefixed (P2SH)
- **Key Format:** WIF (Wallet Import Format)
- **Generation:** bitcoinlib key generation with network='litecoin'

```python
wallet = manager.generate_ltc_wallet(trade_id='TRADE_12345')
# Address: LdRQWka4G5Pgw3k2ZyT1Lmp1gEJJqmSeNq
```

### Async RPC Client Usage

The `RPCClient` class provides async methods for blockchain queries:

```python
from blockchain.rpc_client import RPCClient, NetworkType
import asyncio

async def check_balance():
    async with RPCClient() as client:
        # Ethereum balance
        balance = await client.eth_get_balance('0x742d35Cc6634C0532925a3b844Bc9e7595f42bE')
        print(f"Balance (wei): {balance}")
        
        # Solana balance
        sol_balance = await client.sol_get_balance('9B5X4b23xwYvCKSLF93PFxZzYGMoEt7xNFcKE7K5Qwj')
        print(f"Balance (lamports): {sol_balance}")

asyncio.run(check_balance())
```

---

## Security Best Practices

### 1. Private Key Encryption

**Always encrypt private keys at rest:**

```python
from cryptography.fernet import Fernet

# Generate encryption key (do this once, store securely)
encryption_key = Fernet.generate_key()

# Initialize cipher
cipher = Fernet(encryption_key)

# Encrypt private key
private_key = "0x1234567890abcdef..."
encrypted = cipher.encrypt(private_key.encode())

# Decrypt when needed (only for signing)
decrypted = cipher.decrypt(encrypted).decode()
```

**The WalletManager handles this automatically:**

```python
manager = WalletManager()

# Private keys are encrypted on creation
wallet = manager.create_wallet('ETH', 'TRADE_12345')

# Retrieve and decrypt only when needed
private_key = manager.get_private_key('TRADE_12345', 'ETH')
# Use for signing transaction
# Never log or expose this key
```

### 2. Environment Variable Security

**DO:**
- ✅ Store `WALLET_ENCRYPTION_KEY` in `.env` file (not in version control)
- ✅ Use strong, randomly generated encryption keys
- ✅ Rotate encryption keys every 90 days (set in `config.py`)
- ✅ Restrict file permissions: `chmod 600 .env`
- ✅ Use different keys for development and production

**DON'T:**
- ❌ Commit `.env` file to Git
- ❌ Log encryption keys or private keys
- ❌ Share encryption keys via email or chat
- ❌ Use weak or predictable keys
- ❌ Store keys in code comments

### 3. Key Storage & Backup

**Secure Storage:**

```python
# bot_data.json structure
{
  "wallets": {
    "ETH_TRADE_12345": {
      "network": "ETH",
      "address": "0x...",
      "private_key_encrypted": "gAAAAABl_...",  # Encrypted with Fernet
      "trade_id": "TRADE_12345",
      "created_at": "2024-01-15T10:30:00",
      "public_key": "0x..."
    }
  },
  "metadata": {
    "created_at": "2024-01-15T10:00:00",
    "version": "1.0"
  }
}
```

**Backup Strategy:**

```python
# Enable backups in config.py
WALLET_CONFIG = {
    "backup_enabled": True,
    "backup_location": "./backups/wallets/",
    "key_rotation_days": 90,
}

# Backup bot_data.json regularly
import shutil
from datetime import datetime

def backup_wallets():
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = f"./backups/wallets/bot_data_{timestamp}.json"
    shutil.copy('bot_data.json', backup_file)
    print(f"Backup created: {backup_file}")
```

### 4. Access Control

**Restrict private key access:**

```python
# Only retrieve private keys when signing transactions
def sign_transaction(trade_id, network, transaction_data):
    manager = WalletManager()
    
    # Get private key only when needed
    private_key = manager.get_private_key(trade_id, network)
    
    if not private_key:
        raise ValueError("Failed to retrieve private key")
    
    # Sign transaction
    signed_tx = sign_with_key(private_key, transaction_data)
    
    # Private key is no longer in memory after this function
    return signed_tx
```

**Never expose private keys:**

```python
# ❌ WRONG - Exposes private key
def get_wallet_info(trade_id):
    wallet = manager.get_wallet_by_trade_id(trade_id)
    return wallet  # Contains encrypted private key

# ✅ CORRECT - Returns only public information
def get_wallet_info(trade_id):
    return manager.get_wallet_metadata(trade_id)
```

### 5. Network Security

**Use HTTPS for RPC endpoints:**

```python
# ✅ CORRECT - HTTPS endpoints
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
BTC_RPC_URL=https://api.blockcypher.com/v1/btc/main

# ❌ WRONG - HTTP endpoints (unencrypted)
ETH_RPC_URL=http://localhost:8545
```

**Verify SSL certificates:**

```python
# config.py
WEBHOOK_CONFIG = {
    "verify_ssl": True,  # Always verify SSL certificates
    "timeout_seconds": 30,
}
```

### 6. Rate Limiting & Monitoring

**Configure rate limits:**

```python
# config.py
WEBHOOK_CONFIG = {
    "rate_limit_per_minute": 100,
    "timeout_seconds": 30,
}

# RPC client retry configuration
RPC_MAX_RETRIES=3
RPC_BACKOFF_FACTOR=2.0
RPC_TIMEOUT=10
```

**Monitor for suspicious activity:**

```python
# config.py
MONITORING_CONFIG = {
    "log_level": "INFO",
    "log_file": "./logs/blockchain_monitor.log",
    "alert_on_error": True,
    "alert_discord_webhook": "https://discord.com/api/webhooks/...",
}
```

### 7. Wallet Deletion & Cleanup

**Securely delete wallets when trade completes:**

```python
manager = WalletManager()

# Delete wallet after trade completion
success = manager.delete_wallet(trade_id='TRADE_12345', network='ETH')

if success:
    print("Wallet deleted securely")
else:
    print("Wallet not found")

# Delete all wallets for a trade
manager.delete_wallet(trade_id='TRADE_12345')  # Deletes all networks
```

---

## Troubleshooting Guide

### RPC Connection Issues

#### Problem: "RPC URL not configured"

**Cause:** Environment variable not set or empty

**Solution:**
```bash
# Check .env file
cat .env | grep RPC_URL

# Verify environment variables are loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('ETH_RPC_URL'))"
```

#### Problem: "Connection error: Connection refused"

**Cause:** RPC endpoint is unreachable or down

**Solution:**
```bash
# Test RPC endpoint connectivity
curl -X POST https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# Expected response:
# {"jsonrpc":"2.0","result":"0x1","id":1}
```

#### Problem: "RPC request timed out after 10s"

**Cause:** RPC endpoint is slow or network latency is high

**Solution:**
```python
# Increase timeout in .env
RPC_TIMEOUT=30  # Increase from default 10

# Or in code
from blockchain.rpc_client import RPCClient

client = RPCClient(timeout=30.0)
```

#### Problem: "Rate limit exceeded"

**Cause:** Too many requests to RPC endpoint

**Solution:**
```python
# Increase backoff factor in .env
RPC_BACKOFF_FACTOR=3.0  # Increase from default 2.0

# Or use a paid RPC provider with higher limits
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY  # 300M units/month
```

### Wallet Generation Issues

#### Problem: "Failed to decrypt private key"

**Cause:** Encryption key mismatch or corrupted data

**Solution:**
```python
# Verify encryption key is set
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv('WALLET_ENCRYPTION_KEY')

if not key:
    print("ERROR: WALLET_ENCRYPTION_KEY not set in .env")
else:
    print(f"Encryption key length: {len(key)} characters")

# Regenerate encryption key if needed
from cryptography.fernet import Fernet
new_key = Fernet.generate_key().decode()
print(f"New key: {new_key}")
# Update .env with new key
```

#### Problem: "Unsupported network: XYZ"

**Cause:** Network code is invalid

**Solution:**
```python
# Use supported networks only
SUPPORTED_NETWORKS = ['ETH', 'BTC', 'SOL', 'LTC']

# Correct usage
wallet = manager.create_wallet('ETH', 'TRADE_12345')  # ✅ Valid

# Incorrect usage
wallet = manager.create_wallet('DOGE', 'TRADE_12345')  # ❌ Invalid
```

#### Problem: "bot_data.json not found"

**Cause:** Data file doesn't exist or path is incorrect

**Solution:**
```python
# WalletManager creates bot_data.json automatically
from blockchain.wallet_manager import WalletManager

manager = WalletManager(data_file='bot_data.json')
# File is created if it doesn't exist

# Verify file was created
import os
if os.path.exists('bot_data.json'):
    print("✅ bot_data.json exists")
else:
    print("❌ bot_data.json not found")
```

### Health Check Issues

#### Problem: "Health check failed for ETH"

**Cause:** RPC endpoint is down or unreachable

**Solution:**
```python
# Use the +rpc-health command to check all endpoints
# In Discord: +rpc-health

# Or check programmatically
import asyncio
from blockchain.rpc_client import RPCClient, NetworkType

async def check_health():
    async with RPCClient() as client:
        results = await client.health_check_all()
        for network, status in results.items():
            print(f"{network}: {'✅ Healthy' if status else '❌ Down'}")

asyncio.run(check_health())
```

#### Problem: "No RPC endpoints configured"

**Cause:** All RPC URLs are missing from environment

**Solution:**
```bash
# Add all RPC URLs to .env
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
BTC_RPC_URL=https://api.blockcypher.com/v1/btc/main
SOL_RPC_URL=https://api.mainnet-beta.solana.com
LTC_RPC_URL=https://api.blockcypher.com/v1/ltc/main

# Reload environment
python -c "from dotenv import load_dotenv; load_dotenv()"
```

### Transaction Monitoring Issues

#### Problem: "Webhook not firing for transactions"

**Cause:** Confirmation threshold not met or webhook URL invalid

**Solution:**
```python
# Check webhook configuration in config.py
WEBHOOK_CONFIRMATION_THRESHOLD = 3  # Minimum confirmations

# Verify webhook URL is valid
WEBHOOK_CONFIG = {
    "timeout_seconds": 30,
    "verify_ssl": True,
}

# Test webhook endpoint
import requests
webhook_url = "https://your-webhook-endpoint.com/webhook"
response = requests.post(webhook_url, json={"test": True})
print(f"Webhook status: {response.status_code}")
```

#### Problem: "Transaction not detected"

**Cause:** Wallet address not funded or transaction not confirmed

**Solution:**
```python
# Verify wallet address is correct
manager = WalletManager()
address = manager.get_wallet_address('TRADE_12345', 'ETH')
print(f"Wallet address: {address}")

# Check blockchain explorer
# Ethereum: https://etherscan.io/address/{address}
# Bitcoin: https://blockchain.com/btc/address/{address}
# Solana: https://solscan.io/account/{address}
# Litecoin: https://blockchair.com/litecoin/address/{address}

# Verify transaction confirmations
async def check_confirmations():
    async with RPCClient() as client:
        # Check Ethereum transaction
        tx_count = await client.eth_get_transaction_count(address)
        print(f"Transaction count: {tx_count}")

asyncio.run(check_confirmations())
```

### Performance Issues

#### Problem: "Slow RPC responses"

**Cause:** High network latency or RPC provider overload

**Solution:**
```python
# Use a faster RPC provider
# Compare providers: https://www.alchemy.com/ vs https://www.quicknode.com/

# Or increase timeout and retry settings
RPC_TIMEOUT=30
RPC_MAX_RETRIES=5
RPC_BACKOFF_FACTOR=2.0

# Monitor response times
import time
import asyncio
from blockchain.rpc_client import RPCClient

async def benchmark_rpc():
    async with RPCClient() as client:
        start = time.time()
        balance = await client.eth_get_balance('0x0000000000000000000000000000000000000000')
        elapsed = time.time() - start
        print(f"Response time: {elapsed:.2f}s")

asyncio.run(benchmark_rpc())
```

---

## Commands Reference

### +wallet Command

Create and manage wallets for trades.

**Usage:**
```
+wallet create <trade_id> <network>
+wallet get <trade_id> <network>
+wallet list <trade_id>
+wallet delete <trade_id> [network]
```

**Examples:**
```
+wallet create TRADE_12345 ETH
+wallet get TRADE_12345 BTC
+wallet list TRADE_12345
+wallet delete TRADE_12345 SOL
```

### +rpc-health Command

Check health status of all configured RPC endpoints.

**Usage:**
```
+rpc-health
```

**Output:**
```
🔍 RPC Health Check Results:

ethereum: ✅ Healthy (response time: 245ms)
bitcoin: ✅ Healthy (response time: 312ms)
solana: ✅ Healthy (response time: 189ms)
litecoin: ✅ Healthy (response time: 298ms)

Overall Status: ✅ All endpoints operational
```

**Troubleshooting:**
- If any endpoint shows ❌, check the RPC URL in `.env`
- Verify internet connectivity
- Check RPC provider status page
- Try alternative RPC endpoint

### Configuration Commands

**View blockchain configuration:**
```python
# In config.py
BLOCKCHAIN_NETWORKS  # List of configured networks
WALLET_CONFIG        # Wallet encryption settings
WEBHOOK_CONFIG       # Webhook retry and timeout settings
MONITORING_CONFIG    # Logging and monitoring settings
```

---

## Additional Resources

### Documentation
- [Web3.py Documentation](https://web3py.readthedocs.io/)
- [bitcoinlib Documentation](https://bitcoinlib.readthedocs.io/)
- [Solders Documentation](https://github.com/kevinheavey/solders)
- [Cryptography.io](https://cryptography.io/)

### RPC Providers
- [Alchemy](https://www.alchemy.com/)
- [Infura](https://infura.io/)
- [QuickNode](https://www.quicknode.com/)
- [BlockCypher](https://www.blockcypher.com/)

### Blockchain Explorers
- [Etherscan](https://etherscan.io/) — Ethereum
- [Blockchain.com](https://blockchain.com/) — Bitcoin
- [Solscan](https://solscan.io/) — Solana
- [Blockchair](https://blockchair.com/) — Litecoin

### Security Resources
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Fernet (Symmetric Encryption)](https://cryptography.io/en/latest/fernet/)
- [Private Key Management Best Practices](https://www.coinbase.com/learn/crypto-basics/what-is-a-private-key)

---

## Support

For issues or questions:
1. Check the [Troubleshooting Guide](#troubleshooting-guide) above
2. Review RPC provider documentation
3. Check bot logs: `./logs/blockchain_monitor.log`
4. Contact support with error messages and configuration details

**Last Updated:** January 2024
**Version:** 1.0
