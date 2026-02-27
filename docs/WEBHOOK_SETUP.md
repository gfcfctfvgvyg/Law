# Webhook Setup & Monitoring Guide

Comprehensive documentation for configuring webhook receivers, event handling, authentication, and monitoring for the cryptocurrency escrow bot's blockchain transaction detection system.

---

## Table of Contents

1. [Overview](#overview)
2. [Webhook Receiver Configuration](#webhook-receiver-configuration)
3. [Event Format Specifications](#event-format-specifications)
4. [HMAC-SHA256 Authentication](#hmac-sha256-authentication)
5. [Retry Mechanism](#retry-mechanism)
6. [Dead Letter Queue (DLQ) Handling](#dead-letter-queue-dlq-handling)
7. [Monitoring Dashboard](#monitoring-dashboard)
8. [Testing & Validation](#testing--validation)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The cryptocurrency escrow bot uses webhook receivers to monitor blockchain transactions in real-time across four networks:

- **Ethereum (ETH)** - EVM-compatible chain
- **Bitcoin (BTC)** - UTXO-based chain
- **Solana (SOL)** - Account-based chain
- **Litecoin (LTC)** - UTXO-based chain (Bitcoin fork)

Webhooks are delivered via BlockCypher API, which monitors wallet addresses and sends HTTP POST requests when transactions occur. All webhooks are authenticated using HMAC-SHA256 signatures to ensure data integrity and origin verification.

### Key Features

- **Real-time Detection**: Immediate notification of incoming/outgoing transactions
- **Secure Authentication**: HMAC-SHA256 signature verification on all payloads
- **Automatic Retry**: Failed deliveries are retried with exponential backoff
- **Dead Letter Queue**: Permanently failed events are stored for manual review
- **Comprehensive Monitoring**: Dashboard tracks delivery success rates, latency, and error patterns
- **Idempotent Processing**: Duplicate events are safely ignored

---

## Webhook Receiver Configuration

### Server Setup

The webhook receiver is implemented in `webhooks/receiver.py` and runs as an async HTTP server listening for incoming BlockCypher events.

#### Environment Variables

Configure the following in your `.env` file:

```bash
# Webhook Server Configuration
WEBHOOK_HOST=0.0.0.0                    # Listen on all interfaces
WEBHOOK_PORT=8000                       # HTTP port for webhook receiver
WEBHOOK_SECRET_KEY=your-secret-key-here # HMAC signing key (32+ chars)
WEBHOOK_TIMEOUT=30                      # Request timeout in seconds
WEBHOOK_MAX_RETRIES=5                   # Maximum retry attempts
WEBHOOK_RETRY_DELAY=5                   # Initial retry delay in seconds

# BlockCypher Configuration
BLOCKCYPHER_API_KEY=your-api-key-here   # BlockCypher API key
BLOCKCYPHER_TOKEN=your-token-here       # BlockCypher token for webhooks

# Monitoring
MONITORING_ENABLED=true                 # Enable webhook monitoring
MONITORING_DB_PATH=./data/monitoring.db # SQLite database for metrics
```

#### Starting the Webhook Server

```bash
# Using Python directly
python -m webhooks.receiver

# Using Gunicorn (production)
gunicorn -w 4 -b 0.0.0.0:8000 webhooks.receiver:app

# Using systemd (recommended for VPS)
sudo systemctl start webhook-receiver
```

#### Firewall Configuration

Ensure your firewall allows inbound connections on the webhook port:

```bash
# UFW (Ubuntu)
sudo ufw allow 8000/tcp

# iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# AWS Security Groups
# Add inbound rule: Protocol=TCP, Port=8000, Source=BlockCypher IPs
```

#### Registering Webhooks with BlockCypher

Once your server is running and accessible, register webhook endpoints for each network:

```bash
# Ethereum
curl -X POST https://api.blockcypher.com/v1/eth/main/hooks \
  -H "Content-Type: application/json" \
  -d '{
    "event": "tx-confirmation",
    "address": "0x1234567890abcdef...",
    "url": "https://your-domain.com/webhooks/eth",
    "token": "'$BLOCKCYPHER_TOKEN'"
  }'

# Bitcoin
curl -X POST https://api.blockcypher.com/v1/btc/main/hooks \
  -H "Content-Type: application/json" \
  -d '{
    "event": "tx-confirmation",
    "address": "1A1z7agoat...",
    "url": "https://your-domain.com/webhooks/btc",
    "token": "'$BLOCKCYPHER_TOKEN'"
  }'

# Solana
curl -X POST https://api.blockcypher.com/v1/sol/main/hooks \
  -H "Content-Type: application/json" \
  -d '{
    "event": "tx-confirmation",
    "address": "SolanaWalletAddress...",
    "url": "https://your-domain.com/webhooks/sol",
    "token": "'$BLOCKCYPHER_TOKEN'"
  }'

# Litecoin
curl -X POST https://api.blockcypher.com/v1/ltc/main/hooks \
  -H "Content-Type: application/json" \
  -d '{
    "event": "tx-confirmation",
    "address": "LTC1A1z7agoat...",
    "url": "https://your-domain.com/webhooks/ltc",
    "token": "'$BLOCKCYPHER_TOKEN'"
  }'
```

#### Webhook URL Format

Your webhook endpoints should follow this pattern:

```
https://your-domain.com/webhooks/{network}
```

Where `{network}` is one of: `eth`, `btc`, `sol`, `ltc`

---

## Event Format Specifications

### Ethereum (ETH) Event Format

**Event Type**: `tx-confirmation`

**Payload Structure**:

```json
{
  "hash": "0x1234567890abcdef...",
  "addresses": [
    "0xsender_address...",
    "0xrecipient_address..."
  ],
  "total": "1500000000000000000",
  "fees": "21000000000000",
  "size": 21000,
  "vsize": 21000,
  "preference": "high",
  "relayed_by": "1.2.3.4",
  "received": "2024-01-15T10:30:45.123Z",
  "ver": 1,
  "double_spend": false,
  "vin_sz": 1,
  "vout_sz": 2,
  "confirmations": 1,
  "inputs": [
    {
      "prev_hash": "0xprevious_tx_hash...",
      "output_index": 0,
      "output_value": "2000000000000000000",
      "addresses": ["0xsender_address..."],
      "script": "0x...",
      "script_type": "pay-to-pubkey-hash"
    }
  ],
  "outputs": [
    {
      "value": "1500000000000000000",
      "addresses": ["0xrecipient_address..."],
      "script": "0x...",
      "script_type": "pay-to-pubkey-hash"
    },
    {
      "value": "499999999999999000",
      "addresses": ["0xsender_address..."],
      "script": "0x...",
      "script_type": "pay-to-pubkey-hash"
    }
  ]
}
```

**Key Fields**:
- `hash`: Transaction ID (0x-prefixed hex string)
- `addresses`: Array of involved addresses
- `total`: Total transaction value in wei (1 ETH = 10^18 wei)
- `fees`: Gas fees in wei
- `confirmations`: Number of block confirmations
- `inputs`: Source addresses and amounts
- `outputs`: Destination addresses and amounts

### Bitcoin (BTC) Event Format

**Event Type**: `tx-confirmation`

**Payload Structure**:

```json
{
  "hash": "abcdef1234567890...",
  "addresses": [
    "1A1z7agoat...",
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
  ],
  "total": "50000000",
  "fees": "10000",
  "size": 225,
  "vsize": 225,
  "preference": "high",
  "relayed_by": "1.2.3.4",
  "received": "2024-01-15T10:30:45.123Z",
  "ver": 1,
  "double_spend": false,
  "vin_sz": 1,
  "vout_sz": 2,
  "confirmations": 1,
  "inputs": [
    {
      "prev_hash": "previous_tx_hash...",
      "output_index": 0,
      "output_value": "60000000",
      "addresses": ["1A1z7agoat..."],
      "script": "483045022100...",
      "script_type": "pay-to-pubkey-hash"
    }
  ],
  "outputs": [
    {
      "value": "50000000",
      "addresses": ["1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
      "script": "76a914...",
      "script_type": "pay-to-pubkey-hash"
    },
    {
      "value": "9990000",
      "addresses": ["1A1z7agoat..."],
      "script": "76a914...",
      "script_type": "pay-to-pubkey-hash"
    }
  ]
}
```

**Key Fields**:
- `hash`: Transaction ID (hex string, no prefix)
- `addresses`: Array of involved addresses
- `total`: Total transaction value in satoshis (1 BTC = 10^8 satoshis)
- `fees`: Miner fees in satoshis
- `size`: Transaction size in bytes
- `vsize`: Virtual size (for SegWit transactions)
- `inputs`: UTXO inputs being spent
- `outputs`: UTXO outputs being created

### Solana (SOL) Event Format

**Event Type**: `tx-confirmation`

**Payload Structure**:

```json
{
  "hash": "5Zzgvz5FHWLaLBbKZrQqKp7...",
  "addresses": [
    "SolanaWalletAddress1...",
    "SolanaWalletAddress2..."
  ],
  "total": "5000000000",
  "fees": "5000",
  "size": 1232,
  "vsize": 1232,
  "preference": "high",
  "relayed_by": "1.2.3.4",
  "received": "2024-01-15T10:30:45.123Z",
  "ver": 1,
  "double_spend": false,
  "vin_sz": 1,
  "vout_sz": 2,
  "confirmations": 1,
  "inputs": [
    {
      "prev_hash": "previous_tx_hash...",
      "output_index": 0,
      "output_value": "6000000000",
      "addresses": ["SolanaWalletAddress1..."],
      "script": "base64_encoded_instruction...",
      "script_type": "system-program"
    }
  ],
  "outputs": [
    {
      "value": "5000000000",
      "addresses": ["SolanaWalletAddress2..."],
      "script": "base64_encoded_instruction...",
      "script_type": "system-program"
    },
    {
      "value": "999995000",
      "addresses": ["SolanaWalletAddress1..."],
      "script": "base64_encoded_instruction...",
      "script_type": "system-program"
    }
  ]
}
```

**Key Fields**:
- `hash`: Transaction signature (base58 encoded)
- `addresses`: Array of involved account addresses
- `total`: Total transaction value in lamports (1 SOL = 10^9 lamports)
- `fees`: Transaction fees in lamports
- `inputs`: Source accounts and amounts
- `outputs`: Destination accounts and amounts

### Litecoin (LTC) Event Format

**Event Type**: `tx-confirmation`

**Payload Structure**:

```json
{
  "hash": "ltc_tx_hash_here...",
  "addresses": [
    "LTC1A1z7agoat...",
    "LTC1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
  ],
  "total": "100000000",
  "fees": "10000",
  "size": 225,
  "vsize": 225,
  "preference": "high",
  "relayed_by": "1.2.3.4",
  "received": "2024-01-15T10:30:45.123Z",
  "ver": 1,
  "double_spend": false,
  "vin_sz": 1,
  "vout_sz": 2,
  "confirmations": 1,
  "inputs": [
    {
      "prev_hash": "previous_tx_hash...",
      "output_index": 0,
      "output_value": "110000000",
      "addresses": ["LTC1A1z7agoat..."],
      "script": "483045022100...",
      "script_type": "pay-to-pubkey-hash"
    }
  ],
  "outputs": [
    {
      "value": "100000000",
      "addresses": ["LTC1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
      "script": "76a914...",
      "script_type": "pay-to-pubkey-hash"
    },
    {
      "value": "9990000",
      "addresses": ["LTC1A1z7agoat..."],
      "script": "76a914...",
      "script_type": "pay-to-pubkey-hash"
    }
  ]
}
```

**Key Fields**:
- Similar to Bitcoin format
- `total`: Total transaction value in litoshis (1 LTC = 10^8 litoshis)
- `fees`: Miner fees in litoshis

---

## HMAC-SHA256 Authentication

### Overview

All webhook payloads are signed using HMAC-SHA256 to ensure:
1. **Authenticity**: Verify the payload came from BlockCypher
2. **Integrity**: Confirm the payload hasn't been modified in transit
3. **Non-repudiation**: Prove the origin of the message

### Signature Generation

BlockCypher generates the signature as follows:

```
Signature = HMAC-SHA256(Secret Key, Payload)
```

Where:
- **Secret Key**: Your `WEBHOOK_SECRET_KEY` from `.env`
- **Payload**: The raw JSON body (not parsed, exact bytes)

### Signature Verification

Implement signature verification in your webhook handler:

```python
import hmac
import hashlib
import json
from typing import Tuple

def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret_key: str
) -> Tuple[bool, str]:
    """
    Verify HMAC-SHA256 signature of webhook payload.
    
    Args:
        payload_bytes: Raw request body bytes
        signature_header: X-Signature header value from request
        secret_key: WEBHOOK_SECRET_KEY from environment
    
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        # Generate expected signature
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant-time comparison)
        is_valid = hmac.compare_digest(
            expected_signature,
            signature_header
        )
        
        if is_valid:
            return True, "Signature verified"
        else:
            return False, f"Signature mismatch. Expected: {expected_signature}, Got: {signature_header}"
    
    except Exception as e:
        return False, f"Signature verification error: {str(e)}"


# Usage in Flask/FastAPI handler
from flask import request

@app.route('/webhooks/eth', methods=['POST'])
def handle_eth_webhook():
    payload_bytes = request.get_data()
    signature = request.headers.get('X-Signature')
    secret_key = os.getenv('WEBHOOK_SECRET_KEY')
    
    is_valid, message = verify_webhook_signature(
        payload_bytes,
        signature,
        secret_key
    )
    
    if not is_valid:
        logger.warning(f"Invalid webhook signature: {message}")
        return {"error": "Invalid signature"}, 401
    
    # Process webhook
    payload = json.loads(payload_bytes)
    process_transaction(payload)
    
    return {"status": "received"}, 200
```

### Header Format

BlockCypher sends the signature in the `X-Signature` header:

```
X-Signature: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

### Testing Signature Verification

```python
import hmac
import hashlib

# Test payload
payload = b'{"hash": "test", "total": "1000"}'
secret = "my-secret-key-32-characters-long"

# Generate signature
signature = hmac.new(
    secret.encode('utf-8'),
    payload,
    hashlib.sha256
).hexdigest()

print(f"Signature: {signature}")
# Output: 7f8e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1
```

---

## Retry Mechanism

### Overview

Webhook delivery failures are automatically retried using exponential backoff. This ensures transient network issues don't cause missed transactions.

### Retry Configuration

```bash
# .env configuration
WEBHOOK_MAX_RETRIES=5              # Maximum retry attempts
WEBHOOK_RETRY_DELAY=5              # Initial delay in seconds
WEBHOOK_RETRY_BACKOFF=2            # Exponential backoff multiplier
WEBHOOK_RETRY_MAX_DELAY=300        # Maximum delay between retries (5 min)
```

### Retry Schedule

With default configuration, retries occur at:

```
Attempt 1: Immediate (0s)
Attempt 2: 5s delay
Attempt 3: 10s delay (5s × 2)
Attempt 4: 20s delay (10s × 2)
Attempt 5: 40s delay (20s × 2)
Attempt 6: 80s delay (40s × 2)

Total time: ~155 seconds (~2.6 minutes)
```

### Retry Logic Implementation

```python
import asyncio
import aiohttp
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class WebhookRetryHandler:
    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: int = 5,
        backoff_multiplier: float = 2.0,
        max_delay: int = 300
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay
    
    async def send_with_retry(
        self,
        url: str,
        payload: dict,
        signature: str,
        timeout: int = 30
    ) -> bool:
        """
        Send webhook with automatic retry on failure.
        
        Args:
            url: Webhook endpoint URL
            payload: JSON payload to send
            signature: HMAC-SHA256 signature
            timeout: Request timeout in seconds
        
        Returns:
            True if successful, False if all retries exhausted
        """
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature
        }
        
        delay = self.initial_delay
        
        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        if response.status == 200:
                            logger.info(f"Webhook delivered successfully: {url}")
                            return True
                        elif response.status >= 500:
                            # Server error - retry
                            logger.warning(
                                f"Webhook delivery failed (attempt {attempt}/{self.max_retries}): "
                                f"HTTP {response.status}"
                            )
                        else:
                            # Client error - don't retry
                            logger.error(
                                f"Webhook delivery failed (no retry): HTTP {response.status}"
                            )
                            return False
            
            except asyncio.TimeoutError:
                logger.warning(
                    f"Webhook delivery timeout (attempt {attempt}/{self.max_retries})"
                )
            except aiohttp.ClientError as e:
                logger.warning(
                    f"Webhook delivery error (attempt {attempt}/{self.max_retries}): {str(e)}"
                )
            
            # Calculate next delay
            if attempt < self.max_retries:
                delay = min(
                    int(delay * self.backoff_multiplier),
                    self.max_delay
                )
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
        
        logger.error(f"Webhook delivery failed after {self.max_retries} attempts: {url}")
        return False
```

### Idempotent Processing

To handle potential duplicate deliveries, implement idempotent processing:

```python
from datetime import datetime, timedelta
import hashlib

class IdempotentWebhookProcessor:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_event_hash(self, payload: dict) -> str:
        """
        Generate unique hash for webhook event.
        """
        # Use transaction hash + timestamp for uniqueness
        event_key = f"{payload['hash']}_{payload['received']}"
        return hashlib.sha256(event_key.encode()).hexdigest()
    
    async def process_webhook(
        self,
        payload: dict,
        network: str
    ) -> bool:
        """
        Process webhook with idempotency check.
        """
        event_hash = self.get_event_hash(payload)
        
        # Check if already processed
        existing = await self.db.query(
            "SELECT id FROM webhook_events WHERE event_hash = %s",
            (event_hash,)
        )
        
        if existing:
            logger.info(f"Duplicate webhook detected: {event_hash}")
            return True  # Already processed
        
        try:
            # Process transaction
            await self.process_transaction(payload, network)
            
            # Record processed event
            await self.db.execute(
                "INSERT INTO webhook_events (event_hash, network, payload, processed_at) "
                "VALUES (%s, %s, %s, %s)",
                (event_hash, network, json.dumps(payload), datetime.utcnow())
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return False
```

---

## Dead Letter Queue (DLQ) Handling

### Overview

The Dead Letter Queue stores webhooks that fail all retry attempts. This allows manual investigation and recovery of missed transactions.

### DLQ Configuration

```bash
# .env configuration
DLQ_ENABLED=true                   # Enable DLQ
DLQ_DB_PATH=./data/dlq.db          # SQLite database for DLQ
DLQ_RETENTION_DAYS=30              # Keep DLQ entries for 30 days
DLQ_ALERT_THRESHOLD=10             # Alert when 10+ items in DLQ
```

### DLQ Schema

```sql
CREATE TABLE IF NOT EXISTS dlq_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_hash TEXT UNIQUE NOT NULL,
    network TEXT NOT NULL,
    payload JSON NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    first_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

CREATE INDEX idx_dlq_network ON dlq_events(network);
CREATE INDEX idx_dlq_created ON dlq_events(created_at);
CREATE INDEX idx_dlq_resolved ON dlq_events(resolved_at);
```

### DLQ Processing

```python
import sqlite3
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

class DeadLetterQueue:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize DLQ database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dlq_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_hash TEXT UNIQUE NOT NULL,
                network TEXT NOT NULL,
                payload JSON NOT NULL,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                first_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolution_notes TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dlq_network ON dlq_events(network)
        """)
        
        conn.commit()
        conn.close()
    
    def add_to_dlq(
        self,
        event_hash: str,
        network: str,
        payload: dict,
        error_message: str,
        retry_count: int
    ) -> bool:
        """
        Add failed webhook to DLQ.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO dlq_events 
                (event_hash, network, payload, error_message, retry_count)
                VALUES (?, ?, ?, ?, ?)
            """, (
                event_hash,
                network,
                json.dumps(payload),
                error_message,
                retry_count
            ))
            
            conn.commit()
            conn.close()
            
            logger.error(
                f"Event added to DLQ: {event_hash} ({network}) - {error_message}"
            )
            return True
        
        except sqlite3.IntegrityError:
            # Event already in DLQ, update it
            return self.update_dlq_entry(event_hash, error_message, retry_count)
        
        except Exception as e:
            logger.error(f"Error adding to DLQ: {str(e)}")
            return False
    
    def update_dlq_entry(
        self,
        event_hash: str,
        error_message: str,
        retry_count: int
    ) -> bool:
        """
        Update existing DLQ entry.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE dlq_events
                SET error_message = ?, retry_count = ?, last_attempt_at = CURRENT_TIMESTAMP
                WHERE event_hash = ?
            """, (error_message, retry_count, event_hash))
            
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            logger.error(f"Error updating DLQ entry: {str(e)}")
            return False
    
    def get_dlq_events(
        self,
        network: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """
        Retrieve unresolved DLQ events.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if network:
                cursor.execute("""
                    SELECT * FROM dlq_events
                    WHERE resolved_at IS NULL AND network = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (network, limit))
            else:
                cursor.execute("""
                    SELECT * FROM dlq_events
                    WHERE resolved_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            events = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return events
        
        except Exception as e:
            logger.error(f"Error retrieving DLQ events: {str(e)}")
            return []
    
    def resolve_dlq_event(
        self,
        event_hash: str,
        resolution_notes: str
    ) -> bool:
        """
        Mark DLQ event as resolved.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE dlq_events
                SET resolved_at = CURRENT_TIMESTAMP, resolution_notes = ?
                WHERE event_hash = ?
            """, (resolution_notes, event_hash))
            
            conn.commit()
            conn.close()
            
            logger.info(f"DLQ event resolved: {event_hash}")
            return True
        
        except Exception as e:
            logger.error(f"Error resolving DLQ event: {str(e)}")
            return False
    
    def cleanup_old_entries(self, retention_days: int = 30) -> int:
        """
        Remove resolved entries older than retention period.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            cursor.execute("""
                DELETE FROM dlq_events
                WHERE resolved_at IS NOT NULL AND resolved_at < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old DLQ entries")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning up DLQ: {str(e)}")
            return 0
```

### DLQ Recovery

To manually retry a DLQ event:

```python
async def retry_dlq_event(event_hash: str, dlq: DeadLetterQueue):
    """
    Manually retry a DLQ event.
    """
    events = dlq.get_dlq_events()
    event = next((e for e in events if e['event_hash'] == event_hash), None)
    
    if not event:
        logger.error(f"DLQ event not found: {event_hash}")
        return False
    
    payload = json.loads(event['payload'])
    network = event['network']
    
    try:
        # Reprocess the transaction
        await process_transaction(payload, network)
        
        # Mark as resolved
        dlq.resolve_dlq_event(event_hash, "Manually retried and processed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error retrying DLQ event: {str(e)}")
        return False
```

---

## Monitoring Dashboard

### Overview

The monitoring dashboard provides real-time visibility into webhook delivery, transaction processing, and system health.

### Dashboard Metrics

#### 1. Delivery Metrics

```python
class DeliveryMetrics:
    """
    Track webhook delivery performance.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_delivery_stats(
        self,
        network: Optional[str] = None,
        hours: int = 24
    ) -> dict:
        """
        Get delivery statistics for the past N hours.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        if network:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_events,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    AVG(delivery_time_ms) as avg_latency_ms,
                    MAX(delivery_time_ms) as max_latency_ms,
                    MIN(delivery_time_ms) as min_latency_ms
                FROM webhook_deliveries
                WHERE network = ? AND created_at > ?
            """, (network, cutoff_time))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as total_events,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    AVG(delivery_time_ms) as avg_latency_ms,
                    MAX(delivery_time_ms) as max_latency_ms,
                    MIN(delivery_time_ms) as min_latency_ms
                FROM webhook_deliveries
                WHERE created_at > ?
            """, (cutoff_time,))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'total_events': row[0] or 0,
            'successful': row[1] or 0,
            'failed': row[2] or 0,
            'pending': row[3] or 0,
            'success_rate': (row[1] / row[0] * 100) if row[0] else 0,
            'avg_latency_ms': row[4] or 0,
            'max_latency_ms': row[5] or 0,
            'min_latency_ms': row[6] or 0
        }
```

#### 2. Network-Specific Metrics

```python
def get_network_metrics(network: str, hours: int = 24) -> dict:
    """
    Get metrics for a specific blockchain network.
    """
    stats = metrics.get_delivery_stats(network=network, hours=hours)
    
    return {
        'network': network,
        'period_hours': hours,
        'delivery_stats': stats,
        'dlq_count': dlq.get_dlq_count(network),
        'last_event': get_last_event_time(network),
        'health_status': determine_health_status(stats)
    }

def determine_health_status(stats: dict) -> str:
    """
    Determine network health based on metrics.
    """
    success_rate = stats['success_rate']
    
    if success_rate >= 99:
        return 'HEALTHY'
    elif success_rate >= 95:
        return 'DEGRADED'
    elif success_rate >= 80:
        return 'UNHEALTHY'
    else:
        return 'CRITICAL'
```

#### 3. Dashboard API Endpoints

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/monitoring/dashboard', methods=['GET'])
def get_dashboard():
    """
    Get complete dashboard data.
    """
    return jsonify({
        'timestamp': datetime.utcnow().isoformat(),
        'networks': {
            'eth': get_network_metrics('eth'),
            'btc': get_network_metrics('btc'),
            'sol': get_network_metrics('sol'),
            'ltc': get_network_metrics('ltc')
        },
        'dlq': {
            'total_unresolved': dlq.get_dlq_count(),
            'by_network': dlq.get_dlq_count_by_network()
        },
        'system': {
            'uptime_seconds': get_uptime(),
            'memory_usage_mb': get_memory_usage(),
            'cpu_usage_percent': get_cpu_usage()
        }
    })

@app.route('/api/monitoring/network/<network>', methods=['GET'])
def get_network_dashboard(network: str):
    """
    Get metrics for a specific network.
    """
    return jsonify(get_network_metrics(network))

@app.route('/api/monitoring/dlq', methods=['GET'])
def get_dlq_dashboard():
    """
    Get DLQ status and recent events.
    """
    return jsonify({
        'total_unresolved': dlq.get_dlq_count(),
        'by_network': dlq.get_dlq_count_by_network(),
        'recent_events': dlq.get_dlq_events(limit=20),
        'alert_threshold_exceeded': dlq.get_dlq_count() > 10
    })
```

### Dashboard UI

Access the monitoring dashboard at:

```
https://your-domain.com/monitoring
```

**Key Sections**:

1. **Network Status**: Real-time health for each blockchain
2. **Delivery Metrics**: Success rates, latency, throughput
3. **DLQ Monitor**: Unresolved events, error patterns
4. **System Health**: CPU, memory, uptime
5. **Alerts**: Critical issues requiring attention

---

## Testing & Validation

### Test Webhook Payloads

#### Ethereum Test Payload

```bash
curl -X POST http://localhost:8000/webhooks/eth \
  -H "Content-Type: application/json" \
  -H "X-Signature: $(echo -n '{"hash": "0x1234567890abcdef", "total": "1500000000000000000", "confirmations": 1}' | openssl dgst -sha256 -hmac 'your-secret-key' -hex | cut -d' ' -f2)" \
  -d '{
    "hash": "0x1234567890abcdef",
    "addresses": ["0xsender", "0xrecipient"],
    "total": "1500000000000000000",
    "fees": "21000000000000",
    "confirmations": 1,
    "received": "2024-01-15T10:30:45.123Z",
    "inputs": [{"output_value": "2000000000000000000", "addresses": ["0xsender"]}],
    "outputs": [{"value": "1500000000000000000", "addresses": ["0xrecipient"]}]
  }'
```

#### Bitcoin Test Payload

```bash
curl -X POST http://localhost:8000/webhooks/btc \
  -H "Content-Type: application/json" \
  -H "X-Signature: $(echo -n '{"hash": "abc123", "total": "50000000", "confirmations": 1}' | openssl dgst -sha256 -hmac 'your-secret-key' -hex | cut -d' ' -f2)" \
  -d '{
    "hash": "abc123",
    "addresses": ["1A1z7agoat", "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
    "total": "50000000",
    "fees": "10000",
    "confirmations": 1,
    "received": "2024-01-15T10:30:45.123Z",
    "inputs": [{"output_value": "60000000", "addresses": ["1A1z7agoat"]}],
    "outputs": [{"value": "50000000", "addresses": ["1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"]}]
  }'
```

#### Solana Test Payload

```bash
curl -X POST http://localhost:8000/webhooks/sol \
  -H "Content-Type: application/json" \
  -H "X-Signature: $(echo -n '{"hash": "5Zzgvz5FHWLaLBbKZrQqKp7", "total": "5000000000", "confirmations": 1}' | openssl dgst -sha256 -hmac 'your-secret-key' -hex | cut -d' ' -f2)" \
  -d '{
    "hash": "5Zzgvz5FHWLaLBbKZrQqKp7",
    "addresses": ["SolanaWalletAddress1", "SolanaWalletAddress2"],
    "total": "5000000000",
    "fees": "5000",
    "confirmations": 1,
    "received": "2024-01-15T10:30:45.123Z",
    "inputs": [{"output_value": "6000000000", "addresses": ["SolanaWalletAddress1"]}],
    "outputs": [{"value": "5000000000", "addresses": ["SolanaWalletAddress2"]}]
  }'
```

#### Litecoin Test Payload

```bash
curl -X POST http://localhost:8000/webhooks/ltc \
  -H "Content-Type: application/json" \
  -H "X-Signature: $(echo -n '{"hash": "ltc123", "total": "100000000", "confirmations": 1}' | openssl dgst -sha256 -hmac 'your-secret-key' -hex | cut -d' ' -f2)" \
  -d '{
    "hash": "ltc123",
    "addresses": ["LTC1A1z7agoat", "LTC1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"],
    "total": "100000000",
    "fees": "10000",
    "confirmations": 1,
    "received": "2024-01-15T10:30:45.123Z",
    "inputs": [{"output_value": "110000000", "addresses": ["LTC1A1z7agoat"]}],
    "outputs": [{"value": "100000000", "addresses": ["LTC1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"]}]
  }'
```

### Signature Generation Helper

```python
import hmac
import hashlib
import json

def generate_test_signature(payload: dict, secret_key: str) -> str:
    """
    Generate HMAC-SHA256 signature for testing.
    """
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(
        secret_key.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return signature

# Usage
payload = {
    "hash": "0x1234567890abcdef",
    "total": "1500000000000000000",
    "confirmations": 1
}

secret = "your-secret-key-here"
signature = generate_test_signature(payload, secret)
print(f"Signature: {signature}")
```

### Validation Checklist

- [ ] Webhook server is running and accessible
- [ ] Firewall allows inbound connections on webhook port
- [ ] HMAC-SHA256 signature verification is working
- [ ] Retry mechanism is functioning correctly
- [ ] DLQ is capturing failed events
- [ ] Monitoring dashboard is displaying metrics
- [ ] Test payloads are being processed successfully
- [ ] Idempotent processing prevents duplicates
- [ ] Alerts are triggered for critical issues

---

## Troubleshooting

### Common Issues

#### 1. Webhook Not Receiving Events

**Symptoms**: No webhook events arriving

**Diagnosis**:
```bash
# Check if server is running
curl -s http://localhost:8000/health

# Check firewall
sudo ufw status

# Check logs
tail -f /var/log/webhook-receiver.log
```

**Solutions**:
- Verify webhook URL is publicly accessible
- Check firewall rules allow inbound traffic
- Verify BlockCypher webhook registration
- Check server logs for errors

#### 2. Signature Verification Failures

**Symptoms**: "Invalid signature" errors in logs

**Diagnosis**:
```python
# Test signature generation
import hmac
import hashlib

payload = b'{"test": "data"}'
secret = "your-secret-key"

expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
print(f"Expected signature: {expected}")
```

**Solutions**:
- Verify `WEBHOOK_SECRET_KEY` matches BlockCypher configuration
- Ensure payload bytes are not modified before verification
- Check for encoding issues (UTF-8)

#### 3. High Latency or Timeouts

**Symptoms**: Slow webhook processing, timeout errors

**Diagnosis**:
```bash
# Check system resources
free -h
top -b -n 1 | head -20

# Check network connectivity
ping blockcypher.com
```

**Solutions**:
- Increase `WEBHOOK_TIMEOUT` value
- Optimize database queries
- Scale webhook server (add more workers)
- Check network connectivity

#### 4. DLQ Growing Too Large

**Symptoms**: Many events in DLQ, potential data loss

**Diagnosis**:
```python
# Check DLQ size
from webhooks.dlq import DeadLetterQueue
dlq = DeadLetterQueue('./data/dlq.db')
print(f"Unresolved events: {dlq.get_dlq_count()}")
print(f"By network: {dlq.get_dlq_count_by_network()}")
```

**Solutions**:
- Investigate root cause of failures
- Manually retry failed events
- Check BlockCypher API status
- Review error messages in DLQ

#### 5. Duplicate Event Processing

**Symptoms**: Same transaction processed multiple times

**Diagnosis**:
```python
# Check for duplicate event hashes
from webhooks.processor import IdempotentWebhookProcessor
processor = IdempotentWebhookProcessor(db)

# Query for duplicates
duplicates = processor.find_duplicate_events()
print(f"Found {len(duplicates)} duplicate events")
```

**Solutions**:
- Ensure idempotent processing is enabled
- Check event hash generation logic
- Review database constraints

### Debug Logging

Enable debug logging for detailed troubleshooting:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('webhook-debug.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.debug("Detailed debug information")
```

### Performance Optimization

```python
# Use connection pooling
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://user:password@localhost/db',
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)

# Use async processing
import asyncio

async def process_webhooks_batch(webhooks: list):
    tasks = [process_webhook(w) for w in webhooks]
    await asyncio.gather(*tasks)

# Add caching
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_wallet_info(address: str):
    return db.query(f"SELECT * FROM wallets WHERE address = '{address}'")
```

---

## Support & Resources

- **BlockCypher Documentation**: https://www.blockcypher.com/dev/bitcoin/
- **Webhook Best Practices**: https://www.svix.com/webhooks/
- **HMAC-SHA256 Reference**: https://tools.ietf.org/html/rfc4868
- **Project Repository**: [Your repo URL]
- **Issue Tracker**: [Your issue tracker URL]

---

**Last Updated**: January 2024
**Version**: 1.0.0
