# Event Processor Module

A production-grade asynchronous event processor for handling blockchain transaction events with confirmation counting, trade state management, and robust error handling.

## Features

### ✅ Core Capabilities

- **Async Task Queue**: Non-blocking event processing with asyncio
- **Confirmation Counting**: Configurable threshold for trade confirmation (default: 3 confirmations)
- **Trade State Management**: Automatic state transitions (pending → confirmed → completed)
- **Dead Letter Queue (DLQ)**: Failed events are captured for later retry
- **Retry Mechanism**: Exponential backoff with configurable max attempts (default: 5)
- **Error Logging**: Comprehensive logging with event IDs for debugging
- **Singleton Pattern**: Global event processor instance for easy access

## Installation

### Requirements

```bash
pip install tenacity>=8.0.0
```

The `tenacity` library is already included in `requirements.txt`.

## Quick Start

### Basic Usage

```python
import asyncio
from datetime import datetime
from webhooks.event_processor import Event, get_event_processor

async def main():
    # Get the event processor instance
    processor = get_event_processor(
        bot_data_path="bot_data.json",
        confirmation_threshold=3,
        max_retries=5,
        dlq_path="dead_letter_queue.json",
    )

    # Start the processor as a background task
    processor_task = await processor.start()

    try:
        # Create and enqueue an event
        event = Event(
            event_id="evt_001",
            trade_id="trade_12345",
            tx_hash="0xabc123def456...",
            confirmation_count=1,
            timestamp=datetime.utcnow().isoformat(),
            event_type="confirmation",
            data={"block_number": 18000000, "gas_used": 21000},
        )

        await processor.enqueue_event(event)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check trade status
        trade = processor.get_trade_status("trade_12345")
        print(f"Trade status: {trade['status']}")
        # Output: Trade status: pending

    finally:
        processor.stop()
        await processor_task

if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### EventProcessor Class

#### Initialization

```python
processor = EventProcessor(
    bot_data_path: str = "bot_data.json",
    confirmation_threshold: int = 3,
    max_retries: int = 5,
    dlq_path: str = "dead_letter_queue.json",
)
```

**Parameters:**
- `bot_data_path`: Path to the bot_data.json file (created if doesn't exist)
- `confirmation_threshold`: Number of confirmations required for trade confirmation
- `max_retries`: Maximum number of retry attempts for failed events
- `dlq_path`: Path to the dead letter queue file

#### Methods

##### `async enqueue_event(event: Event) -> None`

Enqueue an event for processing.

```python
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
```

##### `async start() -> asyncio.Task`

Start the event processor as a background task.

```python
processor_task = await processor.start()
# ... do work ...
processor.stop()
await processor_task
```

##### `stop() -> None`

Stop the event processor.

```python
processor.stop()
```

##### `get_trade_status(trade_id: str) -> Optional[Dict[str, Any]]`

Get the current status of a trade.

```python
trade = processor.get_trade_status("trade_001")
if trade:
    print(f"Status: {trade['status']}")
    print(f"Confirmations: {trade['confirmations']}")
```

**Returns:**
```python
{
    "status": "pending|confirmed|completed|failed",
    "created_at": "2024-01-01T12:00:00",
    "confirmed_at": "2024-01-01T12:00:05",  # Only if confirmed
    "completed_at": "2024-01-01T12:00:10",  # Only if completed
    "confirmations": 3,
    "events": [
        {
            "event_id": "evt_001",
            "tx_hash": "0xabc123",
            "confirmation_count": 1,
            "timestamp": "2024-01-01T12:00:00",
            "event_type": "confirmation",
        },
        # ... more events ...
    ]
}
```

##### `get_dlq_events() -> List[Dict[str, Any]]`

Get all events in the dead letter queue.

```python
failed_events = processor.get_dlq_events()
for event in failed_events:
    print(f"Failed event: {event['event_id']}")
    print(f"Error: {event['error_message']}")
    print(f"Retries: {event['retry_count']}")
```

##### `retry_dlq_event(event_id: str) -> bool`

Retry a failed event from the dead letter queue.

```python
success = processor.retry_dlq_event("evt_001")
if success:
    print("Event requeued for processing")
else:
    print("Event not found in DLQ")
