/**
 * Pipeline Dashboard composable — manages pipeline execution state.
 *
 * Subscribes to graph.* events from the WebSocket EventBus and maintains
 * reactive state for the Pipeline panel UI.
 *
 * Usage in Vue app:
 *   import { usePipeline } from './pipeline.js';
 *   const pipeline = usePipeline(bus, sendCommand);
 */

const { ref, computed } = Vue;

/**
 * @param {EventBus} bus - Client-side EventBus instance
 * @param {function} sendCommand - Function to send WS commands: (command, payload) => void
 * @returns {object} Reactive pipeline state and actions
 */
export function usePipeline(bus, sendCommand) {
    // --- Reactive State ---
    const status = ref('idle');       // 'idle' | 'running' | 'completed' | 'error' | 'cancelled'
    const runId = ref(null);
    const task = ref('');
    const nodes = ref([]);            // [{name, status, duration_ms, entered_at}]
    const totalDuration = ref(0);
    const error = ref(null);
    const history = ref([]);          // Past runs: [{runId, task, status, totalDuration, nodes, timestamp}]

    // --- Computed ---
    const completedCount = computed(() =>
        nodes.value.filter(n => n.status === 'completed').length
    );
    const totalNodes = computed(() => nodes.value.length);
    const currentNode = computed(() =>
        nodes.value.find(n => n.status === 'running') || null
    );

    // --- Known graph nodes in execution order ---
    const GRAPH_NODES = [
        'vetting', 'await_clarification', 'initialize',
        'context_aggregator', 'planner', 'blueprint_presentation',
        'blueprint_approval_gate', 'prd_decomposer', 'story_selector',
        'story_commit', 'story_progress', 'story_skip',
        'architect_coder', 'validator', 'ui_vision_check',
        'maestro_navigation_generator', 'vision_validation', 'push'
    ];

    // --- Event Handlers ---

    function onGraphStart(event) {
        const p = event.payload || event;
        status.value = 'running';
        runId.value = p.run_id;
        task.value = p.task || '';
        error.value = null;
        totalDuration.value = 0;

        // Initialize all known nodes as pending
        nodes.value = GRAPH_NODES.map(name => ({
            name,
            status: 'pending',
            duration_ms: 0,
            entered_at: null,
        }));
    }

    function onNodeEnter(event) {
        const p = event.payload || event;
        const node = nodes.value.find(n => n.name === p.node);
        if (node) {
            node.status = 'running';
            node.entered_at = Date.now();
        } else {
            // Unknown node — add dynamically
            nodes.value.push({
                name: p.node,
                status: 'running',
                duration_ms: 0,
                entered_at: Date.now(),
            });
        }
    }

    function onNodeExit(event) {
        const p = event.payload || event;
        const node = nodes.value.find(n => n.name === p.node);
        if (node) {
            node.status = p.status || 'completed';
            node.duration_ms = p.duration_ms || 0;
        }
    }

    function onGraphEnd(event) {
        const p = event.payload || event;
        if (p.cancelled) {
            status.value = 'cancelled';
        } else {
            status.value = 'completed';
        }
        totalDuration.value = p.total_duration_ms || 0;

        // Save to history
        history.value.unshift({
            runId: runId.value,
            task: task.value,
            status: status.value,
            totalDuration: totalDuration.value,
            nodeCount: completedCount.value,
            timestamp: Date.now(),
        });

        // Keep last 10 runs
        if (history.value.length > 10) {
            history.value = history.value.slice(0, 10);
        }
    }

    function onGraphError(event) {
        const p = event.payload || event;
        status.value = 'error';
        error.value = p.error;

        // Mark the errored node if specified
        if (p.node) {
            const node = nodes.value.find(n => n.name === p.node);
            if (node) {
                node.status = 'error';
            }
        }
    }

    function onGateRequest(event) {
        const payload = event.payload || event;
        const nodeName = payload.node;
        const node = nodes.value.find((n) => n.name === nodeName);
        if (node) {
            node.status = 'gated';
            node.gateId = payload.gate_id;
        }
        status.value = 'gated';
    }

    function onGateResponse(event) {
        const payload = event.payload || event;
        const gateId = payload.gate_id;
        const node = nodes.value.find((n) => n.gateId === gateId);
        if (node) {
            // Return to running — the graph will resume and node_exit will set final status
            node.status = 'running';
            delete node.gateId;
        }
        status.value = 'running';
    }

    // --- Subscribe to events ---
    bus.on('graph.start', onGraphStart);
    bus.on('graph.node_enter', onNodeEnter);
    bus.on('graph.node_exit', onNodeExit);
    bus.on('graph.end', onGraphEnd);
    bus.on('graph.error', onGraphError);
    bus.on('gate.request', onGateRequest);
    bus.on('gate.response', onGateResponse);

    // --- Actions ---

    function startPipeline(text) {
        if (status.value === 'running') return;
        sendCommand('pipeline.start', { text });
    }

    function cancelPipeline() {
        if (status.value !== 'running') return;
        sendCommand('pipeline.cancel', {});
    }

    function reset() {
        status.value = 'idle';
        runId.value = null;
        task.value = '';
        nodes.value = [];
        totalDuration.value = 0;
        error.value = null;
    }

    return {
        // State
        status,
        runId,
        task,
        nodes,
        totalDuration,
        error,
        history,
        // Computed
        completedCount,
        totalNodes,
        currentNode,
        // Actions
        startPipeline,
        cancelPipeline,
        reset,
    };
}
