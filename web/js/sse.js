export function streamEvents(handlers) {
  const es = new EventSource("/api/job/events");
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
  es.addEventListener("done", () => es.close());
  return es;
}