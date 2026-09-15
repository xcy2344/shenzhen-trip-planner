# 深圳深度游 AI 旅行规划平台

基于 **LangGraph 多节点编排** 的智能旅游规划服务，用自然语言生成个性化深圳行程，支持多轮修改、RAG 知识增强、预算硬约束与 SSE 流式输出。

## ✨ 核心功能

| 功能 | 说明 |
|---|---|
| 🤖 多节点编排 | LangGraph 15 节点工作流，支持条件分支、循环重试、兜底降级 |
| 💬 三种意图 | `plan` 新规划 / `modify` 多轮修改 / `chat` 闲聊 |
| 📚 RAG 增强 | 深圳旅游知识库 38 条，ChromaDB 向量 + 关键词混合检索 |
| 💰 预算硬约束 | 金额全部由代码计算，超预算自动重试、兜底降级 |
| 🗺️ 路线优化 | 高德 API 补经纬度 + 贪心就近排序 + 开放时间校验 |
| ⚡ SSE 流式输出 | 每个节点完成即推送进度，把 60s 的等待变成可见的过程 |
| 🔐 JWT 鉴权 | `/login` 换取 token，`/chat` 系列接口强制校验 |
| 🚦 滑动窗口限流 | Redis + Lua，IP 10 次/60s、会话 5 次/60s |
| ♻️ 用户级缓存 | 缓存 key 带 `user_id`，用户之间互相隔离 |
| 📊 可观测性 | AI 调用统计（token / 耗时 / 成功率）+ 全量审计日志 |

## 🏗️ 技术栈

| 分类 | 技术 |
|---|---|
| 后端 | Python 3.11 + FastAPI |
| Agent 编排 | LangGraph |
| 大模型 | 阿里云百炼 `qwen-plus`（DashScope） |
| RAG | ChromaDB + 百炼 Embedding |
| 存储 | MySQL（会话 / 调用 / 审计）+ Redis（缓存 / 限流） |
| 地图 | 高德地图 Web API |
| 鉴权 | PyJWT（HS256，24 小时有效期） |
| 前端 | 原生 HTML/CSS/JS 单文件，`fetch` + `ReadableStream` |

## 🔄 LangGraph 工作流

```
START
  ↓
load_session            # 加载历史会话
  ↓
parse_intent            # 意图识别
  ├── plan    → parse_request        # 解析天数 / 人数 / 预算
  ├── modify  → parse_modification   # 解析要改什么
  └── chat    → chat_reply ─────────→ END
                     ↓
              rag_retrieve           # 知识库混合检索
                     ↓
           enrich_coordinates        # 补经纬度
                     ↓
             search_hotels           # 酒店检索
                     ↓
            allocate_budget          # 预算分配（代码计算）
                     ↓
       ┌─── generate_plan ───┐
       └─── modify_plan ─────┘        # 超预算会重试最多 2 次
                     ↓
             validate_plan           # 校验（代码算钱）
                     ↓
         ┌── 不通过且重试 < 2 → 回到生成
         ├── 仍不通过 → auto_fix_plan # 兜底换最便宜的方案
         └── 通过
                     ↓
             optimize_route          # 就近排序 + 开放时间校验
                     ↓
            generate_answer          # 生成自然语言回答
                     ↓
                    END
```

节点与进度提示的对应关系见 `backend/app/api/routes.py` 中的 `NODE_PROGRESS`。

## 📁 项目结构

