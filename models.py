"""数据库模型"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")


def _now_bj():
    return datetime.now(TZ)


db = SQLAlchemy()


class User(db.Model):
    """用户表"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(128), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(64), nullable=True)  # 自定义名字
    base_salary = db.Column(db.Float, default=5000.0)  # 底薪
    created_at = db.Column(db.DateTime, default=_now_bj)
    updated_at = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    records = db.relationship("AttendanceRecord", backref="user", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "openid": self.openid,
            "nickname": self.nickname or f"用户{self.id}",
            "base_salary": self.base_salary,
        }


class AttendanceRecord(db.Model):
    """考勤记录表"""
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)  # 打卡日期
    check_in = db.Column(db.DateTime, nullable=True)  # 上班时间
    check_out = db.Column(db.DateTime, nullable=True)  # 下班时间
    work_hours = db.Column(db.Float, default=0.0)  # 工作时长（已扣除午休）
    overtime_hours = db.Column(db.Float, default=0.0)  # 加班时长
    overtime_pay = db.Column(db.Float, default=0.0)  # 加班费
    is_manual = db.Column(db.Boolean, default=False)  # 是否补卡
    remark = db.Column(db.String(256), nullable=True)  # 备注
    created_at = db.Column(db.DateTime, default=_now_bj)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.strftime("%Y-%m-%d") if self.date else None,
            "check_in": self.check_in.strftime("%H:%M:%S") if self.check_in else None,
            "check_out": self.check_out.strftime("%H:%M:%S") if self.check_out else None,
            "work_hours": round(self.work_hours, 2),
            "overtime_hours": round(self.overtime_hours, 2),
            "overtime_pay": round(self.overtime_pay, 2),
            "is_manual": self.is_manual,
            "remark": self.remark,
        }


class Holiday(db.Model):
    """法定节假日表"""
    __tablename__ = "holidays"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, unique=True, nullable=False, index=True)
    name = db.Column(db.String(64), nullable=True)  # 节日名称
    year = db.Column(db.Integer, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.strftime("%Y-%m-%d"),
            "name": self.name,
            "year": self.year,
        }


class SystemConfig(db.Model):
    """系统配置表"""
    __tablename__ = "system_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.String(256), nullable=False)

    @staticmethod
    def get(key, default=None):
        cfg = SystemConfig.query.filter_by(key=key).first()
        return cfg.value if cfg else default

    @staticmethod
    def set(key, value):
        cfg = SystemConfig.query.filter_by(key=key).first()
        if cfg:
            cfg.value = str(value)
        else:
            cfg = SystemConfig(key=key, value=str(value))
            db.session.add(cfg)
        db.session.commit()
