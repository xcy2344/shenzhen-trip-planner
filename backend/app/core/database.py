"""
MySQL 数据库连接
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import config


# 创建引擎
engine = create_engine(
    config.MYSQL_URL,
    pool_pre_ping=True,      # 自动检测断开的连接
    pool_recycle=3600,       # 1小时回收
    echo=False,              # 设为 True 可看 SQL
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 模型基类
Base = declarative_base()


def get_db():
    """获取数据库会话（FastAPI 依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库：创建所有表"""
    from app.models import db_models  # noqa
    Base.metadata.create_all(bind=engine)
    _ensure_audit_user_id()
    print("✅ 数据库表已创建")


def _ensure_audit_user_id():
    """给已存在的老库补上 audit_logs.user_id 列（create_all 不会修改已有表）"""
    try:
        columns = [c["name"] for c in inspect(engine).get_columns("audit_logs")]
        if "user_id" in columns:
            return
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN user_id VARCHAR(64) NULL"))
            conn.execute(text("CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id)"))
        print("✅ 已为 audit_logs 补上 user_id 列")
    except Exception as e:
        print(f"⚠️ audit_logs.user_id 补列失败：{e}")
