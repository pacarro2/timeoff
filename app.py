from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar
import os
from typing import List, Dict, Any

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def step_date(current: date, schedule: str) -> date:
    if schedule == "weekly":
        return current + timedelta(days=7)
    if schedule == "biweekly":
        return current + timedelta(days=14)
    if schedule == "monthly":
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(current.day, last_day)
        return date(year, month, day)
    if schedule == "semimonthly":
        if current.day == 15:
            last_day = calendar.monthrange(current.year, current.month)[1]
            return date(current.year, current.month, last_day)
        year = current.year + (1 if current.month == 12 else 0)
        month = 1 if current.month == 12 else current.month + 1
        return date(year, month, 15)
    return current


def build_pay_dates(next_pay_date: date, end_date: date, schedule: str) -> set[date]:
    if next_pay_date > end_date:
        return set()
    pay_dates = []
    cursor = next_pay_date
    while cursor <= end_date:
        pay_dates.append(cursor)
        cursor = step_date(cursor, schedule)
    return set(pay_dates)


def build_planned_hours(
    days: List[Dict[str, Any]],
    window_start: date,
    window_end: date,
    include_weekends: bool,
) -> Dict[date, float]:
    planned = {}
    for item in days:
        if "date" not in item:
            continue
        try:
            day = parse_date(item["date"])
        except (ValueError, TypeError):
            continue
        if day < window_start or day > window_end:
            continue
        if not include_weekends and day.weekday() >= 5:
            continue
        hours_value = item.get("hours", 0)
        try:
            hours = float(hours_value)
        except (TypeError, ValueError):
            hours = 0.0
        planned[day] = planned.get(day, 0) + hours
    return planned


def is_nine_eighty_off_friday(day: date, anchor_friday: date) -> bool:
    if day.weekday() != 4:
        return False
    weeks = (day - anchor_friday).days // 7
    return weeks % 2 == 1


def workday_hours(day: date, nine_eighty: bool, anchor_friday: date | None) -> int:
    weekday = day.weekday()
    if weekday >= 5:
        return 0
    if not nine_eighty:
        return 8
    if weekday <= 3:
        return 9
    if anchor_friday and is_nine_eighty_off_friday(day, anchor_friday):
        return 0
    return 8


def holiday_deduction_hours(
    day: date,
    base_hours: float,
    nine_eighty: bool,
    anchor_friday: date | None,
) -> float:
    if base_hours <= 0:
        return 0.0
    work_hours = workday_hours(day, nine_eighty, anchor_friday)
    if work_hours == 0:
        return 0.0
    extra_hour = 1 if nine_eighty and work_hours == 9 else 0
    return base_hours + extra_hour


def normalize_anchor_friday(anchor: date) -> date:
    if anchor.weekday() == 4:
        return anchor
    days_ahead = (4 - anchor.weekday()) % 7
    return anchor + timedelta(days=days_ahead)


def observed_date(holiday: date) -> date:
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    days_ahead = (weekday - first.weekday()) % 7
    return first + timedelta(days=days_ahead + 7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    days_back = (last.weekday() - weekday) % 7
    return last - timedelta(days=days_back)


def federal_holidays(window_start: date, window_end: date) -> Dict[date, str]:
    holidays = {}
    for year in range(window_start.year - 1, window_end.year + 2):
        fixed = [
            (date(year, 1, 1), "New Year's Day"),
            (date(year, 6, 19), "Juneteenth"),
            (date(year, 7, 4), "Independence Day"),
            (date(year, 11, 11), "Veterans Day"),
            (date(year, 12, 25), "Christmas Day"),
        ]
        floating = [
            (nth_weekday(year, 1, 0, 3), "Martin Luther King Jr. Day"),
            (nth_weekday(year, 2, 0, 3), "Presidents' Day"),
            (last_weekday(year, 5, 0), "Memorial Day"),
            (nth_weekday(year, 9, 0, 1), "Labor Day"),
            (nth_weekday(year, 10, 0, 2), "Columbus Day"),
            (nth_weekday(year, 11, 3, 4), "Thanksgiving Day"),
        ]
        for holiday, name in fixed:
            observed = observed_date(holiday)
            holidays[observed] = name
        for holiday, name in floating:
            holidays[holiday] = name
    return {day: name for day, name in holidays.items() if window_start <= day <= window_end}


def normalize_holiday_payload(
    payload: List[Dict[str, Any]] | None,
    window_start: date,
    window_end: date,
) -> List[Dict[str, Any]]:
    if not payload:
        return []
    normalized = []
    for item in payload:
        raw_date = item.get("date")
        if not raw_date:
            continue
        try:
            day = parse_date(raw_date)
        except (ValueError, TypeError):
            continue
        if day < window_start or day > window_end:
            continue
        name = item.get("name") or "Holiday"
        try:
            hours = float(item.get("hours", 8))
        except (TypeError, ValueError):
            hours = 8.0
        normalized.append({"date": day, "name": name, "hours": hours})
    return normalized


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/forecast", methods=["POST"])
def forecast():
    payload = request.get_json(force=True)
    pto_today = float(payload.get("pto_today", 0))
    accrual_rate = float(payload.get("accrual_rate", 0))
    schedule = payload.get("schedule", "biweekly")
    next_pay_date = parse_date(payload.get("next_pay_date"))
    end_date = parse_date(payload.get("end_date"))
    include_weekends = bool(payload.get("include_weekends", False))
    nine_eighty = bool(payload.get("nine_eighty", False))
    nine_eighty_anchor = payload.get("nine_eighty_anchor")
    days = payload.get("days", [])
    holidays_payload = payload.get("holidays")

    today = date.today()
    window_start = today
    window_end = end_date

    anchor_friday = None
    if nine_eighty and nine_eighty_anchor:
        anchor_friday = normalize_anchor_friday(parse_date(nine_eighty_anchor))
    pay_dates = build_pay_dates(next_pay_date, end_date, schedule)
    planned = build_planned_hours(days, window_start, window_end, include_weekends)

    normalized_holidays = normalize_holiday_payload(holidays_payload, window_start, window_end)
    if holidays_payload is None:
        holidays = federal_holidays(window_start, window_end)
        normalized_holidays = [
            {"date": day, "name": name, "hours": 8.0} for day, name in holidays.items()
        ]

    holiday_hours = {}
    for holiday in normalized_holidays:
        day = holiday["date"]
        base_hours = holiday["hours"]
        deducted = holiday_deduction_hours(day, base_hours, nine_eighty, anchor_friday)
        if deducted == 0:
            continue
        holiday_hours[day] = holiday_hours.get(day, 0) + deducted

    balance = pto_today
    balances = {}
    accrued_total = 0.0
    planned_total = 0.0
    holiday_total = 0.0
    cursor = today
    while cursor <= end_date:
        if cursor in pay_dates:
            balance += accrual_rate
            accrued_total += accrual_rate
        if cursor in planned:
            balance -= planned[cursor]
            planned_total += planned[cursor]
        if cursor in holiday_hours:
            balance -= holiday_hours[cursor]
            holiday_total += holiday_hours[cursor]
        balances[cursor.isoformat()] = round(balance, 2)
        cursor += timedelta(days=1)

    return jsonify(
        {
            "balances": balances,
            "accrued_total": round(accrued_total, 2),
            "planned_total": round(planned_total, 2),
            "holiday_total": round(holiday_total, 2),
            "holidays": [
                {
                    "date": holiday["date"].isoformat(),
                    "name": holiday["name"],
                    "hours": holiday["hours"],
                }
                for holiday in normalized_holidays
            ],
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug)
