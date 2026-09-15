import time
import json
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from app.graph.builder import app_graph
from app.core.logging import logger
from app.core.security import create_access_token, verify_token
from app.core.redis_rate_limiter import ip_limiter, session_limiter
from app.core.redis_cache import plan_cache
from app.models.session_mysql import session_store
from app.core.database import SessionLocal
from app.models.db_models import AICall, AuditLog
from app.api.stats import router as stats_router


app = FastAPI(
    title="深圳旅游规划 API",
    description="AI 驱动的深圳深度游规划服务",
    version="1.0.0"
)

# CORS：允许任意来源，方便前端页面（file:// 或本地 http 服务）直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stats_router)


class ChatRequest(BaseModel):
    input: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    output: str
    intent: str
    plan: list
    request: dict
    version: int
    cached: bool = False


class LoginRequest(BaseModel):
    user_id: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization: Bearer <token> 请求头中取出 token"""
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


# LangGraph 节点 → 进度提示
NODE_PROGRESS = {
    "load_session": "正在加载会话...",
    "parse_intent": "正在识别意图...",
    "parse_request": "正在解析需求...",
    "chat_reply": "正在组织回复...",
    "parse_modification": "正在解析修改需求...",
    "rag_retrieve": "正在检索景点和美食...",
    "enrich_coordinates": "正在补充地理位置...",
    "search_hotels": "正在搜索酒店...",
    "allocate_budget": "正在分配预算...",
    "generate_plan": "正在生成行程...",
    "modify_plan": "正在修改行程...",
    "validate_plan": "正在校验行程和预算...",
    "optimize_route": "正在优化路线...",
    "auto_fix_plan": "正在自动调整预算...",
    "generate_answer": "正在整理回答...",
}


def _sse(event: str, data: str) -> str:
    """拼一条 SSE 消息（event + data + 空行结尾）"""
    return f"event: {event}\ndata: {data}\n\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """登录接口：用 user_id 换取 JWT（演示用，未做密码校验）"""
    user_id = req.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    
    access_token = create_access_token(user_id)
    logger.info(f"[{user_id}] 登录成功，已签发 access token")
    return LoginResponse(access_token=access_token, token_type="bearer")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request, authorization: Optional[str] = Header(None)):
    """对话接口（JWT 鉴权 + 限流 + 缓存）"""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # ========== JWT 鉴权 ==========
    token = _extract_bearer_token(authorization)
    user_id = verify_token(token) if token else None
    if not user_id:
        detail = (
            "缺少或格式错误的 Authorization 请求头，应为：Bearer <token>"
            if not token else "token 无效或已过期"
        )
        logger.warning(f"[{ip}] 鉴权失败：{detail}")
        _save_audit(
            session_id=req.session_id or "", action="auth_failed",
            input_text=req.input, output_text="",
            ip=ip, user_id="", user_agent=user_agent,
            success=False, error_msg=detail,
        )
        raise HTTPException(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 未显式传 session_id 时，用 token 里的 user_id 作为会话标识
    session_id = req.session_id or user_id
    
    # ========== IP 限流 ==========
    ip_ok, ip_remaining, ip_reset = ip_limiter.allow(ip)
    if not ip_ok:
        logger.warning(f"[{ip}] 被 IP 限流")
        _save_audit(
            session_id=session_id, action="rate_limit_ip",
            input_text=req.input, output_text="",
            ip=ip, user_id=user_id, success=False,
            error_msg=f"IP 限流，{ip_reset}秒后重试"
        )
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁，请 {ip_reset} 秒后重试",
            headers={"Retry-After": str(ip_reset)}
        )
    
    # ========== Session 限流 ==========
    session_ok, session_remaining, session_reset = session_limiter.allow(session_id)
    if not session_ok:
        logger.warning(f"[{session_id}] 被会话限流")
        _save_audit(
            session_id=session_id, action="rate_limit_session",
            input_text=req.input, output_text="",
            ip=ip, user_id=user_id, success=False,
            error_msg=f"会话限流，{session_reset}秒后重试"
        )
        raise HTTPException(
            status_code=429,
            detail=f"该会话请求太频繁，请 {session_reset} 秒后重试",
            headers={"Retry-After": str(session_reset)}
        )
    
    # ========== 尝试读缓存 ==========
    cache_key = f"chat:{user_id}:{req.input}"
    cached_result = plan_cache.get(cache_key)
    if cached_result:
        logger.info(f"[{session_id}] 命中缓存")
        _save_audit(
            session_id=session_id, action="cache_hit",
            input_text=req.input, output_text=cached_result.get("output", "")[:200],
            ip=ip, user_id=user_id, success=True,
        )
        return ChatResponse(
            output=cached_result.get("output", ""),
            intent=cached_result.get("intent", ""),
            plan=cached_result.get("plan", []),
            request=cached_result.get("request", {}),
            version=cached_result.get("version", 1),
            cached=True,
        )
    
    # ========== 正常处理 ==========
    start_time = time.time()
    logger.info(f"[{session_id}] 收到请求：{req.input}（IP 剩余 {ip_remaining}）")
    
    session_store.append_message(session_id, "user", req.input)
    
    try:
        initial_state = {
            "session_id": session_id,
            "user_input": req.input,
            "request": {},
            "intent": "",
            "prev_plan": [],
            "modify_target": {},
            "attractions": [],
            "restaurants": [],
            "hotels": [],
            "weather": "",
            "route_info": {},
            "plan": [],
            "final_answer": "",
            "version": 0,
            "errors": [],
            "retry_count": 0,
            "messages": []
        }
        
        result = app_graph.invoke(initial_state)
        
        final_plan = result.get("plan", [])
        new_version = result.get("version", 0) + 1
        
        if final_plan:
            session_store.update(
                session_id,
                current_plan=final_plan,
                current_request=result.get("request", {}),
                version=new_version,
            )
        
        final_answer = result.get("final_answer", "")
        session_store.append_message(session_id, "assistant", final_answer)
        
        # 只有 plan 意图才缓存
        if result.get("intent") == "plan" and final_plan:
            plan_cache.set(cache_key, {
                "output": final_answer,
                "intent": result.get("intent", ""),
                "plan": final_plan,
                "request": result.get("request", {}),
                "version": new_version,
            })
        
        duration_ms = int((time.time() - start_time) * 1000)
        _save_audit(
            session_id=session_id,
            action=result.get("intent", "unknown"),
            input_text=req.input,
            output_text=final_answer,
            ip=ip,
            user_id=user_id,
            user_agent=request.headers.get("user-agent", ""),
            success=True,
            duration_ms=duration_ms,
        )
        
        return ChatResponse(
            output=final_answer,
            intent=result.get("intent", ""),
            plan=final_plan,
            request=result.get("request", {}),
            version=new_version,
            cached=False,
        )
    
    except Exception as e:
        logger.error(f"处理失败：{e}", exc_info=True)
        _save_audit(
            session_id=session_id,
            action="error",
            input_text=req.input,
            output_text="",
            ip=ip,
            user_id=user_id,
            user_agent=request.headers.get("user-agent", ""),
            success=False,
            error_msg=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request, authorization: Optional[str] = Header(None)):
    """流式对话接口（SSE）：鉴权/限流与 /chat 一致，逐节点推送进度"""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    
    # ========== JWT 鉴权 ==========
    token = _extract_bearer_token(authorization)
    user_id = verify_token(token) if token else None
    if not user_id:
        detail = (
            "缺少或格式错误的 Authorization 请求头，应为：Bearer <token>"
            if not token else "token 无效或已过期"
        )
        logger.warning(f"[{ip}] 鉴权失败：{detail}")
        _save_audit(
            session_id=req.session_id or "", action="auth_failed",
            input_text=req.input, output_text="",
            ip=ip, user_id="", user_agent=user_agent,
            success=False, error_msg=detail,
        )
        raise HTTPException(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 未显式传 session_id 时，用 token 里的 user_id 作为会话标识
    session_id = req.session_id or user_id
    
    # ========== IP 限流 ==========
    ip_ok, ip_remaining, ip_reset = ip_limiter.allow(ip)
    if not ip_ok:
        logger.warning(f"[{ip}] 被 IP 限流")
        _save_audit(
            session_id=session_id, action="rate_limit_ip",
            input_text=req.input, output_text="",
            ip=ip, user_id=user_id, success=False,
            error_msg=f"IP 限流，{ip_reset}秒后重试"
        )
        raise HTTPException(
            status_code=429,
            detail=f"请求太频繁，请 {ip_reset} 秒后重试",
            headers={"Retry-After": str(ip_reset)}
        )
    
    # ========== Session 限流 ==========
    session_ok, session_remaining, session_reset = session_limiter.allow(session_id)
    if not session_ok:
        logger.warning(f"[{session_id}] 被会话限流")
        _save_audit(
            session_id=session_id, action="rate_limit_session",
            input_text=req.input, output_text="",
            ip=ip, user_id=user_id, success=False,
            error_msg=f"会话限流，{session_reset}秒后重试"
        )
        raise HTTPException(
            status_code=429,
            detail=f"该会话请求太频繁，请 {session_reset} 秒后重试",
            headers={"Retry-After": str(session_reset)}
        )
    
    logger.info(f"[{session_id}] 收到流式请求：{req.input}（IP 剩余 {ip_remaining}）")
    
    return StreamingResponse(
        _chat_stream_generator(req, session_id, user_id, ip, user_agent),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _chat_stream_generator(req: ChatRequest, session_id: str, user_id: str, ip: str, user_agent: str):
    """SSE 生成器：先查缓存，再用 app_graph.stream 逐节点推进度，最后推完整结果"""
    cache_key = f"chat:{user_id}:{req.input}"
    
    # ========== 缓存命中：直接推 result ==========
    cached_result = plan_cache.get(cache_key)
    if cached_result:
        logger.info(f"[{session_id}] 命中缓存（stream）")
        _save_audit(
            session_id=session_id, action="cache_hit",
            input_text=req.input, output_text=cached_result.get("output", "")[:200],
            ip=ip, user_id=user_id, success=True,
        )
        yield _sse("result", json.dumps({
            "output": cached_result.get("output", ""),
            "intent": cached_result.get("intent", ""),
            "plan": cached_result.get("plan", []),
            "request": cached_result.get("request", {}),
            "version": cached_result.get("version", 1),
            "cached": True,
        }, ensure_ascii=False))
        return
    
    # ========== 正常处理 ==========
    start_time = time.time()
    session_store.append_message(session_id, "user", req.input)
    
    state = {
        "session_id": session_id,
        "user_input": req.input,
        "request": {},
        "intent": "",
        "prev_plan": [],
        "modify_target": {},
        "attractions": [],
        "restaurants": [],
        "hotels": [],
        "weather": "",
        "route_info": {},
        "plan": [],
        "final_answer": "",
        "version": 0,
        "errors": [],
        "retry_count": 0,
        "messages": []
    }
    final_state = dict(state)
    
    try:
        # stream_mode="updates"：每个节点跑完产出一条 {节点名: 增量}
        for chunk in app_graph.stream(state, stream_mode="updates"):
            for node_name, update in chunk.items():
                if isinstance(update, dict):
                    final_state.update(update)
                # 节点名不会是 state 字段名，以此兜底防止流模式退化成 values
                if node_name not in state:
                    yield _sse("progress", NODE_PROGRESS.get(node_name, f"正在执行 {node_name}..."))
        
        final_plan = final_state.get("plan", [])
        new_version = final_state.get("version", 0) + 1
        
        if final_plan:
            session_store.update(
                session_id,
                current_plan=final_plan,
                current_request=final_state.get("request", {}),
                version=new_version,
            )
        
        final_answer = final_state.get("final_answer", "")
        session_store.append_message(session_id, "assistant", final_answer)
        
        # 只有 plan 意图才缓存
        if final_state.get("intent") == "plan" and final_plan:
            plan_cache.set(cache_key, {
                "output": final_answer,
                "intent": final_state.get("intent", ""),
                "plan": final_plan,
                "request": final_state.get("request", {}),
                "version": new_version,
            })
        
        _save_audit(
            session_id=session_id,
            action=final_state.get("intent", "unknown"),
            input_text=req.input,
            output_text=final_answer,
            ip=ip,
            user_id=user_id,
            user_agent=user_agent,
            success=True,
            duration_ms=int((time.time() - start_time) * 1000),
        )
        
        yield _sse("result", json.dumps({
            "output": final_answer,
            "intent": final_state.get("intent", ""),
            "plan": final_plan,
            "request": final_state.get("request", {}),
            "version": new_version,
            "cached": False,
        }, ensure_ascii=False))
    
    except Exception as e:
        logger.error(f"流式处理失败：{e}", exc_info=True)
        _save_audit(
            session_id=session_id,
            action="error",
            input_text=req.input,
            output_text="",
            ip=ip,
            user_id=user_id,
            user_agent=user_agent,
            success=False,
            error_msg=str(e),
        )
        yield _sse("error", f"处理失败：{e}")


def _save_audit(session_id, action, input_text, output_text, ip="", user_id="", user_agent="", success=True, error_msg="", duration_ms=0):
    """保存审计日志"""
    db = SessionLocal()
    try:
        log = AuditLog(
            session_id=session_id,
            user_id=user_id,
            action=action,
            input_text=input_text,
            output_text=output_text[:2000] if output_text else "",
            ip=ip,
            user_agent=user_agent[:256],
            success=success,
            error_msg=error_msg,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"审计日志写入失败：{e}")
    finally:
        db.close()
