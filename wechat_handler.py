"""微信消息处理"""
import hashlib
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date
from models import db, User, AttendanceRecord
from utils import (
    get_attendance_cycle, get_day_type, calculate_work_and_overtime,
    calculate_overtime_pay, get_hourly_rate, get_default_record_for_date,
    count_workdays_in_range
)
from config import Config


def verify_signature(signature, timestamp, nonce):
    """验证微信服务器签名"""
    token = Config.WECHAT_TOKEN
    tmp_list = sorted([token, timestamp, nonce])
    tmp_str = "".join(tmp_list)
    tmp_str = hashlib.sha1(tmp_str.encode()).hexdigest()
    return tmp_str == signature


def parse_xml(xml_data):
    """解析微信XML消息"""
    try:
        root = ET.fromstring(xml_data)
        msg = {}
        for child in root:
            msg[child.tag] = child.text
        return msg
    except Exception:
        return {}


def build_text_reply(to_user, from_user, content):
    """构建文本回复XML"""
    reply = f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
    return reply


def get_or_create_user(openid):
    """获取或创建用户"""
    user = User.query.filter_by(openid=openid).first()
    if not user:
        user = User(openid=openid, base_salary=Config.DEFAULT_BASE_SALARY)
        db.session.add(user)
        db.session.commit()
    return user


def handle_message(msg):
    """处理微信消息，返回回复内容"""
    openid = msg.get("FromUserName", "")
    content = msg.get("Content", "").strip()
    msg_type = msg.get("MsgType", "text")

    if msg_type != "text":
        return "请发送文字指令，发送「帮助」查看功能列表"

    user = get_or_create_user(openid)
    nickname = user.nickname or f"用户{user.id}"

    # ---- 帮助 ----
    if content == "帮助":
        return _help_text()

    # ---- 设置用户名 ----
    if content.startswith("设置用户名") or content.startswith("改名"):
        name = content.replace("设置用户名", "").replace("改名", "").strip()
        if not name:
            return "请按格式发送：设置用户名 张三"
        user.nickname = name
        db.session.commit()
        return f"✅ 用户名已设置为：{name}"

    # ---- 上班 ----
    if content == "上班":
        return _check_in(user)

    # ---- 下班 ----
    if content == "下班":
        return _check_out(user)

    # ---- 查询当天考勤 ----
    if content == "查询":
        return _query_today(user)

    # ---- 查询底薪 ----
    if content == "底薪":
        return f"📊 {nickname}\n当前底薪：{user.base_salary:.0f} 元/月\n小时工资：{get_hourly_rate(user.base_salary):.2f} 元/小时\n\n计算方式：底薪 ÷ 21.75天 ÷ 8小时"

    # ---- 汇总 ----
    if content == "汇总":
        return _query_summary(user)

    return f"未识别的指令，发送「帮助」查看功能列表"


def _help_text():
    return """📋 考勤打卡 - 功能列表

【打卡】
• 发送「上班」- 上班打卡
• 发送「下班」- 下班打卡

【查询】
• 发送「查询」- 查看今日考勤
• 发送「汇总」- 查看本月汇总
• 发送「底薪」- 查看底薪配置

【设置】
• 发送「设置用户名 张三」- 设置名字

【加班费计算规则】
• 工作日超8h：1.5倍
• 休息日(周末)：2.0倍
• 法定节假日：3.0倍
• 午休11:30-13:00不计入工时"""


def _check_in(user):
    """上班打卡"""
    today = date.today()
    nickname = user.nickname or f"用户{user.id}"

    # 检查是否已经打过上班卡
    existing = AttendanceRecord.query.filter_by(
        user_id=user.id, date=today
    ).first()

    if existing and existing.check_in:
        return f"⚠️ {nickname}，你今天已经在 {existing.check_in.strftime('%H:%M:%S')} 打过上班卡了"

    now = datetime.now()

    if existing:
        # 已有记录(可能是补卡的)，更新上班时间
        existing.check_in = now
        existing.is_manual = False
    else:
        existing = AttendanceRecord(
            user_id=user.id,
            date=today,
            check_in=now
        )
        db.session.add(existing)

    db.session.commit()

    day_type = get_day_type(today)
    type_text = {"workday": "工作日", "weekend": "休息日", "holiday": "法定节假日"}
    return f"✅ {nickname}，上班打卡成功！\n⏰ {now.strftime('%H:%M:%S')}\n📅 {today} {type_text.get(day_type, '')}"


