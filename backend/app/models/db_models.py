"""
数据库表定义
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, JSON, Boolean
)
from app.core.database import Base


class Session(Base):
    """会话表"""
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    current_plan = Column(JSON, default=list)         # 当前行程
    current_request = Column(JSON, default=dict)      # 当前请求参数
    version = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Message(Base):
    """对话历史表"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(16), nullable=False)         # user / assistant
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)


class AICall(Base):
    """AI 调用记录表"""
    __tablename__ = "ai_calls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True)
    model = Column(String(64))
    purpose = Column(String(64))                       # 用途：parse_intent / generate_plan / ...
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)           # 耗时（毫秒）
    success = Column(Boolean, default=True)
    error_msg = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True)
    user_id = Column(String(64), index=True)            # 鉴权用户（来自 JWT）
    action = Column(String(64))                        # 动作：chat / modify / ...
    input_text = Column(Text)
    output_text = Column(Text)
    ip = Column(String(64))
    user_agent = Column(String(256))
    success = Column(Boolean, default=True)
    error_msg = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)