```
shenzhen-trip-planner/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py         # /login /chat /chat/stream /health + CORS
│   │   │   └── stats.py          # /stats/* 统计接口
│   │   ├── core/
│   │   │   ├── config.py         # 环境变量
│   │   │   ├── security.py       # JWT 签发 / 校验
│   │   │   ├── database.py       # SQLAlchemy 引擎与建表
│   │   │   ├── llm.py            # 百炼调用封装 + token 记录
│   │   │   ├── logging.py        # 日志
│   │   │   ├── redis_client.py   # Redis 连接
│   │   │   ├── redis_cache.py    # 缓存（plan 前缀，24h TTL）
│   │   │   ├── redis_rate_limiter.py  # 滑动窗口限流
│   │   │   └── session.py
│   │   ├── graph/
│   │   │   ├── builder.py        # 工作流组装
│   │   │   ├── nodes.py          # 15 个节点实现
│   │   │   └── state.py          # TripState 定义
│   │   ├── models/
│   │   │   ├── db_models.py      # sessions / messages / ai_calls / audit_logs
│   │   │   └── session_mysql.py  # 会话读写
│   │   ├── rag/
│   │   │   ├── knowledge.py      # 知识库（38 条）
│   │   │   ├── embedder.py       # 文本向量化
│   │   │   ├── store.py          # Chroma 索引
│   │   │   └── retriever.py      # 混合检索
│   │   └── tools/                # 天气 / 景点 / 美食 / 高德地图
│   ├── main.py                   # 服务入口
│   ├── requirements.txt
│   ├── test_*.py                 # 各模块联调脚本
│   └── .env                      # 环境变量（不入库）
└── frontend/
    └── index.html                # 单文件演示页面
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.11+
- MySQL 8.0+（需先建库 `shenzhen_trip`）
- Redis 6.0+
- 阿里云百炼 API Key、高德地图 API Key

### 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 3. 配置环境变量

在 `backend/.env` 中填写（该文件已在 `.gitignore` 中，不会入库）：

```env
# 百炼大模型
BAILIAN_API_KEY=sk-xxxxxxxx
BAILIAN_MODEL=qwen-plus

# 高德地图
AMAP_API_KEY=xxxxxxxx

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=shenzhen_trip

# JWT
JWT_SECRET_KEY=your-secret-key-here
```

### 4. 初始化数据库

```bash
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS shenzhen_trip DEFAULT CHARACTER SET utf8mb4"
cd backend
python -c "from app.core.database import init_db; init_db()"
```

### 5. 构建 RAG 索引

```bash
cd backend
python -c "from app.rag.store import build_index; build_index(force_rebuild=True)"
```

### 6. 启动服务

```bash
cd backend
python main.py
```

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## 📖 API 接口

### POST /login

用 `user_id` 换取 JWT（演示用，未做密码校验）。

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice"}'
```

```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

### POST /chat

同步对话接口，含鉴权 + 限流 + 缓存 + 审计全链路。

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"input": "帮我规划深圳2日游，2个人，预算2000"}'
```

```json
{
  "output": "你好呀～为你规划的2日游行程...",
  "intent": "plan",
  "plan": [ "..." ],
  "request": { "days": 2, "people": 2, "budget": 2000 },
  "version": 1,
  "cached": false
}
```

> `session_id` 为可选参数；不传时用 token 中的 `user_id` 作为会话标识。

### POST /chat/stream

SSE 流式接口，节点完成即推送进度。

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"input": "帮我规划深圳2日游，2个人，预算2000"}'
```

事件格式：

```
event: progress
data: 正在识别意图...

event: progress
data: 正在检索景点和美食...

event: result
data: {"output":"...","intent":"plan","plan":["..."],"cached":false}
```

| 事件 | 含义 |
|---|---|
| `progress` | 某个节点完成，`data` 为中文进度提示 |
| `result` | 全部完成，`data` 为完整 JSON（与 `/chat` 同结构） |
| `error` | 出错，`data` 为错误信息 |

鉴权失败与限流触发返回真实 HTTP 状态码（401 / 429），不是 SSE 事件。

### GET /stats/overview

AI 调用总览：调用次数、成功率、token 消耗、平均耗时。

### GET /stats/by-purpose

按用途（`parse_intent` / `generate_plan` / ...）统计调用量与 token。

### GET /stats/recent-calls?limit=20

最近 N 条 AI 调用记录。

### GET /health

健康检查。

## 🔐 鉴权说明

1. 调 `/login` 拿 `access_token`（HS256，24 小时过期）。
2. 调 `/chat`、`/chat/stream` 时带上请求头 `Authorization: Bearer <token>`。
3. 校验失败返回 `401`；限流触发返回 `429`。

```bash
# 1. 登录拿 token
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"user_id":"alice"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. 带 token 调用，正常返回行程
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"input":"你好"}'

