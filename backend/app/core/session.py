"""
会话存储模块
用内存字典存储每个会话的历史和当前行程
生产环境应换成 Redis
"""
import time
from typing import Dict, Any, Optional


class SessionStore:
    """会话存储（内存版）"""
    
    def __init__(self):
        # { session_id: { messages, current_plan, current_request, version, updated_at } }
        self._store: Dict[str, Dict[str, Any]] = {}
    
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        return self._store.get(session_id)
    
    def save(self, session_id: str, data: Dict[str, Any]):
        """保存会话（全量覆盖）"""
        self._store[session_id] = {
            **data,
            "updated_at": time.time()
        }
    
    def update(self, session_id: str, **kwargs):
        """更新会话（局部更新）"""
        if session_id not in self._store:
            self._store[session_id] = {
                "messages": [],
                "current_plan": [],
                "current_request": {},
                "version": 0,
            }
        self._store[session_id].update(kwargs)
        self._store[session_id]["updated_at"] = time.time()
    
    def append_message(self, session_id: str, role: str, content: str):
        """追加一条对话"""
        if session_id not in self._store:
            self._store[session_id] = {
                "messages": [],
                "current_plan": [],
                "current_request": {},
                "version": 0,
            }
        self._store[session_id]["messages"].append({
            "role": role,
            "content": content,
            "time": time.time()
        })
    
    def get_messages(self, session_id: str):
        """获取对话历史"""
        session = self._store.get(session_id)
        if not session:
            return []
        return session.get("messages", [])
    
    def get_plan(self, session_id: str):
        """获取当前行程"""
        session = self._store.get(session_id)
        if not session:
            return []
        return session.get("current_plan", [])
    
    def get_request(self, session_id: str):
        """获取当前请求参数"""
        session = self._store.get(session_id)
        if not session:
            return {}
        return session.get("current_request", {})
    
    def get_version(self, session_id: str):
        """获取当前版本号"""
        session = self._store.get(session_id)
        if not session:
            return 0
        return session.get("version", 0)
    
    def clear(self, session_id: str):
        """清除会话"""
        if session_id in self._store:
            del self._store[session_id]


# 全局单例
session_store = SessionStore()