"""
Event processor module for handling transaction events asynchronously.

Implements:
- Async task queue for event processing
- Confirmation counting with configurable threshold
- Trade state updates (pending → confirmed → completed)
- Dead letter queue for failed events
- Retry mechanism with exponential backoff (max 5 attempts)
- Error logging with event ID for debugging
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradeStatus(str, Enum):
    """Trade status enumeration."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Event:
    """Event data structure."""
    event_id: str
    trade_id: str
    tx_hash: str
    confirmation_count: int
    timestamp: str
    event_type: str
    data: Dict[str, Any]
    retry_count: int = 0


@dataclass
class DeadLetterEvent:
    """Dead letter queue event structure."""
    event_id: str
    trade_id: str
    error_message: str
    timestamp: str
    retry_count: int
    original_event: Dict[str, Any]


class EventProcessor:
    """
    Asynchronous event processor for blockchain transaction events.
    
    Handles:
    - Event queue management
    - Confirmation counting with configurable threshold
    - Trade state updates
    - Dead letter queue for failed events
    - Retry mechanism with exponential backoff
    """

    def __init__(
        self,
        bot_data_path: str = "bot_data.json",
        confirmation_threshold: int = 3,
        max_retries: int = 5,
        dlq_path: str = "dead_letter_queue.json",
    ):
        """
        Initialize the event processor.

        Args:
            bot_data_path: Path to bot_data.json file
            confirmation_threshold: Number of confirmations required for trade completion
            max_retries: Maximum number of retry attempts
            dlq_path: Path to dead letter queue file
        """
        self.bot_data_path = Path(bot_data_path)
        self.confirmation_threshold = confirmation_threshold
        self.max_retries = max_retries
        self.dlq_path = Path(dlq_path)
        
        # Event queue
        self.event_queue: asyncio.Queue = asyncio.Queue()
        
        # Track processing state
        self.processing = False
        self.processed_events: Dict[str, Event] = {}
        
        # Initialize files
        self._initialize_files()

    def _initialize_files(self) -> None:
        """Initialize bot_data.json and dead letter queue files."""
        # Initialize bot_data.json if it doesn't exist
        if not self.bot_data_path.exists():
            self.bot_data_path.write_text(json.dumps({"trades": {}}, indent=2))
            logger.info(f"Created {self.bot_data_path}")
        
        # Initialize dead letter queue if it doesn't exist
        if not self.dlq_path.exists():
            self.dlq_path.write_text(json.dumps({"failed_events": []}, indent=2))
            logger.info(f"Created {self.dlq_path}")

    def _load_bot_data(self) -> Dict[str, Any]:
        """Load bot_data.json."""
        try:
            content = self.bot_data_path.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading bot_data.json: {e}")
            return {"trades": {}}

    def _save_bot_data(self, data: Dict[str, Any]) -> None:
        """Save bot_data.json."""
        try:
            self.bot_data_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving bot_data.json: {e}")

    def _load_dlq(self) -> Dict[str, Any]:
        """Load dead letter queue."""
        try:
            content = self.dlq_path.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading dead letter queue: {e}")
            return {"failed_events": []}

    def _save_dlq(self, data: Dict[str, Any]) -> None:
        """Save dead letter queue."""
        try:
            self.dlq_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving dead letter queue: {e}")

    async def enqueue_event(self, event: Event) -> None:
        """
        Enqueue an event for processing.

        Args:
            event: Event to process
        """
        await self.event_queue.put(event)
        logger.info(f"Event enqueued: {event.event_id} (trade: {event.trade_id})")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _process_event_with_retry(self, event: Event) -> None:
        """
        Process event with exponential backoff retry.

        Args:
            event: Event to process

        Raises:
            Exception: If processing fails after all retries
        """
        await self._process_event(event)

    async def _process_event(self, event: Event) -> None:
        """
        Process a single event.

        Args:
            event: Event to process

        Raises:
            Exception: If processing fails
        """
        logger.info(
            f"Processing event: {event.event_id} "
            f"(trade: {event.trade_id}, confirmations: {event.confirmation_count})"
        )

        # Load current bot data
        bot_data = self._load_bot_data()
        trades = bot_data.get("trades", {})

        # Get or create trade record
        trade_id = event.trade_id
        if trade_id not in trades:
            trades[trade_id] = {
                "status": TradeStatus.PENDING.value,
                "created_at": datetime.utcnow().isoformat(),
                "confirmations": 0,
                "events": [],
            }

        trade = trades[trade_id]

        # Update confirmation count
        trade["confirmations"] = max(trade["confirmations"], event.confirmation_count)

        # Add event to trade history
        trade["events"].append({
            "event_id": event.event_id,
            "tx_hash": event.tx_hash,
            "confirmation_count": event.confirmation_count,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
        })

        # Update trade status based on confirmation count
        if event.confirmation_count >= self.confirmation_threshold:
            if trade["status"] == TradeStatus.PENDING.value:
                trade["status"] = TradeStatus.CONFIRMED.value
                trade["confirmed_at"] = datetime.utcnow().isoformat()
                logger.info(
                    f"Trade {trade_id} confirmed "
                    f"({event.confirmation_count}/{self.confirmation_threshold} confirmations)"
                )
            
            # Mark as completed if all conditions met
            if event.event_type == "final_confirmation":
                trade["status"] = TradeStatus.COMPLETED.value
                trade["completed_at"] = datetime.utcnow().isoformat()
                logger.info(f"Trade {trade_id} completed")
        else:
            logger.info(
                f"Trade {trade_id} still pending "
                f"({event.confirmation_count}/{self.confirmation_threshold} confirmations)"
            )

        # Save updated bot data
        bot_data["trades"] = trades
        self._save_bot_data(bot_data)

        # Mark event as processed
        self.processed_events[event.event_id] = event

    async def _handle_failed_event(
        self,
        event: Event,
        error: Exception,
        retry_count: int,
    ) -> None:
        """
        Handle a failed event by adding it to the dead letter queue.

        Args:
            event: Failed event
            error: Exception that caused the failure
            retry_count: Number of retries attempted
        """
        logger.error(
            f"Event processing failed: {event.event_id} "
            f"(trade: {event.trade_id}, retries: {retry_count}, error: {str(error)})"
        )

        # Load DLQ
        dlq = self._load_dlq()
        failed_events = dlq.get("failed_events", [])

        # Create dead letter event
        dlq_event = DeadLetterEvent(
            event_id=event.event_id,
            trade_id=event.trade_id,
            error_message=str(error),
            timestamp=datetime.utcnow().isoformat(),
            retry_count=retry_count,
            original_event=asdict(event),
        )

        # Add to DLQ
        failed_events.append(asdict(dlq_event))
        dlq["failed_events"] = failed_events
        self._save_dlq(dlq)

        logger.warning(
            f"Event {event.event_id} added to dead letter queue "
            f"(error: {str(error)})"
        )

    async def process_queue(self) -> None:
        """
        Process events from the queue continuously.
        
        This method should be run as a background task.
        """
        self.processing = True
        logger.info("Event processor started")

        try:
            while self.processing:
                try:
                    # Get event from queue with timeout
                    event = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=1.0,
                    )

                    try:
                        # Process event with retry mechanism
                        await self._process_event_with_retry(event)
                        self.event_queue.task_done()

                    except RetryError as e:
                        # All retries exhausted
                        await self._handle_failed_event(
                            event,
                            e.last_attempt.exception(),
                            self.max_retries,
                        )
                        self.event_queue.task_done()

                    except Exception as e:
                        # Unexpected error
                        await self._handle_failed_event(event, e, 0)
                        self.event_queue.task_done()

                except asyncio.TimeoutError:
                    # No events in queue, continue waiting
                    continue

        except asyncio.CancelledError:
            logger.info("Event processor cancelled")
        finally:
            self.processing = False
            logger.info("Event processor stopped")

    async def start(self) -> asyncio.Task:
        """
        Start the event processor as a background task.

        Returns:
            asyncio.Task: The processor task
        """
        return asyncio.create_task(self.process_queue())

    def stop(self) -> None:
        """Stop the event processor."""
        self.processing = False
        logger.info("Event processor stop requested")

    async def wait_until_processed(self, event_id: str, timeout: float = 30.0) -> bool:
        """
        Wait for a specific event to be processed.

        Args:
            event_id: ID of the event to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if event was processed, False if timeout
        """
        start_time = datetime.utcnow()
        while True:
            if event_id in self.processed_events:
                return True

            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                logger.warning(f"Timeout waiting for event {event_id}")
                return False

            await asyncio.sleep(0.1)

    def get_trade_status(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a trade.

        Args:
            trade_id: ID of the trade

        Returns:
            Trade data or None if not found
        """
        bot_data = self._load_bot_data()
        trades = bot_data.get("trades", {})
        return trades.get(trade_id)

    def get_dlq_events(self) -> List[Dict[str, Any]]:
        """
        Get all events in the dead letter queue.

        Returns:
            List of failed events
        """
        dlq = self._load_dlq()
        return dlq.get("failed_events", [])

    def retry_dlq_event(self, event_id: str) -> bool:
        """
        Retry a failed event from the dead letter queue.

        Args:
            event_id: ID of the event to retry

        Returns:
            bool: True if event was found and requeued, False otherwise
        """
        dlq = self._load_dlq()
        failed_events = dlq.get("failed_events", [])

        # Find the event
        event_data = None
        for i, event in enumerate(failed_events):
            if event["event_id"] == event_id:
                event_data = event
                failed_events.pop(i)
                break

        if not event_data:
            logger.warning(f"Event {event_id} not found in dead letter queue")
            return False

        # Save updated DLQ
        dlq["failed_events"] = failed_events
        self._save_dlq(dlq)

        # Recreate and enqueue event
        original_event = event_data["original_event"]
        event = Event(
            event_id=original_event["event_id"],
            trade_id=original_event["trade_id"],
            tx_hash=original_event["tx_hash"],
            confirmation_count=original_event["confirmation_count"],
            timestamp=original_event["timestamp"],
            event_type=original_event["event_type"],
            data=original_event["data"],
            retry_count=original_event.get("retry_count", 0) + 1,
        )

        # Enqueue for reprocessing
        asyncio.create_task(self.enqueue_event(event))
        logger.info(f"Event {event_id} requeued from dead letter queue")
        return True

    def get_queue_size(self) -> int:
        """Get the current size of the event queue."""
        return self.event_queue.qsize()

    def get_processed_count(self) -> int:
        """Get the number of processed events."""
        return len(self.processed_events)


# Singleton instance
_processor_instance: Optional[EventProcessor] = None


def get_event_processor(
    bot_data_path: str = "bot_data.json",
    confirmation_threshold: int = 3,
    max_retries: int = 5,
    dlq_path: str = "dead_letter_queue.json",
) -> EventProcessor:
    """
    Get or create the event processor singleton.

    Args:
        bot_data_path: Path to bot_data.json file
        confirmation_threshold: Number of confirmations required
        max_retries: Maximum number of retry attempts
        dlq_path: Path to dead letter queue file

    Returns:
        EventProcessor instance
    """
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = EventProcessor(
            bot_data_path=bot_data_path,
            confirmation_threshold=confirmation_threshold,
            max_retries=max_retries,
            dlq_path=dlq_path,
        )
    return _processor_instance
