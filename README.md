# 深圳深度游 AI 旅行规划平台

基于 LangGraph 多 Agent 协作的智能旅游规划平台，支持通过自然语言生成个性化深圳深度游行程。

## ✨ 核心功能

- 🤖 **多 Agent 编排**：基于 LangGraph 设计 10+ 节点工作流，支持条件分支、循环重试、兜底降级
- 📚 **RAG 知识增强**：深圳旅游知识库（38 条）+ 向量混合检索，降低大模型幻觉
- 💬 **多轮对话调整**：支持"轻松一些""加点美食"等自然语言修改，局部重规划避免全量重生成
- 🗺️ **路线优化**：高德地图 API + 就近排序 + 开放时间校验
- 💰 **预算硬约束**：用代码算钱，确保不超预算
- ⚡ **Redis 缓存**：相同请求响应从 60s 降至 0.1s
- 🛡️ **滑动窗口限流**：Redis + Lua 脚本，支持降级放行
- 📊 **可观测性**：全链路追踪 + AI 调用统计 + 审计日志

## 🏗️ 技术栈

| 分类 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI |
| Agent 框架 | LangGraph |
| 大模型 | 阿里云百炼 qwen-plus |
| RAG | ChromaDB + 百炼 Embedding |
| 数据库 | MySQL + Redis |
| 地图 | 高德地图 API |

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/shenzhen-trip-planner.git
cd shenzhen-trip-planner
```

### 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

### 3. 配置环境变量

在 `backend/` 下创建 `.env`：

```env
BAILIAN_API_KEY=你的百炼Key
BAILIAN_MODEL=qwen-plus
AMAP_API_KEY=你的高德Key
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=shenzhen_trip
```

### 4. 初始化数据库

```bash
mysql -u root -p -e "CREATE DATABASE shenzhen_trip DEFAULT CHARACTER SET utf8mb4"
cd backend
python -c "from app.core.database import init_db; init_db()"
```

### 5. 构建 RAG 索引

```bash
python -c "from app.rag.store import build_index; build_index(force_rebuild=True)"
```

### 6. 启动服务

```bash
python main.py
```

访问接口文档：http://127.0.0.1:8000/docs

## 📖 API 接口

### POST /chat
对话接口

**请求：**
```json
{
  "input": "帮我规划深圳3日游，2个人，预算3000",
  "session_id": "user_001"
}
```

**响应：**
```json
{
  "output": "你好呀～为你规划的3日游行程...",
  "intent": "plan",
  "plan": [...],
  "version": 1,
  "cached": false
}
```

### GET /stats/overview
统计总览（AI 调用次数、Token 消耗、成功率）

### GET /health
健康检查

## 📁 项目结构

```
backend/
├── app/
│   ├── api/          # API 接口
│   ├── core/         # 基础设施（配置、日志、数据库、Redis、限流、缓存）
│   ├── graph/        # LangGraph 多 Agent 编排
│   ├── models/       # 数据库模型
│   ├── rag/          # RAG 知识库
│   └── tools/        # 工具（天气、景点、美食、地图）
├── main.py           # 入口
└── requirements.txt
```

## 🔄 LangGraph 工作流

```
START → 加载会话 → 意图识别
                    ├── plan → 参数解析
                    ├── modify → 修改解析
                    └── chat → END
                            ↓
                    RAG 检索 → 补坐标 → 酒店检索 → 预算分配
                            ↓
                    生成行程 / 修改行程
                            ↓
                    结果校验 → 路线优化
                            ↓
                    生成回答 → END
```

## 📄 License

MIT