/**
 * Lios Agent — Main Application
 *
 * Vue 3 app with EventBus-driven WebSocket communication.
 * Handles the Activity Bar, Sidebar, and Chat panel.
 */
import { EventBus } from './event-bus.js';
import { usePipeline } from './pipeline.js';
import { useGates } from './gates.js';

const { createApp, ref, onMounted, nextTick, computed } = Vue;

// Shared client-side event bus
const bus = new EventBus();

createApp({
  setup() {
    // ------------------------------------------------------------------
    // Reactive state
    // ------------------------------------------------------------------
    const messages = ref([
      { role: 'assistant', text: 'Hello! I am Lios.' }
    ]);
    const inputText = ref('');
    const conversations = ref([]);
    const files = ref([]);
    const stats = ref({
      model: 'Unknown',
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
      cost: 0.0,
    });
    const activeTools = ref([]);
    const isThinking = ref(false);
    const activePanel = ref('chat');
    const sidebarCollapsed = ref(false);
    const wsConnected = ref(false);

    let ws = null;

    // ------------------------------------------------------------------
    // WebSocket connection
    // ------------------------------------------------------------------
    onMounted(() => {
      connectWebSocket();
    });

    function connectWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

      ws.onopen = () => {
        wsConnected.value = true;
      };

      ws.onclose = () => {
        wsConnected.value = false;
        // Auto-reconnect after 2s
        setTimeout(connectWebSocket, 2000);
      };

      ws.onerror = () => {
        wsConnected.value = false;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'event') {
            // New event protocol — dispatch through client bus
            bus.dispatch(data);
          } else if (data.type === 'chunk') {
            // Legacy protocol support
            bus.dispatch({
              type: 'event',
              event_type: 'chat.chunk',
              payload: { text: data.text },
              timestamp: Date.now() / 1000,
              correlation_id: 'legacy',
            });
          } else if (data.type === 'stats') {
            // Legacy stats
            bus.dispatch({
              type: 'event',
              event_type: 'system.stats_update',
              payload: {
                model: data.model,
                input_tokens: data.input_tokens,
                output_tokens: data.output_tokens,
                total_tokens: data.total_tokens,
                cost: data.cost,
              },
              timestamp: Date.now() / 1000,
              correlation_id: 'legacy',
            });
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message', err);
        }
      };
    }

    // ------------------------------------------------------------------
    // EventBus subscriptions
    // ------------------------------------------------------------------
    bus.on('chat.chunk', (event) => {
      const payload = event.payload;
      isThinking.value = false;
      const lastMsg = messages.value[messages.value.length - 1];
      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.streaming) {
        lastMsg.text += payload.text;
      } else {
        messages.value.push({ role: 'assistant', text: payload.text, streaming: true });
      }
      scrollToBottom();
    });

    bus.on('chat.done', () => {
      isThinking.value = false;
      // Mark last message as no longer streaming
      const lastMsg = messages.value[messages.value.length - 1];
      if (lastMsg) lastMsg.streaming = false;
    });

    bus.on('chat.error', (event) => {
      isThinking.value = false;
      messages.value.push({
        role: 'assistant',
        text: `Error: ${event.payload.error || 'Unknown error'}`,
        streaming: false,
      });
      scrollToBottom();
    });

    bus.on('system.stats_update', (event) => {
      const p = event.payload;
      stats.value = {
        model: p.model || 'Unknown',
        inputTokens: p.input_tokens || 0,
        outputTokens: p.output_tokens || 0,
        totalTokens: p.total_tokens || 0,
        cost: p.cost || 0.0,
      };
    });

    // ------------------------------------------------------------------
    // Pipeline Dashboard
    // ------------------------------------------------------------------
    const pipelineInput = ref('');

    // sendCommand helper for pipeline composable
    function sendCommand(command, payload) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'command', command, payload }));
      }
    }

    const pipeline = usePipeline(bus, sendCommand);
    const gates = useGates(bus, sendCommand);

    // Format duration helper
    function formatDuration(ms) {
      if (!ms || ms <= 0) return '0s';
      if (ms < 1000) return Math.round(ms) + 'ms';
      if (ms < 60000) return (ms / 1000).toFixed(1) + 's';
      const mins = Math.floor(ms / 60000);
      const secs = ((ms % 60000) / 1000).toFixed(0);
      return mins + 'm ' + secs + 's';
    }

    // Get node bar width relative to longest node
    function getNodeBarWidth(node) {
      if (node.status === 'running') return '60%';
      const maxDuration = Math.max(...pipeline.nodes.value.map(n => n.duration_ms || 0), 1);
      const pct = Math.max(5, (node.duration_ms / maxDuration) * 100);
      return pct + '%';
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------
    const scrollToBottom = async () => {
      await nextTick();
      const terminalBody = document.querySelector('.terminal-body');
      if (terminalBody) {
        terminalBody.scrollTop = terminalBody.scrollHeight;
      }
    };

    const sendMessage = () => {
      if (!inputText.value.trim() || !ws || ws.readyState !== WebSocket.OPEN) return;

      messages.value.push({ role: 'user', text: inputText.value });

      // Send using new command protocol
      ws.send(JSON.stringify({
        type: 'command',
        command: 'chat.send',
        payload: { text: inputText.value },
      }));

      inputText.value = '';
      isThinking.value = true;
      scrollToBottom();
    };

    const setActivePanel = (panel) => {
      activePanel.value = panel;
    };

    const toggleSidebar = () => {
      sidebarCollapsed.value = !sidebarCollapsed.value;
    };

    // ------------------------------------------------------------------
    // Expose to template
    // ------------------------------------------------------------------
    return {
      messages,
      inputText,
      sendMessage,
      conversations,
      files,
      stats,
      activeTools,
      isThinking,
      activePanel,
      sidebarCollapsed,
      wsConnected,
      setActivePanel,
      toggleSidebar,
      pipeline,
      gates,
      pipelineInput,
      formatDuration,
      getNodeBarWidth,
    };
  }
}).mount('#app');

// ------------------------------------------------------------------
// Global functions (for onclick handlers in HTML)
// ------------------------------------------------------------------
window.toggleSidebar = function () {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('collapsed');
};

window.toggleAccordion = function (trigger) {
  const expanded = trigger.getAttribute('aria-expanded') === 'true';
  const body = trigger.nextElementSibling;

  trigger.setAttribute('aria-expanded', !expanded);
  body.setAttribute('aria-hidden', expanded);

  if (expanded) {
    body.style.maxHeight = '0';
  } else {
    body.style.maxHeight = body.scrollHeight + 'px';
  }
};

// Keyboard shortcut: Ctrl+B to toggle sidebar
document.addEventListener('keydown', function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
    e.preventDefault();
    window.toggleSidebar();
  }
});

// Export bus for debugging / external use
window.__liosBus = bus;
