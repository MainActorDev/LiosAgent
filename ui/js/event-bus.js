/**
 * Client-side EventBus — mirrors the backend EventBus API.
 *
 * Supports exact and wildcard (*) pattern matching.
 *
 * Usage:
 *   const bus = new EventBus();
 *   bus.on('chat.*', (event) => console.log(event));
 *   bus.emit('chat.chunk', { text: 'hi' });
 */
export class EventBus {
  constructor() {
    /** @type {Map<string, {pattern: string, callback: Function, once: boolean}>} */
    this._subs = new Map();
    this._nextId = 0;
  }

  /**
   * Subscribe to events matching `pattern`.
   * @param {string} pattern - Exact name or wildcard (e.g. "chat.*", "*")
   * @param {Function} callback - Receives the event object
   * @returns {string} Subscription ID
   */
  on(pattern, callback) {
    const id = String(++this._nextId);
    this._subs.set(id, { pattern, callback, once: false });
    return id;
  }

  /**
   * Subscribe once — auto-removes after first match.
   */
  once(pattern, callback) {
    const id = String(++this._nextId);
    this._subs.set(id, { pattern, callback, once: true });
    return id;
  }

  /**
   * Remove a subscription by ID.
   * @param {string} id
   * @returns {boolean}
   */
  off(id) {
    return this._subs.delete(id);
  }

  /**
   * Emit an event to all matching subscribers.
   * @param {string} type - Event type (e.g. "chat.chunk")
   * @param {object} payload
   * @param {string} [correlationId]
   */
  emit(type, payload = {}, correlationId = null) {
    const event = {
      type,
      payload,
      timestamp: Date.now() / 1000,
      correlation_id: correlationId || this._generateId(),
    };
    this._dispatch(event);
    return event;
  }

  /**
   * Dispatch a pre-formed event object (e.g. from WebSocket).
   * @param {object} event
   */
  dispatch(event) {
    this._dispatch(event);
  }

  /** @private */
  _dispatch(event) {
    const toRemove = [];
    for (const [id, sub] of this._subs) {
      if (this._matches(event.event_type || event.type, sub.pattern)) {
        sub.callback(event);
        if (sub.once) toRemove.push(id);
      }
    }
    for (const id of toRemove) {
      this._subs.delete(id);
    }
  }

  /**
   * Simple wildcard matching: "chat.*" matches "chat.chunk", "*" matches all.
   * @private
   */
  _matches(eventType, pattern) {
    if (pattern === '*') return true;
    if (!pattern.includes('*')) return eventType === pattern;
    // Convert glob to regex
    const re = new RegExp('^' + pattern.replace(/\./g, '\\.').replace(/\*/g, '.*') + '$');
    return re.test(eventType);
  }

  /** @private */
  _generateId() {
    return Math.random().toString(36).slice(2, 14);
  }

  get subscriberCount() {
    return this._subs.size;
  }
}
