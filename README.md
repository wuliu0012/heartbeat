# Heartbeat������ͬ��ʽ AI �Զ�����

**ԭ��������С����ʦ** �� [MIT License](LICENSE)

����������������ԭ�е�ģ�ͽӿڣ���ǰ�˶����һ������ͬ����ַ���������������һ��ͬ���Ļ�Ի�����ʱ��������ģ�ͣ�������������Ϣ�򱣳ְ�����

**�ֿ����Ѱ��������еĶ�����������룬��ֻ��ԭ���ĵ���** ������˽��ǰ�˵���������������˽��������IP����ɫ��ʾ�ʡ����졢�����ƾ�ݡ�

## �� Dylan Heartbeat ������

[Dylan Heartbeat](https://github.com/callie0313/dylan-heartbeat) �Ĺ����ܹ�ʹ�� Gateway ���ղ�ת���ͻ�����������ͬʱά��ʱ���ߡ����������ӹ���ͨ����� API ��·��ǰ������������ӿ�����ͬ�����գ������������е���ģ�͡�

ͬ�� Nginx ·��ֻ���� HTTPS ���룬�����ڰ��ճ������ɾ����������ص�ת�����󡣱Ƚ������ǶԷ����� README�����Ƕ���ȫ��ʵ�ֵ���ơ���л�Է���Ŀ����������˼·�����������ֿ�δ������ʵ�ִ��룬��������Ŀ�����ظ�������֤��

```text
��ͨ���죺ǰ�� �� ԭ��ģ�� API �� ǰ��
�������̣�ǰ�� �� /heartbeat-api/sync �� ����˵�ǰ����
                                     �� ��ʱ���
                                  ����ģ�͵���
                                  ���� <SILENCE/> �� ������
                                  ���� ��Ϣ �� ���� + ��ѡ Bark
                                           ��
                           ǰ�� pull �� ���桢�� ID ȥ�� �� ack
```

## �ļ�

| �ļ� | ��; |
|---|---|
| `app.py` | ��Ȩ API����ǰ�����ġ�SQLite �����Ͷ�ݶ��� |
| `worker.py` | ���м�顢OpenAI ����ģ�͵��á���ѡ Bark ֪ͨ |
| `frontend/heartbeat-client.js` | ����ֲǰ����������������������� UI |
| `examples/` | �����н���ʾ����Token ����ҳ���ڴ��б��� |
| `.env.example` | �հ�����ģ�壬����������Կ |
| `deploy/` | Nginx ͬ��·�ɺ� Linux systemd ʾ�� |
| `tests/` | ��ʹ���鹹���ݺ�ģ������Ĳ��� |
| `docs/PRINCIPLES.md` | ˽��ԭ��ԭ�����������ǹ�����ӿ���Լ |

## ���ؿ��ٿ�ʼ

��Ҫ Python 3.10+��Node.js ������ǰ���߼����ԣ����Ƿ�������������������� Linux��

```sh
git clone https://github.com/wuliu0012/heartbeat.git
cd heartbeat
python -m venv .venv
# Linux / macOS
. .venv/bin/activate
# Windows PowerShell ���� .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

�� `.env.example` ����Ϊ**�µ�** `.env`����Ҫ�����������á����ɷ��� Token��

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

�����ֻ�����Լ��� `.env` �е� `HEARTBEAT_TOKEN`������ƾ�ݣ���Ҫ�ύ Git��������ͼ�򷢽����졣

���ز��Ա��� `ALLOWED_ORIGIN=http://127.0.0.1:5051`�������Լ��� `LLM_BASE_URL`��`LLM_API_KEY`��`LLM_MODEL`��ģ�͵�ַ�ǰ��� `/v1` �� OpenAI ���� API ��ַ���������� `/chat/completions` ��ַ����Ҫ��ռλ��ַ������ʵ����

```sh
# �ն�һ��ֻ����������������������Ҫ��¶������
python app.py
# �ն˶���ʹ��ͬһ���⻷������ĿĿ¼
python worker.py
# ������һ�Σ�python worker.py --once
```

�� `http://127.0.0.1:5051/demo`������ղŵķ��� Token������һ��**�鹹�û���Ϣ**����Ҫ���� `localhost`������Ҳ�޸��� Origin ���á�ͬ����ᰴ������ֵ��飬��������������Ϣ��

ֻ������ҳ����ʱ������ `BARK_KEY`����Ҫ�ֻ�֪ͨʱ�������Լ��� Bark �豸ƾ�ݺͿ�ѡ `FRONTEND_URL`��ģ�͵��ÿ����շѣ�ѡ���ĬҲ���ܲ������á�

## �����Լ���ǰ��

�� `frontend/heartbeat-client.js` �ŵ��Լ���վ����ģ�鵼�롣��ҳ������ API ����ͬ��`ALLOWED_ORIGIN` ��������ҳ scheme��host��port ��ȫһ�¡�

```js
import {createHeartbeat} from '/heartbeat-client.js';
const heartbeat = createHeartbeat({
  base: '/heartbeat-api',
  getToken: () => yourInMemoryHeartbeatToken,
  getSnapshot: () => ({
    id: yourActiveConversation.id,
    systemPrompt: yourSystemPrompt,
    history: yourActiveConversation.history
  }),
  selectedContent: message => yourSelectedMessageText(message),
  onEntries: async (entries, isCurrent) => {
    if (!isCurrent()) return false;
    // ������������Ҫ�Լ�ʵ�ֵĺ��������ǿ��Դ�������
    // �� entry.id ȥ�أ�д��ǰ�ٴ�ȷ�ϵ�ǰ���ڣ��־û��ɹ���� resolve��
    await yourDurableMergeById(entries, isCurrent);
    return true;
  },
  onError: code => yourStatusDisplay(code)
});
heartbeat.start();
// ���桢�༭���л�ѡ�а汾��������֪ͨ��������
heartbeat.notifyChanged();
// �û�����Ϣ��ɶ���ˢ�»���ʱ�䣺
heartbeat.touch();
```

���������������� `examples/demo.js`�������鹹��������Լ�����ʾר�� localStorage ������Ӵ�����ǰ�˵Ĵ洢����Token ֻ�������ڴ档`stop()` ֹֻͣ��ҳͬ��������ֹͣ������ worker��ͣ���Զ�����Ӧֹͣ worker ���̻��Ӧ����

## ��������˽��ԭ�͵Ĳ���

- ģ����Կ���ٴ���ҳͬ�����ɲ������ڷ���˻������������ã�API ֻ���ջ�Ի��������ѡϵͳ��ʾ�ʡ�
- ������������Ŀ�� Token ��·����ʹ�ö����� `HEARTBEAT_TOKEN`��
- ʹ�� SQLite �������״̬�Ͷ��У����ԭ�͵Ķ�� JSON �ļ���
- ������������֧�� **OpenAI ���� `chat/completions`**����ֱ��ʵ�� Anthropic ԭ�� Messages API������Э������д��������
- ������˽��ǰ�ˡ����衢��ʵ���ú��������ݣ����ܵ����޲�����������˽��վ�㡣

## Linux ��������

��Ҫʹ�� Flask �������������ع������񡣿�ʹ�ã�

```sh
.venv/bin/gunicorn --workers 1 --bind 127.0.0.1:5051 --timeout 30 'app:create_app()'
```

�� Nginx ���Լ����е� HTTPS վ���´��� `/heartbeat-api/`���ο� `deploy/nginx.conf.example`��������·��**����ǰ׺**����Ҫ����ɰ��� `/heartbeat-api/` �Ĵ�����

���� systemd ǰ���ȴ����Լ��ĵ�Ȩ�� `heartbeat` �û�����������ŵ� `/opt/heartbeat`���������⻷������Ԥ�ȴ������û���д�� `/opt/heartbeat/data`��`.env` ���޷����û��ɶ�����ʵ��Ŀ¼�޸����� service �ļ����˶Ժ��ٰ�װ�����ã���Ҫ����ԭ����Ŀ�ͷ���

��ʵǰ�������ṩ��̬�ļ���`/demo` �ǽ������ҳ��������ʽ����ҳ�档��Ҫ�����ݿ⡢`.env` �򱸷ݷ��뾲̬�ļ�����Ŀ¼��

## ��������˽

�ڲֿ��Ŀ¼���У�

```sh
python -m unittest discover -s tests -v
node tests/test_client.mjs
python tools/privacy_scan.py
```

���Բ���Ҫ��ʵ Key��������ģ�͡�����֪ͨ������ȡ `.env`��ȫ��ʹ���鹹������GitHub Actions ֻ������Щ���ԣ�����Ҫ Secrets����˽ɨ��ֻ�����ȷ�ķ����嵥������ȡ����ƾ�ݡ�

����ʱ�Ի�����˽�����ݣ����ݿ�ͱ�����Ҫ���ʿ��ƣ�������Ϊ���빫�����ϴ����ݡ��ͻ��� Token ͬ����ƾ�ݣ�����ֻ���ܿ�ҳ���ڴ��У������� XSS��

## ��֪�߽�

- ���û�������Ի������Ƕ��û�ϵͳ����Ҫ���˹���ͬһ�� Token��
- �����ֻ֪������ɹ�ͬ���Ŀ��գ���ҳ�رպ��԰��ÿ��ռ�顣
- �����ı仯Ҳ��ˢ�¿��м�ʱ��Ĭ�ϰ�����ֵ 60 ���ӡ�ҹ�� 180 ���ӣ�������ڷֱ�Ϊ 10 ������ 120 ���ӡ�
- ֻͬ�����֣���͸��ͼƬ��ԭʼ��Ƶ����������ִ�����ݡ�
- �޶��������ͻ���ʱ�ӣ����豸ʱ��ƫ����ǩҳ���������һ����ơ�
- ���ɺ����ǰ�˶������ģ��ⲿ�ֻ�֪ͨ�޷��ͱ������ݿ⹹��ͬһԭ�����񣬼��̻�����̬���ʹ����б߽硣
- ֪ͨʧ�ܱ�����ҳ���У����ޱ�֤֪ͨ����ĳ־����Ի��ƣ�ACK ��ʾ�����ѱ��棬�������û��Ѷ���
- �Զ�������ʹ��ģ�� HTTP����ʵģ�ͼ����ԡ�Linux ����װ��HTTPS ���ֻ�֪ͨ��Ҫ�������������ա�

ԭ�����������ڱ��ֿⷽ��˵���빫����ʵ�֣����� HTTP��SQLite��Bark ��ͨ�ü������������Ŀ��Ϊ��ռԭ�����������������ظ�������֤��ת�ؼ����ηַ��뱣��������С����ʦ�������� MIT ����������
