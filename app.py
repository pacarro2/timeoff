from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar
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
    days = payload.get("days", [])

    today = date.today()
    window_start = today
    window_end = end_date

    pay_dates = build_pay_dates(next_pay_date, end_date, schedule)
    planned = build_planned_hours(days, window_start, window_end, include_weekends)

    balance = pto_today
    balances = {}
    accrued_total = 0.0
    planned_total = 0.0
    cursor = today
    while cursor <= end_date:
        if cursor in pay_dates:
            balance += accrual_rate
            accrued_total += accrual_rate
        if cursor in planned:
            balance -= planned[cursor]
            planned_total += planned[cursor]
        balances[cursor.isoformat()] = round(balance, 2)
        cursor += timedelta(days=1)

    return jsonify(
        {
            "balances": balances,
            "accrued_total": round(accrued_total, 2),
            "planned_total": round(planned_total, 2),
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
