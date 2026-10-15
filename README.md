# Heartbeat：独立同步式 AI 自动唤醒

**原创：空气小狗老师** · [MIT License](LICENSE)

正常聊天仍连接你原有的模型接口；在前端额外挂一个心跳同步地址，服务器依据最近一次同步的活动对话，定时独立调用模型，决定主动发消息或保持安静。

**仓库现已包含可运行的独立公开版代码，不只是原理文档。** 它不是私人前端的完整导出，不含私人域名、IP、角色提示词、聊天、记忆或凭据。

## 与 Dylan Heartbeat 的区别

[Dylan Heartbeat](https://github.com/callie0313/dylan-heartbeat) 的公开架构使用 Gateway 接收并转发客户端聊天请求，同时维护时间线。本方案不接管普通聊天的 API 链路；前端向独立心跳接口主动同步快照，心跳进程另行调用模型。

同域 Nginx 路由只负责 HTTPS 接入，不等于把日常聊天变成经过心跳网关的转发请求。比较依据是对方公开 README，不是对其全部实现的审计。感谢对方项目对主动唤醒思路的启发；本仓库未复制其实现代码，第三方项目仍遵守各自许可证。

```text
普通聊天：前端 → 原有模型 API → 前端
心跳流程：前端 → /heartbeat-api/sync → 服务端当前快照
                                     ↓ 定时检查
                                  独立模型调用
                                  ├─ <SILENCE/> → 不推送
                                  └─ 消息 → 队列 + 可选 Bark
                                           ↓
                           前端 pull → 保存、按 ID 去重 → ack
```

## 文件

| 文件 | 用途 |
|---|---|
| `app.py` | 鉴权 API、当前上下文、SQLite 事务和投递队列 |
| `worker.py` | 空闲检查、OpenAI 兼容模型调用、可选 Bark 通知 |
| `frontend/heartbeat-client.js` | 可移植前端适配器，不包含你的聊天 UI |
| `examples/` | 可运行接入示例，Token 仅在页面内存中保存 |
| `.env.example` | 空白配置模板，不含可用密钥 |
| `deploy/` | Nginx 同域路由和 Linux systemd 示例 |
| `tests/` | 仅使用虚构数据和模拟网络的测试 |
| `docs/PRINCIPLES.md` | 私有原型原理背景，不是公开版接口契约 |

## 本地快速开始

需要 Python 3.10+。Node.js 仅用于前端逻辑测试，不是服务端依赖。生产部署建议 Linux。

```sh
git clone https://github.com/wuliu0012/heartbeat.git
cd heartbeat
python -m venv .venv
# Linux / macOS
. .venv/bin/activate
# Windows PowerShell 改用 .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

把 `.env.example` 复制为**新的** `.env`，不要覆盖已有配置。生成服务 Token：

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

将输出只填入自己的 `.env` 中的 `HEARTBEAT_TOKEN`。这是凭据，不要提交 Git、公开截图或发进聊天。

本地测试保留 `ALLOWED_ORIGIN=http://127.0.0.1:5051`。配置自己的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`；模型地址是包含 `/v1` 的 OpenAI 兼容 API 基址，不是完整 `/chat/completions` 地址。不要把占位地址当成真实服务。

```sh
# 终端一：只监听本机；开发服务器不要暴露到公网
python app.py
# 终端二：使用同一虚拟环境和项目目录
python worker.py
# 或仅检查一次：python worker.py --once
```

打开 `http://127.0.0.1:5051/demo`，输入刚才的服务 Token，添加一条**虚构用户消息**。不要改用 `localhost`，除非也修改了 Origin 配置。同步后会按空闲阈值检查，不会立即生成消息。

只测试网页队列时可留空 `BARK_KEY`；需要手机通知时，配置自己的 Bark 设备凭据和可选 `FRONTEND_URL`。模型调用可能收费，选择沉默也可能产生费用。

## 接入自己的前端

把 `frontend/heartbeat-client.js` 放到自己网站并以模块导入。网页与心跳 API 必须同域；`ALLOWED_ORIGIN` 必须与网页 scheme、host、port 完全一致。

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
    // 下面是宿主需要自己实现的函数，不是库自带函数：
    // 按 entry.id 去重，写入前再次确认当前窗口，持久化成功后才 resolve。
    await yourDurableMergeById(entries, isCurrent);
    return true;
  },
  onError: code => yourStatusDisplay(code)
});
heartbeat.start();
// 保存、编辑、切换选中版本、换窗后通知适配器：
heartbeat.notifyChanged();
// 用户发消息后可额外刷新互动时间：
heartbeat.touch();
```

完整可运行宿主在 `examples/demo.js`。它将虚构聊天存在自己的演示专用 localStorage 键里，不接触其他前端的存储键；Token 只保留在内存。`stop()` 只停止网页同步，不会停止服务器 worker；停用自动唤醒应停止 worker 进程或对应服务。

## 公开版与私有原型的差异

- 模型密钥不再从网页同步：由部署者在服务端环境变量中配置；API 只接收活动对话文字与可选系统提示词。
- 不依赖其他项目的 Token 或路径，使用独立的 `HEARTBEAT_TOKEN`。
- 使用 SQLite 事务更新状态和队列，替代原型的多个 JSON 文件。
- 内置适配器仅支持 **OpenAI 兼容 `chat/completions`**，不直接实现 Anthropic 原生 Messages API；其他协议需另写适配器。
- 不包含私人前端、人设、真实配置和生产备份，不能当成无差异升级覆盖私人站点。

## Linux 生产部署

不要使用 Flask 开发服务器承载公网服务。可使用：

```sh
.venv/bin/gunicorn --workers 1 --bind 127.0.0.1:5051 --timeout 30 'app:create_app()'
```

让 Nginx 在自己已有的 HTTPS 站点下代理 `/heartbeat-api/`，参考 `deploy/nginx.conf.example`。公开版路由**保留前缀**，不要误配成剥掉 `/heartbeat-api/` 的代理。

采用 systemd 前，先创建自己的低权限 `heartbeat` 用户，将公开版放到 `/opt/heartbeat`、建立虚拟环境，并预先创建该用户可写的 `/opt/heartbeat/data`。`.env` 仅限服务用户可读。按实际目录修改两个 service 文件，核对后再安装、启用；不要覆盖原有项目和服务。

真实前端自行提供静态文件。`/demo` 是接入测试页，不是正式聊天页面。不要将数据库、`.env` 或备份放入静态文件服务目录。

## 测试与隐私

在仓库根目录运行：

```sh
python -m unittest discover -s tests -v
node tests/test_client.mjs
python tools/privacy_scan.py
```

测试不需要真实 Key，不调用模型、不发通知、不读取 `.env`，全部使用虚构样本。GitHub Actions 只运行这些测试，不需要 Secrets。隐私扫描只检查明确的发布清单，不读取本机凭据。

运行时对话仍是私密数据：数据库和备份需要访问控制，不能因为代码公开而上传数据。客户端 Token 同样是凭据，建议只放受控页面内存中，并防范 XSS。

## 已知边界

- 单用户、单活动对话，不是多用户系统；不要多人共享同一个 Token。
- 服务端只知道最近成功同步的快照，网页关闭后仍按该快照检查。
- 上下文变化也会刷新空闲计时。默认白天阈值 60 分钟、夜间 180 分钟，检查周期分别为 10 分钟与 120 分钟。
- 只同步文字，不透传图片、原始音频或完整工具执行数据。
- 修订号依赖客户端时钟，多设备时钟偏差及多标签页争用尚需进一步设计。
- 生成后、入队前核对上下文；外部手机通知无法和本地数据库构成同一原子事务，极短换窗竞态及送达仍有边界。
- 通知失败保留网页队列，但无保证通知到达的持久重试机制；ACK 表示宿主已保存，不代表用户已读。
- 自动化测试使用模拟 HTTP；真实模型兼容性、Linux 服务安装、HTTPS 和手机通知需要部署者自行验收。

原创署名适用于本仓库方案说明与公开版实现，不把 HTTP、SQLite、Bark 等通用技术或第三方项目纳为独占原创。第三方依赖遵守各自许可证。转载及二次分发请保留“空气小狗老师”署名及 MIT 许可声明。