```

##### `async wait_until_processed(event_id: str, timeout: float = 30.0) -> bool`

Wait for a specific event to be processed.

```python
processed = await processor.wait_until_processed("evt_001", timeout=30.0)
if processed:
    print("Event was processed")
else:
    print("Timeout waiting for event")
```

##### `get_queue_size() -> int`

Get the current size of the event queue.

```python
size = processor.get_queue_size()
print(f"Events in queue: {size}")
```

##### `get_processed_count() -> int`

Get the number of processed events.

```python
count = processor.get_processed_count()
print(f"Processed events: {count}")
```

### Event Class

Data structure for events.

```python
@dataclass
class Event:
    event_id: str                    # Unique event identifier
    trade_id: str                    # Associated trade ID
    tx_hash: str                     # Transaction hash
    confirmation_count: int          # Current confirmation count
    timestamp: str                   # ISO format timestamp
    event_type: str                  # Type of event (e.g., "confirmation", "final_confirmation")
    data: Dict[str, Any]            # Additional event data
    retry_count: int = 0            # Number of retries (auto-managed)
```

### TradeStatus Enum

```python
class TradeStatus(str, Enum):
    PENDING = "pending"              # Trade created, awaiting confirmations
    CONFIRMED = "confirmed"          # Confirmation threshold reached
    COMPLETED = "completed"          # Trade finalized
    FAILED = "failed"                # Trade processing failed
```

### DeadLetterEvent Class

Data structure for failed events in the DLQ.

```python
@dataclass
class DeadLetterEvent:
    event_id: str                    # Event ID
    trade_id: str                    # Trade ID
    error_message: str               # Error that caused failure
    timestamp: str                   # When it failed
    retry_count: int                 # Number of retry attempts
    original_event: Dict[str, Any]  # Original event data
```

### Singleton Helper

```python
def get_event_processor(
    bot_data_path: str = "bot_data.json",
    confirmation_threshold: int = 3,
    max_retries: int = 5,
    dlq_path: str = "dead_letter_queue.json",
) -> EventProcessor:
    """Get or create the event processor singleton."""
```

## Trade State Transitions

```
┌─────────┐
│ PENDING │  (0 to threshold-1 confirmations)
└────┬────┘
     │ (confirmation_count >= threshold)
     ▼
┌───────────┐
│ CONFIRMED │  (threshold confirmations reached)
└────┬──────┘
     │ (final_confirmation event)
     ▼
┌───────────┐
│ COMPLETED │  (trade finalized)
└───────────┘
```

## Retry Mechanism

The event processor uses exponential backoff for retries:

- **Max Attempts**: 5 (configurable)
- **Backoff Strategy**: Exponential with multiplier=1, min=2s, max=10s
- **Retry Condition**: Retries on any Exception
- **Failed Events**: Moved to dead letter queue after all retries exhausted

### Backoff Schedule

| Attempt | Wait Time |
|---------|-----------|
| 1       | 2s        |
| 2       | 4s        |
| 3       | 8s        |
| 4       | 10s       |
| 5       | 10s       |

## File Formats

### bot_data.json

```json
{
  "trades": {
    "trade_001": {
      "status": "confirmed",
      "created_at": "2024-01-01T12:00:00",
      "confirmed_at": "2024-01-01T12:00:05",
      "confirmations": 3,
      "events": [
        {
          "event_id": "evt_001",
          "tx_hash": "0xabc123",
          "confirmation_count": 1,
          "timestamp": "2024-01-01T12:00:00",
          "event_type": "confirmation"
        }
      ]
    }
  },
  "metadata": {
    "version": "1.0",
    "created_at": "2024-01-01T00:00:00",
    "last_updated": "2024-01-01T12:00:05"
  }
}
```

### dead_letter_queue.json

```json
{
  "failed_events": [
    {
      "event_id": "evt_fail_001",
      "trade_id": "trade_fail_001",
      "error_message": "Connection timeout",
      "timestamp": "2024-01-01T12:00:10",
      "retry_count": 5,
      "original_event": {
        "event_id": "evt_fail_001",
        "trade_id": "trade_fail_001",
        "tx_hash": "0xfail...",
        "confirmation_count": 1,
        "timestamp": "2024-01-01T12:00:00",
        "event_type": "confirmation",
        "data": {}
      }
    }
  ],
  "metadata": {
    "version": "1.0",
    "created_at": "2024-01-01T00:00:00",
    "last_updated": "2024-01-01T12:00:10"
  }
}
```

## Logging

The event processor logs all operations with event IDs for easy debugging:

```
2024-01-01 12:00:00 - webhooks.event_processor - INFO - Event enqueued: evt_001 (trade: trade_001)
2024-01-01 12:00:00 - webhooks.event_processor - INFO - Processing event: evt_001 (trade: trade_001, confirmations: 1)
2024-01-01 12:00:01 - webhooks.event_processor - INFO - Trade trade_001 confirmed (1/3 confirmations)
2024-01-01 12:00:02 - webhooks.event_processor - INFO - Event processor started
```

### Log Levels

- **INFO**: Event enqueued, processing started, state transitions
- **WARNING**: Events added to DLQ, timeouts
- **ERROR**: Processing failures, file I/O errors

## Advanced Usage

### Custom Confirmation Threshold

```python
# Require 5 confirmations instead of default 3
processor = get_event_processor(confirmation_threshold=5)
```

### Handling Failed Events

```python
# Get all failed events
failed_events = processor.get_dlq_events()

