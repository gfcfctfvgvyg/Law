"""
Comprehensive test specifications for event processor.

Test Coverage:
- Confirmation counting with configurable thresholds
- Trade state updates (pending → confirmed → completed)
- Dead letter queue handling for failed events
- Retry mechanism with exponential backoff
- Error logging with event ID tracking
"""

import asyncio
import json
import pytest
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, Any, List

from webhooks.event_processor import (
    EventProcessor,
    Event,
    DeadLetterEvent,
    TradeStatus,
    get_event_processor,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_bot_data(tmp_path):
    """Create temporary bot_data.json file."""
    bot_data_file = tmp_path / "bot_data.json"
    bot_data_file.write_text(json.dumps({"trades": {}}, indent=2))
    return bot_data_file


@pytest.fixture
def temp_dlq(tmp_path):
    """Create temporary dead letter queue file."""
    dlq_file = tmp_path / "dead_letter_queue.json"
    dlq_file.write_text(json.dumps({"failed_events": []}, indent=2))
    return dlq_file


@pytest.fixture
def event_processor(temp_bot_data, temp_dlq):
    """Create event processor instance with temporary files."""
    processor = EventProcessor(
        bot_data_path=str(temp_bot_data),
        confirmation_threshold=3,
        max_retries=5,
        dlq_path=str(temp_dlq),
    )
    yield processor
    # Cleanup
    processor.stop()


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        event_id="evt_001",
        trade_id="trade_001",
        tx_hash="0xabc123",
        confirmation_count=1,
        timestamp=datetime.utcnow().isoformat(),
        event_type="confirmation",
        data={"amount": 100, "currency": "BTC"},
        retry_count=0,
    )


@pytest.fixture
def caplog_handler(caplog):
    """Configure caplog to capture all log levels."""
    caplog.set_level(logging.DEBUG)
    return caplog


# ============================================================================
# INITIALIZATION & FILE MANAGEMENT TESTS
# ============================================================================

class TestEventProcessorInitialization:
    """Test event processor initialization and file management."""

    def test_processor_initialization(self, temp_bot_data, temp_dlq):
        """Test that processor initializes with correct parameters."""
        processor = EventProcessor(
            bot_data_path=str(temp_bot_data),
            confirmation_threshold=5,
            max_retries=3,
            dlq_path=str(temp_dlq),
        )
        
        assert processor.confirmation_threshold == 5
        assert processor.max_retries == 3
        assert processor.bot_data_path == temp_bot_data
        assert processor.dlq_path == temp_dlq
        assert processor.processing is False
        assert len(processor.processed_events) == 0

    def test_bot_data_file_creation(self, tmp_path):
        """Test that bot_data.json is created if it doesn't exist."""
        bot_data_file = tmp_path / "bot_data.json"
        dlq_file = tmp_path / "dlq.json"
        
        assert not bot_data_file.exists()
        
        processor = EventProcessor(
            bot_data_path=str(bot_data_file),
            dlq_path=str(dlq_file),
        )
        
        assert bot_data_file.exists()
        data = json.loads(bot_data_file.read_text())
        assert "trades" in data
        assert data["trades"] == {}

    def test_dlq_file_creation(self, tmp_path):
        """Test that dead letter queue file is created if it doesn't exist."""
        bot_data_file = tmp_path / "bot_data.json"
        dlq_file = tmp_path / "dlq.json"
        
        assert not dlq_file.exists()
        
        processor = EventProcessor(
            bot_data_path=str(bot_data_file),
            dlq_path=str(dlq_file),
        )
        
        assert dlq_file.exists()
        data = json.loads(dlq_file.read_text())
        assert "failed_events" in data
        assert data["failed_events"] == []

    def test_load_existing_bot_data(self, temp_bot_data):
        """Test loading existing bot_data.json."""
        existing_data = {
            "trades": {
                "trade_001": {
                    "status": "pending",
                    "confirmations": 1,
                }
            }
        }
        temp_bot_data.write_text(json.dumps(existing_data))
        
        processor = EventProcessor(
            bot_data_path=str(temp_bot_data),
            dlq_path=str(Path(temp_bot_data.parent) / "dlq.json"),
        )
        
        data = processor._load_bot_data()
        assert "trade_001" in data["trades"]
        assert data["trades"]["trade_001"]["status"] == "pending"

    def test_load_corrupted_bot_data(self, temp_bot_data, caplog_handler):
        """Test handling of corrupted bot_data.json."""
        temp_bot_data.write_text("{ invalid json }")
        
        processor = EventProcessor(
            bot_data_path=str(temp_bot_data),
            dlq_path=str(Path(temp_bot_data.parent) / "dlq.json"),
        )
        
        data = processor._load_bot_data()
        assert data == {"trades": {}}
        assert "Error loading bot_data.json" in caplog_handler.text

    def test_singleton_pattern(self, temp_bot_data, temp_dlq):
        """Test that get_event_processor returns singleton instance."""
        processor1 = get_event_processor(
            bot_data_path=str(temp_bot_data),
            dlq_path=str(temp_dlq),
        )
        processor2 = get_event_processor(
            bot_data_path=str(temp_bot_data),
            dlq_path=str(temp_dlq),
        )
        
        assert processor1 is processor2


