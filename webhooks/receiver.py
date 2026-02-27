"""
Webhook receiver module for handling blockchain transaction events.

Implements:
- Async HTTP server using aiohttp
- HMAC-SHA256 signature verification for webhook authentication
- Event parsing for multiple blockchain networks (ETH, BTC, SOL, LTC)
- Idempotency checks to prevent duplicate event processing
- Event persistence to bot_data.json
- Error handling and validation
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from aiohttp import web
from dataclasses import dataclass, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    """Webhook event data structure."""
    event_id: str
    network: str
    tx_hash: str
    confirmation_count: int
    timestamp: str
    event_type: str
    data: Dict[str, Any]
    received_at: str


class WebhookReceiver:
    """
    Async HTTP webhook receiver for blockchain transaction events.
    
    Handles:
    - HMAC-SHA256 signature verification
    - Event parsing for multiple networks
    - Idempotency checks
    - Event persistence
    - Error handling and validation
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        webhook_secret: str = "",
        bot_data_path: str = "bot_data.json",
        events_path: str = "webhook_events.json",
    ):
        """
        Initialize the webhook receiver.

        Args:
            host: Host to bind the HTTP server to
            port: Port to bind the HTTP server to
            webhook_secret: Secret key for HMAC-SHA256 signature verification
            bot_data_path: Path to bot_data.json file
            events_path: Path to webhook_events.json file
        """
        self.host = host
        self.port = port
        self.webhook_secret = webhook_secret.encode() if webhook_secret else b""
        self.bot_data_path = Path(bot_data_path)
        self.events_path = Path(events_path)
        self.app = web.Application()
        self.runner = None
        self.site = None
        
        # Setup routes
        self.app.router.add_post('/webhook', self.handle_webhook)
        self.app.router.add_get('/health', self.handle_health)
        
        # Initialize event storage
        self._init_event_storage()

    def _init_event_storage(self) -> None:
        """Initialize webhook event storage files."""
        if not self.events_path.exists():
            self.events_path.write_text(json.dumps({"events": [], "processed_ids": []}, indent=2))
            logger.info(f"Created webhook events file: {self.events_path}")

    def _load_events(self) -> Dict[str, Any]:
        """Load events from storage."""
        try:
            if self.events_path.exists():
                return json.loads(self.events_path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading events: {e}")
        return {"events": [], "processed_ids": []}

    def _save_events(self, data: Dict[str, Any]) -> None:
        """Save events to storage."""
        try:
            self.events_path.write_text(json.dumps(data, indent=2))
        except IOError as e:
            logger.error(f"Error saving events: {e}")

    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify HMAC-SHA256 signature.

        Args:
            payload: Raw request body
            signature: Signature from X-Webhook-Signature header

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature verification")
            return True

        try:
            # Compute expected signature
            expected_signature = hmac.new(
                self.webhook_secret,
                payload,
                hashlib.sha256
            ).hexdigest()

            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def _check_idempotency(self, event_id: str) -> bool:
        """
        Check if event has already been processed.

        Args:
            event_id: Unique event identifier

        Returns:
            True if event is new, False if already processed
        """
        data = self._load_events()
        return event_id not in data.get("processed_ids", [])

    def _mark_processed(self, event_id: str) -> None:
        """Mark event as processed."""
        data = self._load_events()
        if event_id not in data.get("processed_ids", []):
            data["processed_ids"].append(event_id)
            self._save_events(data)

    def _parse_ethereum_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Ethereum webhook event."""
        try:
            return WebhookEvent(
                event_id=payload.get("event_id", ""),
                network="ETH",
                tx_hash=payload.get("tx_hash", ""),
                confirmation_count=payload.get("confirmations", 0),
                timestamp=payload.get("timestamp", ""),
                event_type=payload.get("type", "transaction"),
                data={
                    "from": payload.get("from"),
                    "to": payload.get("to"),
                    "value": payload.get("value"),
                    "gas_price": payload.get("gas_price"),
                    "gas_used": payload.get("gas_used"),
                },
                received_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error parsing Ethereum event: {e}")
            return None

    def _parse_bitcoin_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Bitcoin webhook event."""
        try:
            return WebhookEvent(
                event_id=payload.get("event_id", ""),
                network="BTC",
                tx_hash=payload.get("tx_hash", ""),
                confirmation_count=payload.get("confirmations", 0),
                timestamp=payload.get("timestamp", ""),
                event_type=payload.get("type", "transaction"),
                data={
                    "inputs": payload.get("inputs", []),
                    "outputs": payload.get("outputs", []),
                    "fee": payload.get("fee"),
                    "size": payload.get("size"),
                },
                received_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error parsing Bitcoin event: {e}")
            return None

    def _parse_solana_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Solana webhook event."""
        try:
            return WebhookEvent(
                event_id=payload.get("event_id", ""),
                network="SOL",
                tx_hash=payload.get("tx_hash", ""),
                confirmation_count=payload.get("confirmations", 0),
                timestamp=payload.get("timestamp", ""),
                event_type=payload.get("type", "transaction"),
                data={
                    "accounts": payload.get("accounts", []),
                    "instructions": payload.get("instructions", []),
                    "fee": payload.get("fee"),
                    "slot": payload.get("slot"),
                },
                received_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error parsing Solana event: {e}")
            return None

    def _parse_litecoin_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """Parse Litecoin webhook event."""
        try:
            return WebhookEvent(
                event_id=payload.get("event_id", ""),
                network="LTC",
                tx_hash=payload.get("tx_hash", ""),
                confirmation_count=payload.get("confirmations", 0),
                timestamp=payload.get("timestamp", ""),
                event_type=payload.get("type", "transaction"),
                data={
                    "inputs": payload.get("inputs", []),
                    "outputs": payload.get("outputs", []),
                    "fee": payload.get("fee"),
                    "size": payload.get("size"),
                },
                received_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error parsing Litecoin event: {e}")
            return None

    def _parse_event(self, payload: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        Parse webhook event based on network type.

        Args:
            payload: Webhook payload

        Returns:
            Parsed WebhookEvent or None if parsing fails
        """
        network = payload.get("network", "").upper()

        if network == "ETH":
            return self._parse_ethereum_event(payload)
        elif network == "BTC":
            return self._parse_bitcoin_event(payload)
        elif network == "SOL":
            return self._parse_solana_event(payload)
        elif network == "LTC":
            return self._parse_litecoin_event(payload)
        else:
            logger.error(f"Unknown network: {network}")
            return None

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """
        Handle incoming webhook request.

        Args:
            request: aiohttp request object

        Returns:
            JSON response with status
        """
        try:
            # Read raw body for signature verification
            body = await request.read()

            # Get signature from header
            signature = request.headers.get("X-Webhook-Signature", "")

            # Verify signature
            if not self._verify_signature(body, signature):
                logger.warning("Invalid webhook signature")
                return web.json_response(
                    {"error": "Invalid signature"},
                    status=401
                )

            # Parse JSON payload
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                logger.error("Invalid JSON payload")
                return web.json_response(
                    {"error": "Invalid JSON"},
                    status=400
                )

            # Validate required fields
            event_id = payload.get("event_id")
            if not event_id:
                logger.error("Missing event_id in payload")
                return web.json_response(
                    {"error": "Missing event_id"},
                    status=400
                )

            # Check idempotency
            if not self._check_idempotency(event_id):
                logger.info(f"Duplicate event received: {event_id}")
                return web.json_response(
                    {"status": "duplicate", "event_id": event_id},
                    status=200
                )

            # Parse event
            event = self._parse_event(payload)
            if not event:
                logger.error(f"Failed to parse event: {event_id}")
                return web.json_response(
                    {"error": "Failed to parse event"},
                    status=400
                )

            # Store event
            data = self._load_events()
            data["events"].append(asdict(event))
            self._save_events(data)

            # Mark as processed
            self._mark_processed(event_id)

            logger.info(f"Webhook received and stored: {event_id} ({event.network})")

            return web.json_response(
                {
                    "status": "received",
                    "event_id": event_id,
                    "network": event.network,
                    "tx_hash": event.tx_hash,
                },
                status=200
            )

        except Exception as e:
            logger.error(f"Error handling webhook: {e}", exc_info=True)
            return web.json_response(
                {"error": "Internal server error"},
                status=500
            )

    async def handle_health(self, request: web.Request) -> web.Response:
        """
        Handle health check request.

        Args:
            request: aiohttp request object

        Returns:
            JSON response with health status
        """
        return web.json_response(
            {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
            },
            status=200
        )

    async def start(self) -> None:
        """Start the webhook receiver server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            logger.info(f"Webhook receiver started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Error starting webhook receiver: {e}")
            raise

    async def stop(self) -> None:
        """Stop the webhook receiver server."""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("Webhook receiver stopped")
        except Exception as e:
            logger.error(f"Error stopping webhook receiver: {e}")

    async def run(self) -> None:
        """Run the webhook receiver server (blocking)."""
        await self.start()
        try:
            # Keep the server running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()


# Standalone server function for direct execution
async def run_webhook_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    webhook_secret: str = "",
) -> None:
    """
    Run webhook receiver as standalone server.

    Args:
        host: Host to bind to
        port: Port to bind to
        webhook_secret: Secret for HMAC verification
    """
    receiver = WebhookReceiver(
        host=host,
        port=port,
        webhook_secret=webhook_secret,
    )
    await receiver.run()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", 8080))
    secret = os.getenv("WEBHOOK_SECRET", "")

    asyncio.run(run_webhook_server(host, port, secret))
