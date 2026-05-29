"""核心业务工具函数"""
from datetime import datetime, date, timedelta, time
from calendar import monthrange
from config import Config
from models import Holiday


def get_attendance_cycle(today=None):
    """
    计算考勤周期: 上月26日 ~ 当月25日
    例如: 3.26 ~ 4.25 算4月
    返回: (cycle_start, cycle_end, cycle_label)
    """
    if today is None:
        today = date.today()

    if today.day >= 26:
        # 当前周期: 当月26日 ~ 下月25日
        cycle_start = date(today.year, today.month, 26)
        # 下个月
        if today.month == 12:
            next_month = 1
            next_year = today.year + 1
        else:
            next_month = today.month + 1
            next_year = today.year
        cycle_end = date(next_year, next_month, 25)
        cycle_label = f"{next_year}年{next_month}月"
    else:
        # 当前周期: 上月26日 ~ 当月25日
        cycle_end = date(today.year, today.month, 25)
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        cycle_start = date(prev_year, prev_month, 26)
        cycle_label = f"{today.year}年{today.month}月"

    return cycle_start, cycle_end, cycle_label


def get_cycle_by_label(cycle_label):
    """
    根据周期标签(如"2026年4月")反查周期范围
    """
    parts = cycle_label.replace("年", " ").replace("月", "").split()
    year = int(parts[0])
    month = int(parts[1])

    # 上月26日
    if month == 1:
        start = date(year - 1, 12, 26)
    else:
        start = date(year, month - 1, 26)
    end = date(year, month, 25)
    return start, end


def is_holiday(d):
    """判断是否为法定节假日"""
    return Holiday.query.filter_by(date=d).first() is not None


def is_weekend(d):
    """判断是否为周末"""
    return d.weekday() >= 5  # 5=周六, 6=周日


def is_workday(d):
    """判断是否为工作日（非周末且非法定节假日）"""
    return not is_weekend(d) and not is_holiday(d)


def get_day_type(d):
    """
    获取日期类型
    返回: 'workday' | 'weekend' | 'holiday'
    """
    if is_holiday(d):
        return "holiday"
    if is_weekend(d):
        return "weekend"
    return "workday"


def calculate_lunch_break(check_in, check_out):
    """
    计算午休时间重叠部分
    午休: 11:30 ~ 13:00 (1.5小时)
    返回实际午休重叠小时数
    """
    lunch_start = time(Config.LUNCH_START_HOUR, Config.LUNCH_START_MINUTE)
    lunch_end = time(Config.LUNCH_END_HOUR, Config.LUNCH_END_MINUTE)

    # 转换为同一天的时间范围
    ci_time = check_in.time()
    co_time = check_out.time()

    # 如果上班或下班在午休范围内，取交集
    overlap_start = max(ci_time, lunch_start)
    overlap_end = min(co_time, lunch_end)

    if overlap_start < overlap_end:
        delta = datetime.combine(date.today(), overlap_end) - datetime.combine(date.today(), overlap_start)
        return delta.total_seconds() / 3600
    return 0.0


def calculate_work_and_overtime(check_in, check_out, day_type):
    """
    计算工作时长和加班时长
    - 先算总工作时长 = 下班 - 上班
    - 扣除午休重叠时间
    - 工作日: 超出8小时部分为加班
    - 休息日/节假日: 全部计入加班

    返回: (work_hours, overtime_hours)
    """
    if check_in is None or check_out is None:
        return 0.0, 0.0

    total_seconds = (check_out - check_in).total_seconds()
    if total_seconds <= 0:
        return 0.0, 0.0

    total_hours = total_seconds / 3600

    # 扣除午休
    lunch_overlap = calculate_lunch_break(check_in, check_out)
    effective_hours = total_hours - lunch_overlap
    if effective_hours < 0:
        effective_hours = 0

    if day_type == "workday":
        # 工作日: 8小时内为正常工时, 超出为加班
        if effective_hours <= Config.DEFAULT_WORK_HOURS:
            return effective_hours, 0.0
        else:
            return Config.DEFAULT_WORK_HOURS, effective_hours - Config.DEFAULT_WORK_HOURS
    else:
        # 休息日/节假日: 全部算加班
        return 0.0, effective_hours


def calculate_overtime_pay(overtime_hours, day_type, hourly_rate):
    """
    计算加班费
    - 工作日: 1.5倍
    - 休息日: 2.0倍
    - 节假日: 3.0倍
    """
    if day_type == "workday":
        rate = Config.OVERTIME_RATE_WORKDAY
    elif day_type == "weekend":
        rate = Config.OVERTIME_RATE_WEEKEND
    else:  # holiday
        rate = Config.OVERTIME_RATE_HOLIDAY

    return overtime_hours * hourly_rate * rate


def get_hourly_rate(base_salary):
    """计算小时工资 = 底薪 / 21.75 / 8"""
    return base_salary / Config.STANDARD_WORK_DAYS / Config.DEFAULT_WORK_HOURS


def get_default_record_for_date(d, user):
    """
    获取某天的默认考勤记录（用于无打卡记录时的计算）
    工作日: 默认8小时正常出勤，无加班
    休息日/节假日: 默认休息，无出勤
    """
    from models import AttendanceRecord

    day_type = get_day_type(d)
    if day_type == "workday":
        check_in = datetime.combine(d, time(9, 0, 0))
        check_out = datetime.combine(d, time(17, 30, 0))
        record = AttendanceRecord(
            user_id=user.id,
            date=d,
            check_in=check_in,
            check_out=check_out,
            work_hours=8.0,
            overtime_hours=0.0,
            overtime_pay=0.0,
            is_manual=False,
            remark="默认出勤（无打卡记录）"
        )
    else:
        record = AttendanceRecord(
            user_id=user.id,
            date=d,
            check_in=None,
            check_out=None,
            work_hours=0.0,
            overtime_hours=0.0,
            overtime_pay=0.0,
            is_manual=False,
            remark="休息日"
        )
    return record


def count_workdays_in_range(start_date, end_date):
    """计算日期范围内的工作日天数"""
    count = 0
    current = start_date
    while current <= end_date:
        if is_workday(current):
            count += 1
        current += timedelta(days=1)
    return count