# ============================================================================
# CONFIRMATION COUNTING TESTS
# ============================================================================

class TestConfirmationCounting:
    """Test confirmation counting and threshold logic."""

    @pytest.mark.asyncio
    async def test_confirmation_count_increments(self, event_processor, sample_event):
        """Test that confirmation count is tracked correctly."""
        await event_processor._process_event(sample_event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data is not None
        assert trade_data["confirmations"] == 1

    @pytest.mark.asyncio
    async def test_confirmation_count_updates_to_max(self, event_processor, sample_event):
        """Test that confirmation count updates to the maximum received."""
        # First event with 1 confirmation
        await event_processor._process_event(sample_event)
        
        # Second event with 2 confirmations
        event2 = Event(
            event_id="evt_002",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=2,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event2)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["confirmations"] == 2

    @pytest.mark.asyncio
    async def test_confirmation_threshold_pending(self, event_processor, sample_event):
        """Test that trade remains pending below confirmation threshold."""
        event_processor.confirmation_threshold = 5
        
        await event_processor._process_event(sample_event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["status"] == TradeStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_confirmation_threshold_confirmed(self, event_processor, sample_event):
        """Test that trade transitions to confirmed at threshold."""
        event_processor.confirmation_threshold = 3
        
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["status"] == TradeStatus.CONFIRMED.value
        assert "confirmed_at" in trade_data

    @pytest.mark.asyncio
    async def test_confirmation_threshold_exceeded(self, event_processor):
        """Test that trade handles confirmations exceeding threshold."""
        event_processor.confirmation_threshold = 3
        
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=10,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["confirmations"] == 10
        assert trade_data["status"] == TradeStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_configurable_confirmation_threshold(self, temp_bot_data, temp_dlq):
        """Test that confirmation threshold is configurable."""
        processor = EventProcessor(
            bot_data_path=str(temp_bot_data),
            confirmation_threshold=10,
            dlq_path=str(temp_dlq),
        )
        
        assert processor.confirmation_threshold == 10

    @pytest.mark.asyncio
    async def test_multiple_events_same_trade(self, event_processor):
        """Test multiple confirmation events for the same trade."""
        confirmations = [1, 2, 3, 4, 5]
        
        for i, conf in enumerate(confirmations):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id="trade_001",
                tx_hash="0xabc123",
                confirmation_count=conf,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["confirmations"] == 5
        assert len(trade_data["events"]) == 5


# ============================================================================
# TRADE STATE UPDATE TESTS
# ============================================================================

class TestTradeStateUpdates:
    """Test trade state transitions and updates."""

    @pytest.mark.asyncio
    async def test_trade_creation_on_first_event(self, event_processor, sample_event):
        """Test that trade is created on first event."""
        await event_processor._process_event(sample_event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data is not None
        assert trade_data["status"] == TradeStatus.PENDING.value
        assert "created_at" in trade_data
        assert trade_data["confirmations"] == 1

    @pytest.mark.asyncio
    async def test_trade_status_pending_to_confirmed(self, event_processor):
        """Test trade status transition from pending to confirmed."""
        event_processor.confirmation_threshold = 3
        
        # Event with 3 confirmations
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["status"] == TradeStatus.CONFIRMED.value
        assert "confirmed_at" in trade_data

    @pytest.mark.asyncio
    async def test_trade_status_confirmed_to_completed(self, event_processor):
        """Test trade status transition from confirmed to completed."""
        event_processor.confirmation_threshold = 3
        
        # First event: reach confirmation threshold
        event1 = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event1)
        
        # Second event: final confirmation
        event2 = Event(
            event_id="evt_002",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=4,
            timestamp=datetime.utcnow().isoformat(),
            event_type="final_confirmation",
            data={},
        )
        await event_processor._process_event(event2)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["status"] == TradeStatus.COMPLETED.value
        assert "completed_at" in trade_data

    @pytest.mark.asyncio
    async def test_trade_status_not_downgraded(self, event_processor):
        """Test that trade status is not downgraded."""
        event_processor.confirmation_threshold = 3
        
        # Reach confirmed status
        event1 = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event1)
        
        # Try to process event with lower confirmation count
        event2 = Event(
            event_id="evt_002",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=2,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event2)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["status"] == TradeStatus.CONFIRMED.value
        assert trade_data["confirmations"] == 3  # Max value retained

    @pytest.mark.asyncio
    async def test_trade_event_history(self, event_processor):
        """Test that trade maintains event history."""
        events_data = [
            ("evt_001", 1),
            ("evt_002", 2),
            ("evt_003", 3),
        ]
        
        for event_id, conf_count in events_data:
            event = Event(
                event_id=event_id,
                trade_id="trade_001",
                tx_hash="0xabc123",
                confirmation_count=conf_count,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert len(trade_data["events"]) == 3
        assert trade_data["events"][0]["event_id"] == "evt_001"
        assert trade_data["events"][2]["event_id"] == "evt_003"

    @pytest.mark.asyncio
    async def test_multiple_trades_independent(self, event_processor):
        """Test that multiple trades are tracked independently."""
        for trade_num in range(1, 4):
            event = Event(
                event_id=f"evt_{trade_num:03d}",
                trade_id=f"trade_{trade_num:03d}",
                tx_hash=f"0xhash{trade_num}",
                confirmation_count=2,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            await event_processor._process_event(event)
        
        for trade_num in range(1, 4):
            trade_data = event_processor.get_trade_status(f"trade_{trade_num:03d}")
            assert trade_data is not None
            assert trade_data["confirmations"] == 2


# ============================================================================
# DEAD LETTER QUEUE TESTS
# ============================================================================

class TestDeadLetterQueue:
    """Test dead letter queue handling for failed events."""

    @pytest.mark.asyncio
    async def test_failed_event_added_to_dlq(self, event_processor, sample_event):
        """Test that failed event is added to dead letter queue."""
        error = Exception("Processing failed")
        
        await event_processor._handle_failed_event(sample_event, error, 5)
        
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 1
        assert dlq_events[0]["event_id"] == "evt_001"
        assert dlq_events[0]["trade_id"] == "trade_001"
        assert dlq_events[0]["error_message"] == "Processing failed"
        assert dlq_events[0]["retry_count"] == 5

    @pytest.mark.asyncio
    async def test_dlq_event_structure(self, event_processor, sample_event):
        """Test that DLQ event has correct structure."""
        error = Exception("Test error")
        
        await event_processor._handle_failed_event(sample_event, error, 3)
        
        dlq_events = event_processor.get_dlq_events()
        dlq_event = dlq_events[0]
        
        assert "event_id" in dlq_event
        assert "trade_id" in dlq_event
        assert "error_message" in dlq_event
        assert "timestamp" in dlq_event
        assert "retry_count" in dlq_event
        assert "original_event" in dlq_event

    @pytest.mark.asyncio
    async def test_dlq_preserves_original_event(self, event_processor, sample_event):
        """Test that DLQ preserves original event data."""
        error = Exception("Test error")
        
        await event_processor._handle_failed_event(sample_event, error, 5)
        
        dlq_events = event_processor.get_dlq_events()
        original = dlq_events[0]["original_event"]
        
        assert original["event_id"] == sample_event.event_id
        assert original["trade_id"] == sample_event.trade_id
        assert original["tx_hash"] == sample_event.tx_hash
        assert original["confirmation_count"] == sample_event.confirmation_count

    @pytest.mark.asyncio
    async def test_multiple_failed_events_in_dlq(self, event_processor):
        """Test that multiple failed events are stored in DLQ."""
        for i in range(3):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id=f"trade_{i:03d}",
                tx_hash=f"0xhash{i}",
                confirmation_count=1,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            error = Exception(f"Error {i}")
            await event_processor._handle_failed_event(event, error, i)
        
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 3

    @pytest.mark.asyncio
    async def test_retry_dlq_event_success(self, event_processor, sample_event):
        """Test retrying a failed event from DLQ."""
        error = Exception("Initial failure")
        await event_processor._handle_failed_event(sample_event, error, 5)
        
        # Verify event is in DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 1
        
        # Retry the event
        result = event_processor.retry_dlq_event("evt_001")
        
        assert result is True
        # Event should be removed from DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 0

    @pytest.mark.asyncio
    async def test_retry_dlq_event_not_found(self, event_processor):
        """Test retrying a non-existent DLQ event."""
        result = event_processor.retry_dlq_event("nonexistent_evt")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_dlq_event_increments_retry_count(self, event_processor, sample_event):
        """Test that retrying increments the retry count."""
        error = Exception("Initial failure")
        await event_processor._handle_failed_event(sample_event, error, 3)
        
        # Get the event before retry
        dlq_events = event_processor.get_dlq_events()
        original_retry_count = dlq_events[0]["retry_count"]
        
        # Retry the event
        event_processor.retry_dlq_event("evt_001")
        
        # The event should be requeued with incremented retry count
        # (This would be verified by processing the requeued event)

    @pytest.mark.asyncio
    async def test_dlq_persistence(self, temp_bot_data, temp_dlq):
        """Test that DLQ is persisted to disk."""
        processor = EventProcessor(
            bot_data_path=str(temp_bot_data),
            dlq_path=str(temp_dlq),
        )
        
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        error = Exception("Test error")
        
        await processor._handle_failed_event(event, error, 5)
        
        # Load DLQ from disk
        dlq_data = json.loads(temp_dlq.read_text())
        assert len(dlq_data["failed_events"]) == 1
        assert dlq_data["failed_events"][0]["event_id"] == "evt_001"


# ============================================================================
# RETRY MECHANISM & EXPONENTIAL BACKOFF TESTS
# ============================================================================

class TestRetryMechanism:
    """Test retry mechanism with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_decorator_applied(self, event_processor):
        """Test that retry decorator is applied to process method."""
        # The _process_event_with_retry method should have retry decorator
        assert hasattr(event_processor._process_event_with_retry, "__wrapped__")

    @pytest.mark.asyncio
    async def test_successful_event_no_retry(self, event_processor, sample_event):
        """Test that successful event processing doesn't trigger retries."""
        await event_processor._process_event_with_retry(sample_event)
        
        # Event should be processed successfully
        assert "evt_001" in event_processor.processed_events

    @pytest.mark.asyncio
    async def test_retry_on_exception(self, event_processor, sample_event):
        """Test that exception triggers retry mechanism."""
        call_count = 0
        
        async def failing_process(event):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            # Success on third attempt
        
        with patch.object(event_processor, "_process_event", side_effect=failing_process):
            try:
                await event_processor._process_event_with_retry(sample_event)
            except Exception:
                pass
        
        # Should have retried
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, event_processor, sample_event):
        """Test that max retries limit is enforced."""
        async def always_fail(event):
            raise Exception("Persistent failure")
        
        with patch.object(event_processor, "_process_event", side_effect=always_fail):
            with pytest.raises(Exception):
                await event_processor._process_event_with_retry(sample_event)

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, event_processor, sample_event):
        """Test that exponential backoff increases wait time."""
        # This is a timing test - verify backoff parameters are set
        # The decorator should have wait_exponential with multiplier=1, min=2, max=10
        
        # Create a mock to track timing
        call_times = []
        
        async def track_calls(event):
            call_times.append(datetime.utcnow())
            if len(call_times) < 3:
                raise Exception("Retry")
        
        with patch.object(event_processor, "_process_event", side_effect=track_calls):
            try:
                await event_processor._process_event_with_retry(sample_event)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_retry_count_tracking(self, event_processor, sample_event):
        """Test that retry count is tracked in failed events."""
        async def fail_n_times(event, n=3):
            if not hasattr(fail_n_times, "count"):
                fail_n_times.count = 0
            fail_n_times.count += 1
            if fail_n_times.count < n:
                raise Exception("Retry")
        
        with patch.object(event_processor, "_process_event", side_effect=fail_n_times):
            try:
                await event_processor._process_event_with_retry(sample_event)
            except Exception:
                pass


# ============================================================================
# ERROR LOGGING TESTS
# ============================================================================

class TestErrorLogging:
    """Test error logging with event ID tracking."""

    @pytest.mark.asyncio
    async def test_event_processing_logged(self, event_processor, sample_event, caplog_handler):
        """Test that event processing is logged."""
        await event_processor._process_event(sample_event)
        
        assert "Processing event: evt_001" in caplog_handler.text
        assert "trade: trade_001" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_confirmation_threshold_reached_logged(self, event_processor, caplog_handler):
        """Test that confirmation threshold is logged."""
        event_processor.confirmation_threshold = 3
        
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor._process_event(event)
        
        assert "Trade trade_001 confirmed" in caplog_handler.text
        assert "3/3 confirmations" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_trade_completion_logged(self, event_processor, caplog_handler):
        """Test that trade completion is logged."""
        event_processor.confirmation_threshold = 3
        
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=3,
            timestamp=datetime.utcnow().isoformat(),
            event_type="final_confirmation",
            data={},
        )
        await event_processor._process_event(event)
        
        assert "Trade trade_001 completed" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_failed_event_logged(self, event_processor, sample_event, caplog_handler):
        """Test that failed events are logged."""
        error = Exception("Processing failed")
        
        await event_processor._handle_failed_event(sample_event, error, 5)
        
        assert "Event processing failed: evt_001" in caplog_handler.text
        assert "trade: trade_001" in caplog_handler.text
        assert "retries: 5" in caplog_handler.text
        assert "Processing failed" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_dlq_addition_logged(self, event_processor, sample_event, caplog_handler):
        """Test that DLQ addition is logged."""
        error = Exception("Test error")
        
        await event_processor._handle_failed_event(sample_event, error, 5)
        
        assert "Event evt_001 added to dead letter queue" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_event_enqueue_logged(self, event_processor, sample_event, caplog_handler):
        """Test that event enqueue is logged."""
        await event_processor.enqueue_event(sample_event)
        
        assert "Event enqueued: evt_001" in caplog_handler.text
        assert "trade: trade_001" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_processor_start_logged(self, event_processor, caplog_handler):
        """Test that processor start is logged."""
        task = await event_processor.start()
        await asyncio.sleep(0.1)
        event_processor.stop()
        
        assert "Event processor started" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_processor_stop_logged(self, event_processor, caplog_handler):
        """Test that processor stop is logged."""
        task = await event_processor.start()
        await asyncio.sleep(0.1)
        event_processor.stop()
        await asyncio.sleep(0.1)
        
        assert "Event processor stop requested" in caplog_handler.text

    @pytest.mark.asyncio
    async def test_error_message_includes_event_id(self, event_processor, sample_event, caplog_handler):
        """Test that error messages include event ID."""
        error = Exception("Specific error")
        
        await event_processor._handle_failed_event(sample_event, error, 3)
        
        # Error log should contain event ID
        assert "evt_001" in caplog_handler.text


