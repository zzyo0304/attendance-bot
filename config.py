"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "attendance-secret-key")
    # 优先使用 PostgreSQL（Supabase），本地开发回退到 SQLite
    _db_url = os.getenv("DATABASE_URL", "")
    if _db_url and _db_url.startswith("postgres"):
        # Render 环境的 DATABASE_URL 前缀需要适配
        SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)
    else:
        SQLALCHEMY_DATABASE_URI = _db_url or "sqlite:///attendance.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 微信配置
    WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "")
    WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")
    WECHAT_APP_SECRET = os.getenv("WECHAT_APP_SECRET", "")

    # 薪资配置
    DEFAULT_BASE_SALARY = float(os.getenv("DEFAULT_BASE_SALARY", "5000"))
    DEFAULT_WORK_HOURS = int(os.getenv("DEFAULT_WORK_HOURS", "8"))
    OVERTIME_RATE_WORKDAY = float(os.getenv("OVERTIME_RATE_WORKDAY", "1.5"))
    OVERTIME_RATE_WEEKEND = float(os.getenv("OVERTIME_RATE_WEEKEND", "2.0"))
    OVERTIME_RATE_HOLIDAY = float(os.getenv("OVERTIME_RATE_HOLIDAY", "3.0"))
    STANDARD_WORK_DAYS = 21.75  # 月标准出勤天数

    # 午休时间
    LUNCH_START_HOUR = 11
    LUNCH_START_MINUTE = 30
    LUNCH_END_HOUR = 13
    LUNCH_END_MINUTE = 0
    LUNCH_DURATION = 1.5  # 午休1.5小时

    # 管理员
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
