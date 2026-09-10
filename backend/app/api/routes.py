import time
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from app.graph.builder import app_graph
from app.core.logging import logger
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request):
    """对话接口（带限流 + 缓存）"""
    session_id = req.session_id or "default_session"
    ip = request.client.host if request.client else "unknown"
    
    # ========== IP 限流 ==========
    ip_ok, ip_remaining, ip_reset = ip_limiter.allow(ip)
    if not ip_ok:
        logger.warning(f"[{ip}] 被 IP 限流")
        _save_audit(
            session_id=session_id, action="rate_limit_ip",
            input_text=req.input, output_text="",
            ip=ip, success=False,
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
            ip=ip, success=False,
            error_msg=f"会话限流，{session_reset}秒后重试"
        )
        raise HTTPException(
            status_code=429,
            detail=f"该会话请求太频繁，请 {session_reset} 秒后重试",
            headers={"Retry-After": str(session_reset)}
        )
    
    # ========== 尝试读缓存 ==========
    cache_key = f"chat:{req.input}"
    cached_result = plan_cache.get(cache_key)
    if cached_result:
        logger.info(f"[{session_id}] 命中缓存")
        _save_audit(
            session_id=session_id, action="cache_hit",
            input_text=req.input, output_text=cached_result.get("output", "")[:200],
            ip=ip, success=True,
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
            user_agent=request.headers.get("user-agent", ""),
            success=False,
            error_msg=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


def _save_audit(session_id, action, input_text, output_text, ip="", user_agent="", success=True, error_msg="", duration_ms=0):
    """保存审计日志"""
    db = SessionLocal()
    try:
        log = AuditLog(
            session_id=session_id,
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