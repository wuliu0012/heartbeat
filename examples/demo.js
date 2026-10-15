import {createHeartbeat} from '/heartbeat-client.js';
const $ = id => document.getElementById(id);
let token = '', active = $('chat').value;
const key = 'heartbeat_public_demo_history_v1';
let windows;
try { windows = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) { windows = {}; }
if (!windows || typeof windows !== 'object' || Array.isArray(windows)) windows = {};
const history = () => windows[active] ||= [];
function render() { $('history').replaceChildren(); for (const m of history()) { const li = document.createElement('li'); li.textContent = m.role + ': ' + m.content; $('history').appendChild(li); } }
const heartbeat = createHeartbeat({
  getToken: () => token,
  getSnapshot: () => ({id: active, history: history(), systemPrompt: '请尊重用户的休息时间。'}),
  onStatus: () => { $('status').textContent = '同步成功'; },
  onError: code => { $('status').textContent = ({auth: '未授权，请检查 Token', origin: '来源不符，请检查服务端 Origin', data: '数据不被接受', storage: '本地保存失败，未确认取走消息', network: '网络暂不可用，稍后自动重试'})[code] || '请求失败'; },
  onEntries: async (entries, isCurrent) => {
    if (!isCurrent()) return false;
    const old = history(), ids = new Set(old.map(m => m.heartbeatId));
    const next = old.concat(entries.filter(e => !ids.has(e.id)).map(e => ({role: 'ai', content: e.content, heartbeatId: e.id})));
    // Save first; if storage throws, the adapter will not ACK.
    localStorage.setItem(key, JSON.stringify({...windows, [active]: next}));
    windows[active] = next; render(); return true;
  }
});
$('connect').onclick = () => { token = $('token').value.trim(); $('token').value = ''; heartbeat.start(); heartbeat.poll(); };
$('disconnect').onclick = () => { heartbeat.stop(); token = ''; $('status').textContent = '已停止浏览器同步；服务器仍可能按最后快照唤醒'; };
$('switch').onclick = () => { if (!/^[A-Za-z0-9_-]{1,128}$/.test($('chat').value)) return; active = $('chat').value; heartbeat.notifyChanged(); render(); };
$('send').onclick = () => { if (!$('message').value.trim()) return; const next = history().concat({role: 'user', content: $('message').value}); try { localStorage.setItem(key, JSON.stringify({...windows, [active]: next})); } catch (_) { $('status').textContent = '存储失败，未修改记录'; return; } windows[active] = next; $('message').value = ''; heartbeat.notifyChanged(); heartbeat.touch(); render(); };
render();
