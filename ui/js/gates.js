/**
 * useGates composable — tracks pending HITL gate requests.
 *
 * Listens for gate.request events from the backend and provides
 * approve/reject actions that send gate.response commands via WebSocket.
 *
 * @param {EventBus} bus - Client-side event bus
 * @param {Function} sendCommand - Function to send WS commands
 * @returns {Object} Reactive gate state and actions
 */
export function useGates(bus, sendCommand) {
  const { ref, computed } = Vue;

  // ── Reactive State ──────────────────────────────────────────────
  const pendingGates = ref([]);

  // ── Computed ────────────────────────────────────────────────────
  const hasActiveGate = computed(() => pendingGates.value.length > 0);
  const currentGate = computed(() => pendingGates.value[0] || null);

  // ── Event Handlers ──────────────────────────────────────────────
  function onGateRequest(event) {
    const payload = event.payload || event;
    pendingGates.value.push({
      gate_id: payload.gate_id,
      run_id: payload.run_id,
      node: payload.node,
      title: payload.title,
      description: payload.description,
      context: payload.context || {},
      timestamp: payload.timestamp || Date.now() / 1000,
    });
  }

  function onGateResponse(event) {
    const payload = event.payload || event;
    const gateId = payload.gate_id;
    pendingGates.value = pendingGates.value.filter(
      (g) => g.gate_id !== gateId
    );
  }

  // ── Actions ─────────────────────────────────────────────────────
  function approveGate(gateId, feedback = '') {
    sendCommand('gate.response', {
      gate_id: gateId,
      approved: true,
      feedback,
    });
  }

  function rejectGate(gateId, feedback = '') {
    sendCommand('gate.response', {
      gate_id: gateId,
      approved: false,
      feedback,
    });
  }

  // ── Subscriptions ───────────────────────────────────────────────
  bus.on('gate.request', onGateRequest);
  bus.on('gate.response', onGateResponse);

  return {
    // State
    pendingGates,
    // Computed
    hasActiveGate,
    currentGate,
    // Actions
    approveGate,
    rejectGate,
  };
}
