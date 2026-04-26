/**
 * useTools composable — tracks tool call state from tool.* and file.* events.
 *
 * Follows the same pattern as useGates(bus, sendCommand).
 * Tool events are server→client only, so no sendCommand usage.
 *
 * @param {EventBus} bus - Client-side event bus
 * @returns {Object} Reactive tool call state and helpers
 */
export function useTools(bus) {
  const { ref, computed } = Vue;

  // --- State ---
  /** @type {import('vue').Ref<Array<Object>>} All tool calls (active + completed) */
  const toolCalls = ref([]);

  /** @type {import('vue').Ref<Array<Object>>} File change events */
  const fileChanges = ref([]);

  // --- Computed ---
  const activeToolCalls = computed(() =>
    toolCalls.value.filter(tc => tc.status === 'running')
  );

  const hasActiveTools = computed(() => activeToolCalls.value.length > 0);

  const completedToolCalls = computed(() =>
    toolCalls.value.filter(tc => tc.status !== 'running')
  );

  const totalToolCalls = computed(() => toolCalls.value.length);

  // --- Event Handlers ---

  function onToolStart(event) {
    const payload = event.payload || event;
    toolCalls.value.push({
      tool_call_id: payload.tool_call_id,
      run_id: payload.run_id,
      tool_name: payload.tool_name,
      input_data: payload.input_data || {},
      node: payload.node || null,
      status: 'running',
      started_at: Date.now(),
      duration_ms: null,
      output_data: null,
      error: null,
      expanded: false,
    });
  }

  function onToolResult(event) {
    const payload = event.payload || event;
    const tc = toolCalls.value.find(
      t => t.tool_call_id === payload.tool_call_id
    );
    if (tc) {
      tc.status = 'success';
      tc.output_data = payload.output_data || {};
      tc.duration_ms = payload.duration_ms || (Date.now() - tc.started_at);
      tc.truncated = payload.truncated || false;
    }
  }

  function onToolError(event) {
    const payload = event.payload || event;
    const tc = toolCalls.value.find(
      t => t.tool_call_id === payload.tool_call_id
    );
    if (tc) {
      tc.status = 'error';
      tc.error = payload.error || 'Unknown error';
      tc.duration_ms = Date.now() - tc.started_at;
    }
  }

  function onFileRead(event) {
    const payload = event.payload || event;
    fileChanges.value.push({
      type: 'read',
      tool_call_id: payload.tool_call_id,
      run_id: payload.run_id,
      path: payload.path,
      lines: payload.lines || 0,
      preview: payload.preview || null,
      timestamp: Date.now(),
    });
  }

  function onFileWrite(event) {
    const payload = event.payload || event;
    fileChanges.value.push({
      type: 'write',
      tool_call_id: payload.tool_call_id,
      run_id: payload.run_id,
      path: payload.path,
      diff: payload.diff || '',
      lines_added: payload.lines_added || 0,
      lines_removed: payload.lines_removed || 0,
      is_new_file: payload.is_new_file || false,
      timestamp: Date.now(),
    });
  }

  // --- Actions ---

  function toggleToolCall(toolCallId) {
    const tc = toolCalls.value.find(t => t.tool_call_id === toolCallId);
    if (tc) {
      tc.expanded = !tc.expanded;
    }
  }

  function clearToolCalls() {
    toolCalls.value = [];
    fileChanges.value = [];
  }

  function getFileChangeForTool(toolCallId) {
    return fileChanges.value.find(fc => fc.tool_call_id === toolCallId) || null;
  }

  function formatToolDuration(ms) {
    if (ms === null || ms === undefined) return '...';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }

  function getToolIcon(toolName) {
    const icons = {
      'Write': '\u270F',
      'Edit': '\u270F',
      'Read': '\uD83D\uDCC4',
      'Bash': '\u25B6',
      'Glob': '\uD83D\uDD0D',
      'Grep': '\uD83D\uDD0D',
      'WebFetch': '\uD83C\uDF10',
    };
    return icons[toolName] || '\u2699';
  }

  function parseDiffLines(diff) {
    if (!diff) return [];
    return diff.split('\n').map((line, i) => {
      let type = 'context';
      if (line.startsWith('@@')) type = 'header';
      else if (line.startsWith('+')) type = 'added';
      else if (line.startsWith('-')) type = 'removed';
      return { number: i + 1, content: line, type };
    });
  }

  // --- Subscriptions ---
  bus.on('tool.start', onToolStart);
  bus.on('tool.result', onToolResult);
  bus.on('tool.error', onToolError);
  bus.on('file.read', onFileRead);
  bus.on('file.write', onFileWrite);

  return {
    // State
    toolCalls,
    fileChanges,
    // Computed
    activeToolCalls,
    hasActiveTools,
    completedToolCalls,
    totalToolCalls,
    // Actions
    toggleToolCall,
    clearToolCalls,
    getFileChangeForTool,
    formatToolDuration,
    getToolIcon,
    parseDiffLines,
  };
}
