"""Tests for PipelineRunner — handles pipeline.start/cancel commands."""
from agent.event_bus import EventBus
from agent.repl.pipeline_runner import PipelineRunner


class TestPipelineRunnerInit:
    """PipelineRunner initialization."""

    def test_init_subscribes_to_pipeline_commands(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        assert runner._bus is bus
        assert runner._running is False
        assert runner._current_run_id is None

    def test_start_subscribes_to_bus(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        # Verify subscriptions exist by emitting events
        # (they won't crash even if handler is no-op)
        bus.emit("pipeline.start", {"text": "test"})
        bus.emit("pipeline.cancel", {})


class TestPipelineRunnerStart:
    """pipeline.start command handling."""

    def test_start_emits_graph_start(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        received = []
        bus.on("graph.start", lambda e: received.append(e))

        bus.emit("pipeline.start", {"text": "Build a login screen"})

        assert len(received) == 1
        assert received[0].payload["task"] == "Build a login screen"
        assert received[0].payload["run_id"] is not None

    def test_start_sets_running_state(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()

        bus.emit("pipeline.start", {"text": "Test task"})

        assert runner._running is True
        assert runner._current_run_id is not None

    def test_start_while_running_emits_error(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        errors = []
        bus.on("pipeline.error", lambda e: errors.append(e))

        bus.emit("pipeline.start", {"text": "First"})
        bus.emit("pipeline.start", {"text": "Second"})

        assert len(errors) == 1
        assert "already running" in errors[0].payload["error"].lower()


class TestPipelineRunnerCancel:
    """pipeline.cancel command handling."""

    def test_cancel_when_running(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        cancelled = []
        bus.on("graph.end", lambda e: cancelled.append(e))

        bus.emit("pipeline.start", {"text": "Task"})
        bus.emit("pipeline.cancel", {})

        assert runner._running is False
        assert len(cancelled) == 1
        assert cancelled[0].payload.get("cancelled") is True

    def test_cancel_when_not_running(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        errors = []
        bus.on("pipeline.error", lambda e: errors.append(e))

        bus.emit("pipeline.cancel", {})

        assert len(errors) == 1
        assert "not running" in errors[0].payload["error"].lower()

    def test_stop_unsubscribes_from_bus(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        runner.stop()
        received = []
        bus.on("graph.start", lambda e: received.append(e))

        bus.emit("pipeline.start", {"text": "Should be ignored"})

        assert len(received) == 0
        assert runner._running is False