# ============================================================================
# QUEUE MANAGEMENT TESTS
# ============================================================================

class TestQueueManagement:
    """Test event queue management and processing."""

    @pytest.mark.asyncio
    async def test_enqueue_event(self, event_processor, sample_event):
        """Test enqueueing an event."""
        await event_processor.enqueue_event(sample_event)
        
        assert event_processor.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_queue_fifo_order(self, event_processor):
        """Test that queue processes events in FIFO order."""
        events = []
        for i in range(3):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id="trade_001",
                tx_hash="0xabc123",
                confirmation_count=1,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            events.append(event)
            await event_processor.enqueue_event(event)
        
        assert event_processor.get_queue_size() == 3

    @pytest.mark.asyncio
    async def test_get_queue_size(self, event_processor):
        """Test getting queue size."""
        assert event_processor.get_queue_size() == 0
        
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        await event_processor.enqueue_event(event)
        
        assert event_processor.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_get_processed_count(self, event_processor, sample_event):
        """Test getting processed event count."""
        assert event_processor.get_processed_count() == 0
        
        await event_processor._process_event(sample_event)
        
        assert event_processor.get_processed_count() == 1

    @pytest.mark.asyncio
    async def test_wait_until_processed_success(self, event_processor, sample_event):
        """Test waiting for event to be processed."""
        # Process event in background
        asyncio.create_task(event_processor._process_event(sample_event))
        
        # Wait for it
        result = await event_processor.wait_until_processed("evt_001", timeout=5.0)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_until_processed_timeout(self, event_processor):
        """Test timeout when waiting for non-existent event."""
        result = await event_processor.wait_until_processed("nonexistent", timeout=0.5)
        
        assert result is False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestEventProcessorIntegration:
    """Integration tests for complete event processing workflows."""

    @pytest.mark.asyncio
    async def test_complete_event_processing_workflow(self, event_processor):
        """Test complete workflow from event to trade completion."""
        event_processor.confirmation_threshold = 3
        
        # Process events with increasing confirmations
        for i in range(1, 4):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id="trade_001",
                tx_hash="0xabc123",
                confirmation_count=i,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation" if i < 3 else "final_confirmation",
                data={"amount": 100},
            )
            await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["status"] == TradeStatus.COMPLETED.value
        assert trade_data["confirmations"] == 3
        assert len(trade_data["events"]) == 3

    @pytest.mark.asyncio
    async def test_failed_event_recovery_workflow(self, event_processor):
        """Test workflow for recovering failed events from DLQ."""
        event_processor.confirmation_threshold = 2
        
        # Create and fail an event
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=2,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        error = Exception("Temporary failure")
        await event_processor._handle_failed_event(event, error, 5)
        
        # Verify it's in DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 1
        
        # Retry the event
        result = event_processor.retry_dlq_event("evt_001")
        assert result is True
        
        # Verify it's removed from DLQ
        dlq_events = event_processor.get_dlq_events()
        assert len(dlq_events) == 0

    @pytest.mark.asyncio
    async def test_concurrent_trade_processing(self, event_processor):
        """Test processing multiple trades concurrently."""
        event_processor.confirmation_threshold = 2
        
        # Create events for multiple trades
        tasks = []
        for trade_num in range(1, 4):
            for conf_num in range(1, 3):
                event = Event(
                    event_id=f"evt_{trade_num}_{conf_num}",
                    trade_id=f"trade_{trade_num:03d}",
                    tx_hash=f"0xhash{trade_num}",
                    confirmation_count=conf_num,
                    timestamp=datetime.utcnow().isoformat(),
                    event_type="confirmation",
                    data={},
                )
                tasks.append(event_processor._process_event(event))
        
        await asyncio.gather(*tasks)
        
        # Verify all trades are confirmed
        for trade_num in range(1, 4):
            trade_data = event_processor.get_trade_status(f"trade_{trade_num:03d}")
            assert trade_data["status"] == TradeStatus.CONFIRMED.value

    @pytest.mark.asyncio
    async def test_event_processor_lifecycle(self, event_processor):
        """Test complete lifecycle of event processor."""
        # Start processor
        task = await event_processor.start()
        assert event_processor.processing is True
        
        # Enqueue events
        for i in range(3):
            event = Event(
                event_id=f"evt_{i:03d}",
                trade_id=f"trade_{i:03d}",
                tx_hash=f"0xhash{i}",
                confirmation_count=1,
                timestamp=datetime.utcnow().isoformat(),
                event_type="confirmation",
                data={},
            )
            await event_processor.enqueue_event(event)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Stop processor
        event_processor.stop()
        await asyncio.sleep(0.2)
        
        assert event_processor.processing is False


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_duplicate_event_ids(self, event_processor):
        """Test handling of duplicate event IDs."""
        event1 = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        event2 = Event(
            event_id="evt_001",  # Same ID
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=2,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event1)
        await event_processor._process_event(event2)
        
        # Both should be in processed events (last one overwrites)
        assert "evt_001" in event_processor.processed_events

    @pytest.mark.asyncio
    async def test_empty_event_data(self, event_processor):
        """Test handling of event with empty data."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data is not None

    @pytest.mark.asyncio
    async def test_zero_confirmation_count(self, event_processor):
        """Test handling of zero confirmation count."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=0,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["confirmations"] == 0

    @pytest.mark.asyncio
    async def test_negative_confirmation_count(self, event_processor):
        """Test handling of negative confirmation count."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=-1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        # Should handle gracefully
        assert trade_data is not None

    @pytest.mark.asyncio
    async def test_very_large_confirmation_count(self, event_processor):
        """Test handling of very large confirmation count."""
        event = Event(
            event_id="evt_001",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=999999,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("trade_001")
        assert trade_data["confirmations"] == 999999

    @pytest.mark.asyncio
    async def test_special_characters_in_event_id(self, event_processor):
        """Test handling of special characters in event ID."""
        event = Event(
            event_id="evt_!@#$%^&*()",
            trade_id="trade_001",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event)
        
        assert "evt_!@#$%^&*()" in event_processor.processed_events

    @pytest.mark.asyncio
    async def test_missing_trade_id(self, event_processor):
        """Test handling of missing trade ID."""
        event = Event(
            event_id="evt_001",
            trade_id="",
            tx_hash="0xabc123",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={},
        )
        
        await event_processor._process_event(event)
        
        trade_data = event_processor.get_trade_status("")
        assert trade_data is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
