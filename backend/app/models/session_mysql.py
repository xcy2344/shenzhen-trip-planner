"""
MySQL 版会话存储
"""
from typing import Dict, Any, Optional
from app.core.database import SessionLocal, init_db
from app.models.db_models import Session, Message


class MySQLSessionStore:
    """MySQL 会话存储"""
    
    def __init__(self):
        init_db()
    
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            session = db.query(Session).filter(
                Session.session_id == session_id
            ).first()
            if not session:
                return None
            return {
                "session_id": session.session_id,
                "current_plan": session.current_plan or [],
                "current_request": session.current_request or {},
                "version": session.version or 0,
            }
        finally:
            db.close()
    
    def save(self, session_id: str, data: Dict[str, Any]):
        db = SessionLocal()
        try:
            session = db.query(Session).filter(
                Session.session_id == session_id
            ).first()
            
            if not session:
                session = Session(session_id=session_id)
                db.add(session)
            
            if "current_plan" in data:
                session.current_plan = data["current_plan"]
            if "current_request" in data:
                session.current_request = data["current_request"]
            if "version" in data:
                session.version = data["version"]
            
            db.commit()
        finally:
            db.close()
    
    def update(self, session_id: str, **kwargs):
        self.save(session_id, kwargs)
    
    def append_message(self, session_id: str, role: str, content: str):
        db = SessionLocal()
        try:
            msg = Message(session_id=session_id, role=role, content=content)
            db.add(msg)
            db.commit()
        finally:
            db.close()
    
    def get_messages(self, session_id: str) -> list:
        db = SessionLocal()
        try:
            msgs = db.query(Message).filter(
                Message.session_id == session_id
            ).order_by(Message.created_at).all()
            return [
                {"role": m.role, "content": m.content, "time": m.created_at.timestamp() if m.created_at else 0}
                for m in msgs
            ]
        finally:
            db.close()
    
    def get_plan(self, session_id: str) -> list:
        session = self.get(session_id)
        return session["current_plan"] if session else []
    
    def get_request(self, session_id: str) -> dict:
        session = self.get(session_id)
        return session["current_request"] if session else {}
    
    def get_version(self, session_id: str) -> int:
        session = self.get(session_id)
        return session["version"] if session else 0
    
    def clear(self, session_id: str):
        db = SessionLocal()
        try:
            db.query(Session).filter(Session.session_id == session_id).delete()
            db.query(Message).filter(Message.session_id == session_id).delete()
            db.commit()
        finally:
            db.close()


# 全局单例
session_store = MySQLSessionStore()