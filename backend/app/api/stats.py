"""
统计接口
"""
from fastapi import APIRouter
from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.db_models import AICall, Session, Message, AuditLog


router = APIRouter(prefix="/stats", tags=["统计"])


@router.get("/overview")
def get_overview():
    """总览统计"""
    db = SessionLocal()
    try:
        total_calls = db.query(func.count(AICall.id)).scalar() or 0
        total_tokens = db.query(func.sum(AICall.total_tokens)).scalar() or 0
        total_input = db.query(func.sum(AICall.input_tokens)).scalar() or 0
        total_output = db.query(func.sum(AICall.output_tokens)).scalar() or 0
        success_calls = db.query(func.count(AICall.id)).filter(AICall.success == True).scalar() or 0
        avg_duration = db.query(func.avg(AICall.duration_ms)).scalar() or 0
        
        total_sessions = db.query(func.count(Session.id)).scalar() or 0
        total_messages = db.query(func.count(Message.id)).scalar() or 0
        total_audit = db.query(func.count(AuditLog.id)).scalar() or 0
        
        success_rate = round(success_calls / total_calls, 4) if total_calls > 0 else 1.0
        
        return {
            "ai": {
                "total_calls": total_calls,
                "success_calls": success_calls,
                "success_rate": success_rate,
                "total_tokens": int(total_tokens),
                "input_tokens": int(total_input),
                "output_tokens": int(total_output),
                "avg_duration_ms": round(float(avg_duration), 2),
            },
            "business": {
                "total_sessions": total_sessions,
                "total_messages": total_messages,
                "total_audit_logs": total_audit,
            }
        }
    finally:
        db.close()


@router.get("/by-purpose")
def get_by_purpose():
    """按用途统计"""
    db = SessionLocal()
    try:
        results = db.query(
            AICall.purpose,
            func.count(AICall.id).label("calls"),
            func.sum(AICall.total_tokens).label("tokens"),
            func.avg(AICall.duration_ms).label("avg_ms"),
        ).group_by(AICall.purpose).all()
        
        return [
            {
                "purpose": r[0] or "unknown",
                "calls": r[1],
                "tokens": int(r[2] or 0),
                "avg_duration_ms": round(float(r[3] or 0), 2),
            }
            for r in results
        ]
    finally:
        db.close()


@router.get("/recent-calls")
def get_recent_calls(limit: int = 20):
    """最近的调用"""
    db = SessionLocal()
    try:
        calls = db.query(AICall).order_by(
            AICall.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": c.id,
                "session_id": c.session_id,
                "model": c.model,
                "purpose": c.purpose,
                "tokens": c.total_tokens,
                "duration_ms": c.duration_ms,
                "success": c.success,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in calls
        ]
    finally:
        db.close()