# Retry a specific failed event
if failed_events:
    event_id = failed_events[0]["event_id"]
    processor.retry_dlq_event(event_id)
```

### Monitoring Queue Status

```python
# Check queue size
queue_size = processor.get_queue_size()
processed = processor.get_processed_count()

print(f"Queue: {queue_size} events pending")
print(f"Processed: {processed} events")
```

### Waiting for Event Processing

```python
# Enqueue event
await processor.enqueue_event(event)

# Wait for it to be processed (with timeout)
processed = await processor.wait_until_processed(
    event_id="evt_001",
    timeout=30.0
)

if processed:
    trade = processor.get_trade_status("trade_001")
    print(f"Trade status: {trade['status']}")
```

## Testing

Run the test suite:

```bash
pytest webhooks/test_event_processor.py -v
```

Run specific test:

```bash
pytest webhooks/test_event_processor.py::TestEventProcessor::test_confirmation_counting -v
```

## Examples

See `webhooks/example_usage.py` for complete working examples:

1. **Process Transaction Events**: Basic event processing with confirmation counting
2. **Handle Failed Events**: DLQ management and retry logic
3. **Multiple Trades**: Concurrent processing of multiple trades

Run examples:

```bash
python webhooks/example_usage.py
```

## Performance Considerations

- **Queue Processing**: Non-blocking async operations
- **File I/O**: Synchronous JSON read/write (consider async file I/O for high-volume scenarios)
- **Memory**: Processed events stored in memory (consider periodic cleanup for long-running processes)
- **Concurrency**: Single processor instance handles all events sequentially per queue

## Error Handling

The event processor handles errors gracefully:

1. **Processing Errors**: Logged and event moved to DLQ
2. **File I/O Errors**: Logged, operation skipped
3. **Retry Exhaustion**: Event moved to DLQ after max retries
4. **Unexpected Errors**: Caught and logged with event ID

## Security Considerations

- **Event Data**: No sensitive data should be stored in `data` field
- **File Permissions**: Ensure `bot_data.json` and `dead_letter_queue.json` have appropriate permissions
- **Logging**: Event IDs are logged; ensure logs are secured
- **Async Safety**: Thread-safe queue operations

## Troubleshooting

### Events Not Processing

1. Check if processor is started: `processor.processing`
2. Check queue size: `processor.get_queue_size()`
3. Check logs for errors
4. Verify `bot_data.json` is writable

### High DLQ Count

1. Check error messages in DLQ
2. Verify external dependencies (blockchain APIs, etc.)
3. Increase `max_retries` if transient failures
4. Manually retry events: `processor.retry_dlq_event(event_id)`

### Memory Usage

1. Monitor `processed_events` dictionary size
2. Consider periodic cleanup of old processed events
3. Archive old `bot_data.json` entries

## Contributing

When extending the event processor:

1. Add tests in `test_event_processor.py`
2. Update documentation
3. Follow existing code style
4. Ensure backward compatibility

## License

Part of the Law Discord Bot project.
