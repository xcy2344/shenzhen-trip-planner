"""
LLM 调用封装
自动记录 Token 消耗和耗时
"""
import time
import dashscope
from app.core.config import config


# 当前请求上下文（用于记录是哪个 session 在调用）
_current_context = {
    "session_id": "",
    "purpose": "",   # parse_intent / generate_plan / ...
}


def set_context(session_id: str = "", purpose: str = ""):
    """设置当前调用上下文"""
    _current_context["session_id"] = session_id
    _current_context["purpose"] = purpose


def chat(prompt: str, purpose: str = "") -> str:
    """调用百炼大模型（自动记录 token）"""
    dashscope.api_key = config.BAILIAN_API_KEY
    
    start = time.time()
    success = True
    error_msg = ""
    input_tokens = 0
    output_tokens = 0
    
    try:
        response = dashscope.Generation.call(
            model=config.BAILIAN_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        if response.status_code != 200:
            success = False
            error_msg = response.message
            return ""
        
        # 提取 token 信息
        usage = response.get("usage", {}) or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        
        text = response["output"]["text"]
        return text
    
    except Exception as e:
        success = False
        error_msg = str(e)
        return ""
    
    finally:
        # 记录到数据库
        duration_ms = int((time.time() - start) * 1000)
        _save_ai_call(
            model=config.BAILIAN_MODEL,
            purpose=purpose or _current_context.get("purpose", ""),
            session_id=_current_context.get("session_id", ""),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            success=success,
            error_msg=error_msg,
        )


def _save_ai_call(model, purpose, session_id, input_tokens, output_tokens, duration_ms, success, error_msg=""):
    """把调用记录写入数据库"""
    try:
        from app.core.database import SessionLocal
        from app.models.db_models import AICall
        
        db = SessionLocal()
        try:
            call = AICall(
                session_id=session_id or "",
                model=model,
                purpose=purpose or "",
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                total_tokens=(input_tokens or 0) + (output_tokens or 0),
                duration_ms=duration_ms,
                success=success,
                error_msg=error_msg[:500] if error_msg else "",
            )
            db.add(call)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        # 记录失败不影响主流程
        print(f"[警告] AI 调用记录失败：{e}")