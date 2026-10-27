/* Dispatch job event-stream messages to page handlers and manage terminal connections. */
/** Open job SSE updates and return the connection for caller-managed cleanup. */
export function streamEvents(handlers) {
  const es = new EventSource("/api/job/events");
  // Decode event envelopes and dispatch optional JSON payloads to matching handlers.
  es.onmessage = (e) => {
    let msg;
    try {
      msg = JSON.parse(e.data);
    } catch { return; }
    const fn = handlers[msg.event];
    if (fn) {
      let data = msg.data;
      try { data = JSON.parse(data); } catch {}
      fn(data);
    }
  };
  // Close terminal streams before notifying the page to refresh its final status.
  es.addEventListener("done", () => { es.close(); handlers.done?.(); });
  // Delegate connection failures to the caller’s recovery handler.
  es.onerror = () => handlers.error?.();
  return es;
}