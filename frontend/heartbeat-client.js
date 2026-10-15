/* ԭ��������С����ʦ. MIT. Independent sync adapter; no chat API proxy. */
export function createHeartbeat(options) {
  const base = (options.base || '/heartbeat-api').replace(/\/$/, '');
  if (!/^\/[A-Za-z0-9/_-]+$/.test(base) || base.startsWith('//')) throw new Error('Use a same-origin API path');
  let chain = Promise.resolve(), timer, retry, debounce, revision = 0, epoch = 0, failures = 0, running = false;
  const enqueue = fn => { const next = chain.catch(() => {}).then(fn); chain = next.catch(() => {}); return next; };
  const selected = m => {
    const value = options.selectedContent ? options.selectedContent(m) : Array.isArray(m.versions) ? m.versions[m.verIdx ?? m.versions.length - 1] : m.content;
    if (typeof value !== 'string') throw Object.assign(new Error('text_history_required'), {code: 'data'});
    return value;
  };
  function snapshot() {
    const w = options.getSnapshot();
    if (!w) return null;
    return {conversation_id: w.id, system_prompt: w.systemPrompt || '', history: w.history
      .filter(m => ['user', 'ai', 'assistant'].includes(m.role))
      .map(m => ({role: m.role, content: selected(m)}))};
  }
  async function request(path, body) {
    const token = options.getToken();
    if (!token) throw Object.assign(new Error('unauthorized'), {code: 'auth'});
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const headers = {'X-Heartbeat-Token': token};
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const response = await fetch(base + path, {method: body === undefined ? 'GET' : 'POST', headers,
        signal: controller.signal, cache: 'no-store', body: body === undefined ? undefined : JSON.stringify(body)});
      if (!response.ok) throw Object.assign(new Error('heartbeat_request_failed'), {
        code: response.status === 409 ? 'stale' : response.status === 401 ? 'auth' : response.status === 403 ? 'origin' : response.status === 429 || response.status >= 500 ? 'network' : 'data'});
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  function report(error) {
    if (error.code === 'stale') return;
    if (['auth', 'origin', 'data', 'storage'].includes(error.code)) { options.onError?.(error.code); return; }
    failures++;
    if (running && failures < 3 && !retry) retry = setTimeout(() => { retry = null; poll(); }, 2000 * 2 ** (failures - 1));
    if (failures === 3) options.onError?.('network');
  }
  async function run(pull, touch = false) {
    if (document.hidden) return false;
    let body;
    try { body = snapshot(); } catch (e) { report(e); return false; }
    if (!body) return false;
    const ticket = epoch;
    return enqueue(async () => {
      const current = () => ticket === epoch && !document.hidden && options.getSnapshot()?.id === body.conversation_id;
      if (!current()) return false;
      try {
        revision = Math.max(Date.now() * 1000, revision + 1);
        const state = await request('/sync', {...body, revision});
        if (!current()) return false;
        const scope = {conversation_id: body.conversation_id, generation: state.generation};
        if (touch) await request('/touch', scope);
        if (pull) {
          const result = await request('/pull?' + new URLSearchParams(scope));
          if (!current() || result.conversation_id !== scope.conversation_id || result.generation !== scope.generation) return false;
          const entries = result.entries.filter(e => e.conversation_id === scope.conversation_id && e.generation === scope.generation);
          if (entries.length) {
            // Host MUST persist by ID before resolving, rechecking isCurrent before mutation.
            const saved = await options.onEntries(entries, current);
            if (saved === false) throw Object.assign(new Error('not_saved'), {code: 'storage'});
            if (!current()) return false;
            await request('/ack', {...scope, ids: entries.map(e => e.id)});
          }
        }
        failures = 0; clearTimeout(retry); retry = null;
        options.onStatus?.('connected');
        return true;
      } catch (e) { if (current()) report(e); return false; }
    });
  }
  const poll = () => run(true);
  const resume = () => { if (running && !document.hidden) { failures = 0; poll(); } };
  function notifyChanged() {
    epoch++; clearTimeout(debounce);
    if (running) debounce = setTimeout(poll, 300);
  }
  return {
    sync: () => run(false), poll, touch: () => run(false, true), notifyChanged,
    start() { if (running) return; running = true; document.addEventListener('visibilitychange', resume); window.addEventListener('online', resume); timer = setInterval(poll, 30000); poll(); },
    stop() { running = false; epoch++; clearInterval(timer); clearTimeout(retry); clearTimeout(debounce); retry = null; document.removeEventListener('visibilitychange', resume); window.removeEventListener('online', resume); }
  };
}