def _check_out(user):
    """下班打卡"""
    today = date.today()
    nickname = user.nickname or f"用户{user.id}"

    existing = AttendanceRecord.query.filter_by(
        user_id=user.id, date=today
    ).first()

    if not existing or not existing.check_in:
        # 没有上班记录，自动补上班卡（默认9:00）
        now = datetime.now()
        check_in = datetime.combine(today, datetime.strptime("09:00", "%H:%M").time())
        if not existing:
            existing = AttendanceRecord(
                user_id=user.id,
                date=today,
                check_in=check_in
            )
            db.session.add(existing)
        else:
            existing.check_in = check_in
        existing.check_out = now
    elif existing.check_out:
        return f"⚠️ {nickname}，你今天已经在 {existing.check_out.strftime('%H:%M:%S')} 打过下班卡了"
    else:
        existing.check_out = datetime.now()

    # 计算工时和加班费
    day_type = get_day_type(today)
    work_hours, overtime_hours = calculate_work_and_overtime(
        existing.check_in, existing.check_out, day_type
    )
    hourly_rate = get_hourly_rate(user.base_salary)
    overtime_pay = calculate_overtime_pay(overtime_hours, day_type, hourly_rate)

    existing.work_hours = work_hours
    existing.overtime_hours = overtime_hours
    existing.overtime_pay = overtime_pay

    db.session.commit()

    type_text = {"workday": "工作日", "weekend": "休息日", "holiday": "法定节假日"}
    return (
        f"✅ {nickname}，下班打卡成功！\n"
        f"⏰ {existing.check_out.strftime('%H:%M:%S')}\n"
        f"📅 {today} {type_text.get(day_type, '')}\n"
        f"━━━━━━━━━━\n"
        f"🕐 工作时长：{work_hours:.1f}h\n"
        f"⏱ 加班时长：{overtime_hours:.1f}h\n"
        f"💰 加班费：{overtime_pay:.2f}元"
    )


def _query_today(user):
    """查询今日考勤"""
    today = date.today()
    nickname = user.nickname or f"用户{user.id}"

    record = AttendanceRecord.query.filter_by(
        user_id=user.id, date=today
    ).first()

    day_type = get_day_type(today)
    type_text = {"workday": "工作日", "weekend": "休息日", "holiday": "法定节假日"}

    if not record:
        # 返回默认情况
        if day_type == "workday":
            return f"📋 {nickname} 今日考勤\n📅 {today} {type_text.get(day_type, '')}\n📌 暂未打卡\n💡 默认出勤：8小时（无加班）"
        else:
            return f"📋 {nickname} 今日考勤\n📅 {today} {type_text.get(day_type, '')}\n📌 暂未打卡\n💡 默认休息"

    ci = record.check_in.strftime('%H:%M:%S') if record.check_in else "未打卡"
    co = record.check_out.strftime('%H:%M:%S') if record.check_out else "未打卡"

    return (
        f"📋 {nickname} 今日考勤\n"
        f"📅 {today} {type_text.get(day_type, '')}\n"
        f"━━━━━━━━━━\n"
        f"⏰ 上班：{ci}\n"
        f"⏰ 下班：{co}\n"
        f"🕐 工时：{record.work_hours:.1f}h\n"
        f"⏱ 加班：{record.overtime_hours:.1f}h\n"
        f"💰 加班费：{record.overtime_pay:.2f}元"
    )


def _query_summary(user):
    """查询本月考勤汇总"""
    nickname = user.nickname or f"用户{user.id}"
    cycle_start, cycle_end, cycle_label = get_attendance_cycle()

    records = AttendanceRecord.query.filter(
        AttendanceRecord.user_id == user.id,
        AttendanceRecord.date >= cycle_start,
        AttendanceRecord.date <= cycle_end
    ).all()

    record_dates = {r.date for r in records}

    total_work = 0.0
    total_overtime = 0.0
    total_pay = 0.0

    # 统计已有记录的
    for r in records:
        total_work += r.work_hours
        total_overtime += r.overtime_hours
        total_pay += r.overtime_pay

    # 补充无记录的工作日（默认8小时）
    current = cycle_start
    while current <= cycle_end:
        if current not in record_dates and get_day_type(current) == "workday":
            total_work += 8.0
        current += __import__("datetime").timedelta(days=1)

    workday_count = count_workdays_in_range(cycle_start, cycle_end)
    expected_hours = workday_count * 8

    return (
        f"📊 {nickname} {cycle_label}考勤汇总\n"
        f"📅 {cycle_start} ~ {cycle_end}\n"
        f"━━━━━━━━━━\n"
        f"📌 应出勤天数：{workday_count}天\n"
        f"📌 应出勤工时：{expected_hours:.0f}h\n"
        f"🕐 实际工时：{total_work:.1f}h\n"
        f"⏱ 加班时长：{total_overtime:.1f}h\n"
        f"💰 加班费合计：{total_pay:.2f}元\n"
        f"━━━━━━━━━━\n"
        f"💡 无打卡记录工作日按8h计"
    )
