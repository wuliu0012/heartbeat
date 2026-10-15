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
  getSnapshot: () => ({id: active, history: history(), systemPrompt: '�������û�����Ϣʱ�䡣'}),
  onStatus: () => { $('status').textContent = 'ͬ���ɹ�'; },
  onError: code => { $('status').textContent = ({auth: 'δ��Ȩ������ Token', origin: '��Դ�������������� Origin', data: '���ݲ�������', storage: '���ر���ʧ�ܣ�δȷ��ȡ����Ϣ', network: '�����ݲ����ã��Ժ��Զ�����'})[code] || '����ʧ��'; },
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
$('disconnect').onclick = () => { heartbeat.stop(); token = ''; $('status').textContent = '��ֹͣ�����ͬ�����������Կ��ܰ������ջ���'; };
$('switch').onclick = () => { if (!/^[A-Za-z0-9_-]{1,128}$/.test($('chat').value)) return; active = $('chat').value; heartbeat.notifyChanged(); render(); };
$('send').onclick = () => { if (!$('message').value.trim()) return; const next = history().concat({role: 'user', content: $('message').value}); try { localStorage.setItem(key, JSON.stringify({...windows, [active]: next})); } catch (_) { $('status').textContent = '�洢ʧ�ܣ�δ�޸ļ�¼'; return; } windows[active] = next; $('message').value = ''; heartbeat.notifyChanged(); heartbeat.touch(); render(); };
render();