# 3. 不带 token，应返回 401
curl -i -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"input":"你好"}'
```

## 🖥️ 前端演示页

`frontend/index.html` 是一个单文件页面（深色 + 蓝色主题），包含登录区、输入区、实时进度区、行程结果区，用 `fetch` + `ReadableStream` 手工解析 SSE —— 因为 `EventSource` 不支持 POST 和自定义请求头。

后端已开启 CORS（`allow_origins=["*"]`），可以直接用 `file://` 打开，也可以起一个本地静态服务器：

```bash
cd frontend
python -m http.server 5500 --bind 127.0.0.1
# 浏览器打开 http://127.0.0.1:5500/index.html
```

页面默认连 `http://127.0.0.1:8000`，换机器演示时可用 `index.html?api=http://你的IP:8000` 覆盖。

演示步骤：输入 `alice` 点「登录」→ 输入“帮我规划深圳2日游，2个人，预算2000”→ 点「开始规划」，进度会一条条刷新，最后显示完整行程。

> 首次规划约 60-90 秒（多节点串行调用大模型）；命中缓存后约 0.1 秒返回。

## ⚙️ 配置项

| 变量 | 说明 | 默认值 |
|---|---|---|
| `BAILIAN_API_KEY` | 百炼 API Key | — |
| `BAILIAN_MODEL` | 使用的模型 | `qwen-plus` |
| `AMAP_API_KEY` | 高德地图 Key | — |
| `MYSQL_HOST` / `MYSQL_PORT` | MySQL 地址 | `localhost` / `3306` |
| `MYSQL_USER` / `MYSQL_PASSWORD` | MySQL 账号 | `root` / — |
| `MYSQL_DATABASE` | 数据库名 | `shenzhen_trip` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | — |

## 🗄️ 数据库表

| 表 | 用途 |
|---|---|
| `sessions` | 会话当前的行程、请求参数、版本号 |
| `messages` | 对话历史（user / assistant） |
| `ai_calls` | 每次大模型调用：模型、用途、token、耗时、成功与否 |
| `audit_logs` | 审计日志：user_id、动作、输入输出、IP、UA、成功与否 |

## 🧪 测试脚本

`backend/` 下提供了各模块的联调脚本：

| 脚本 | 用途 |
|---|---|
| `test_llm.py` | 大模型连通性 |
| `test_graph.py` / `test_node.py` | LangGraph 工作流 |
| `test_modify.py` | 多轮修改意图 |
| `test_rag_build.py` / `test_rag_search.py` | RAG 索引与检索 |
| `test_map.py` / `test_amap.py` | 高德地图工具 |
| `test_rate_limit.py` | 限流 |
| `test_session.py` | 会话存储 |
| `test_tools.py` | 天气 / 景点 / 美食工具 |
| `test_key.py` | 环境变量校验 |

```bash
cd backend
python test_graph.py
```

## 🎯 设计要点

**预算硬约束**：金额从不让大模型算。`validate_plan` 用纯代码逐日累加（住宿按房间、餐饮与门票按“人均 × 人数”、每天固定 10 元交通），总价超过预算就记一条 critical error 并触发重试；重试 2 次仍不通过则进入 `auto_fix_plan`，由代码强制换成最便宜的酒店并替换高价餐厅，改完再校验一次，若仍超预算会在最终回答里明确提示。

**缓存隔离**：缓存 key 为 `chat:{user_id}:{input}`，用户之间互相隔离；只有 `intent == "plan"` 且确实生成了行程才写缓存。

**限流**：Redis + Lua 滑动窗口，IP 10 次/60 秒、会话 5 次/60 秒；Redis 不可用时降级放行，不影响主流程。

**可观测性**：所有大模型调用统一经 `core/llm.py` 出口，自动把 token 与耗时写入 `ai_calls`；每次请求写 `audit_logs`，包含鉴权用户、IP、UA、成功与否。

## 📄 License

MIT