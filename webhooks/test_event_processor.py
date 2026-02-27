"""
Unit tests for the EventProcessor module.

Tests:
- Event enqueueing and processing
- Confirmation counting and threshold logic
- Trade state transitions (pending → confirmed → completed)
- Dead letter queue functionality
- Retry mechanism with exponential backoff
- Error logging with event IDs
"""

import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from webhooks.event_processor import (
    Event,
    EventProcessor,
    TradeStatus,
    DeadLetterEvent,
    get_event_processor,
)


@pytest.fixture
def temp_files(tmp_path):
    """Create temporary bot_data.json and dead_letter_queue.json files."""
    bot_data_path = tmp_path / "bot_data.json"
    dlq_path = tmp_path / "dead_letter_queue.json"
    return str(bot_data_path), str(dlq_path)


@pytest.fixture
def processor(temp_files):
    """Create an EventProcessor instance with temporary files."""
    bot_data_path, dlq_path = temp_files
    return EventProcessor(
        bot_data_path=bot_data_path,
        confirmation_threshold=3,
        max_retries=5,
        dlq_path=dlq_path,
    )


class TestEventProcessor:
    """Test suite for EventProcessor."""

    def test_initialization(self, processor):
        """Test processor initialization."""
        assert processor.confirmation_threshold == 3
        assert processor.max_retries == 5
        assert processor.processing is False
        assert processor.event_queue.qsize() == 0

    def test_files_created(self, processor, temp_files):
        """Test that bot_data.json and DLQ files are created."""
        bot_data_path, dlq_path = temp_files
        assert Path(bot_data_path).exists()
        assert Path(dlq_path).exists()

    def test_load_bot_data(self, processor):
        """Test loading bot_data.json."""
        data = processor._load_bot_data()
        assert "trades" in data
        assert isinstance(data["trades"], dict)

    def test_load_dlq(self, processor):
        """Test loading dead letter queue."""
        dlq = processor._load_dlq()
        assert "failed_events" in dlq
        assert isinstance(dlq["failed_events"], list)

    @pytest.mark.asyncio
    async def test_enqueue_event(self, processor):
        """Test enqueueing an event."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"block": 1000},
        )

        await processor.enqueue_event(event)
        assert processor.event_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_process_single_event(self, processor):
        """Test processing a single event."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"block": 1000},
        )

        await processor._process_event(event)

        # Check trade was created
        trade = processor.get_trade_status("trade_001")
        assert trade is not None
        assert trade["status"] == TradeStatus.PENDING.value
        assert trade["confirmations"] == 1
        assert len(trade["events"]) == 1

    @pytest.mark.asyncio
    async def test_confirmation_counting(self, processor):
        """Test confirmation counting and threshold logic."""
        trade_id = "trade_confirm"

        # Event 1: 1 confirmation
        event1 = Event(
            event_id="evt_001",
            trade_id=trade_id,
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await processor._process_event(event1)
        trade = processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.PENDING.value
        assert trade["confirmations"] == 1

        # Event 2: 2 confirmations
        event2 = Event(
            event_id="evt_002",
            trade_id=trade_id,
            tx_hash="0xabc123",
            confirmation_count=2,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await processor._process_event(event2)
        trade = processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.PENDING.value
        assert trade["confirmations"] == 2

        # Event 3: 3 confirmations (threshold reached)
        event3 = Event(
            event_id="evt_003",
            trade_id=trade_id,
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await processor._process_event(event3)
        trade = processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.CONFIRMED.value
        assert trade["confirmations"] == 3
        assert "confirmed_at" in trade

    @pytest.mark.asyncio
    async def test_trade_completion(self, processor):
        """Test trade completion with final_confirmation event."""
        trade_id = "trade_complete"

        # Process events up to confirmation threshold
        for i in range(1, 4):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id=trade_id,
                tx_hash="0xabc123",
                confirmation_count=i,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            await processor._process_event(event)

        trade = processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.CONFIRMED.value

        # Final confirmation event
        final_event = Event(
            event_id="evt_final",
            trade_id=trade_id,
            tx_hash="0xabc123",
            confirmation_count=4,
            timestamp=datetime.utcnow().isoformat(),
            event_type="final_confirmation",
            data={},
        )
        await processor._process_event(final_event)

        trade = processor.get_trade_status(trade_id)
        assert trade["status"] == TradeStatus.COMPLETED.value
        assert "completed_at" in trade

    @pytest.mark.asyncio
    async def test_event_history(self, processor):
        """Test that event history is maintained in trade."""
        trade_id = "trade_history"

        events = []
        for i in range(1, 4):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id=trade_id,
                tx_hash=f"0xabc{i}",
                confirmation_count=i,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={"index": i},
            )
            events.append(event)
            await processor._process_event(event)

        trade = processor.get_trade_status(trade_id)
        assert len(trade["events"]) == 3

        for i, event_record in enumerate(trade["events"], 1):
            assert event_record["event_id"] == f"evt_{i:03d}"
            assert event_record["confirmation_count"] == i

    @pytest.mark.asyncio
    async def test_dead_letter_queue(self, processor):
        """Test dead letter queue functionality."""
        event = Event(
            event_id="evt_dlq_001",
            trade_id="trade_dlq",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )

        error = Exception("Test error")
        await processor._handle_failed_event(event, error, 5)

        dlq_events = processor.get_dlq_events()
        assert len(dlq_events) == 1
        assert dlq_events[0]["event_id"] == "evt_dlq_001"
        assert dlq_events[0]["trade_id"] == "trade_dlq"
        assert dlq_events[0]["error_message"] == "Test error"
        assert dlq_events[0]["retry_count"] == 5

    @pytest.mark.asyncio
    async def test_retry_dlq_event(self, processor):
        """Test retrying a failed event from DLQ."""
        # Add event to DLQ
        event = Event(
            event_id="evt_retry_001",
            trade_id="trade_retry",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"test": True},
        )

        error = Exception("Test error")
        await processor._handle_failed_event(event, error, 3)

        # Verify it's in DLQ
        dlq_events = processor.get_dlq_events()
        assert len(dlq_events) == 1

        # Retry the event
        success = processor.retry_dlq_event("evt_retry_001")
        assert success is True

        # Verify it was removed from DLQ
        dlq_events = processor.get_dlq_events()
        assert len(dlq_events) == 0

        # Verify it was enqueued
        assert processor.event_queue.qsize() == 1

    def test_retry_nonexistent_dlq_event(self, processor):
        """Test retrying a non-existent DLQ event."""
        success = processor.retry_dlq_event("nonexistent_event")
        assert success is False

    @pytest.mark.asyncio
    async def test_queue_size(self, processor):
        """Test queue size tracking."""
        assert processor.get_queue_size() == 0

        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )

        await processor.enqueue_event(event)
        assert processor.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_processed_count(self, processor):
        """Test processed event count tracking."""
        assert processor.get_processed_count() == 0

        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )

        await processor._process_event(event)
        assert processor.get_processed_count() == 1

    @pytest.mark.asyncio
    async def test_multiple_trades(self, processor):
        """Test processing events for multiple trades."""
        trades = ["trade_A", "trade_B", "trade_C"]

        for trade_id in trades:
            for i in range(1, 4):
                event = Event(
                    event_id=f"{trade_id}_evt_{i}",
                    trade_id=trade_id,
                    tx_hash=f"0x{trade_id}_{i}",
                    confirmation_count=i,
                    timestamp=datetime.utcnow().isoformat(),
                    event_type="confirmation",
                    data={},
                )
                await processor._process_event(event)

        # Verify all trades
        for trade_id in trades:
            trade = processor.get_trade_status(trade_id)
            assert trade is not None
            assert trade["status"] == TradeStatus.CONFIRMED.value
            assert trade["confirmations"] == 3

    @pytest.mark.asyncio
    async def test_process_queue_background_task(self, processor):
        """Test processing queue as a background task."""
        # Start processor
        task = await processor.start()

        try:
            # Enqueue events
            for i in range(1, 4):
                event = Event(
                    event_id=f"evt_{i:03d}",
                    trade_id="trade_bg",
                    tx_hash="0xabc123",
                    confirmation_count=i,
                    timestamp=datetime.utcnow().isoformat(),
                    event_type="confirmation",
                    data={},
                )
                await processor.enqueue_event(event)

            # Wait for processing
            await asyncio.sleep(0.5)

            # Verify trade was processed
            trade = processor.get_trade_status("trade_bg")
            assert trade is not None
            assert trade["status"] == TradeStatus.CONFIRMED.value

        finally:
            processor.stop()
            await task

    @pytest.mark.asyncio
    async def test_wait_until_processed(self, processor):
        """Test waiting for event to be processed."""
        event = Event(
            event_id="evt_wait_001",
            trade_id="trade_wait",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )

        await processor._process_event(event)

        # Wait for event
        result = await processor.wait_until_processed("evt_wait_001", timeout=5.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_until_processed_timeout(self, processor):
        """Test timeout when waiting for non-existent event."""
        result = await processor.wait_until_processed("nonexistent_event", timeout=0.1)
        assert result is False

    def test_get_event_processor_singleton(self, temp_files):
        """Test that get_event_processor returns singleton."""
        bot_data_path, dlq_path = temp_files

        processor1 = get_event_processor(
            bot_data_path=bot_data_path,
            dlq_path=dlq_path,
        )
        processor2 = get_event_processor(
            bot_data_path=bot_data_path,
            dlq_path=dlq_path,
        )

        assert processor1 is processor2


class TestTradeStatusEnum:
    """Test TradeStatus enumeration."""

    def test_trade_status_values(self):
        """Test TradeStatus enum values."""
        assert TradeStatus.PENDING.value == "pending"
        assert TradeStatus.CONFIRMED.value == "confirmed"
        assert TradeStatus.COMPLETED.value == "completed"
        assert TradeStatus.FAILED.value == "failed"


class TestEventDataStructure:
    """Test Event data structure."""

    def test_event_creation(self):
        """Test creating an Event."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"key": "value"},
        )

        assert event.event_id == "evt_001"
        assert event.trade_id == "trade_001"
        assert event.tx_hash == "0xabc123"
        assert event.confirmation_count == 1
        assert event.event_type == "confirmation"
        assert event.data == {"key": "value"}
        assert event.retry_count == 0

    def test_event_with_retry_count(self):
        """Test Event with retry count."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
            retry_count=3,
        )

        assert event.retry_count == 3


class TestDeadLetterEventDataStructure:
    """Test DeadLetterEvent data structure."""

    def test_dead_letter_event_creation(self):
        """Test creating a DeadLetterEvent."""
        original_event = {
            "event_id": "evt_001",
            "trade_id": "trade_001",
            "tx_hash": "0xabc123",
            "confirmation_count": 1,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "confirmation",
            "data": {},
        }

        dlq_event = DeadLetterEvent(
            event_id="evt_001",
            trade_id="trade_001",
            error_message="Test error",
            timestamp=datetime.utcnow().isoformat(),
            retry_count=5,
            original_event=original_event,
        )

        assert dlq_event.event_id == "evt_001"
        assert dlq_event.trade_id == "trade_001"
        assert dlq_event.error_message == "Test error"
        assert dlq_event.retry_count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
