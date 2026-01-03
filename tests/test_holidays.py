from datetime import date

from app import (
    federal_holidays,
    holiday_deduction_hours,
    normalize_anchor_friday,
    normalize_holiday_payload,
    filter_holidays_in_window,
    workday_hours,
)


def test_federal_holidays_observed_new_years():
    holidays = federal_holidays(date(2022, 12, 30), date(2023, 1, 4))
    assert date(2023, 1, 2) in holidays
    assert holidays[date(2023, 1, 2)] == "New Year's Day"


def test_normalize_anchor_friday_moves_to_friday():
    anchor = normalize_anchor_friday(date(2024, 5, 15))  # Wednesday
    assert anchor.weekday() == 4
    assert anchor == date(2024, 5, 17)


def test_workday_hours_nine_eighty_cycle():
    anchor = date(2024, 5, 3)  # Friday, 8-hour day
    off_friday = date(2024, 5, 10)
    assert workday_hours(anchor, True, anchor) == 8
    assert workday_hours(off_friday, True, anchor) == 0
    assert workday_hours(date(2024, 5, 6), True, anchor) == 9


def test_holiday_deduction_adds_extra_hour_on_nine_hour_day():
    anchor = date(2024, 5, 3)
    nine_hour_day = date(2024, 5, 6)  # Monday
    assert holiday_deduction_hours(nine_hour_day, 8, True, anchor) == 1


def test_holiday_deduction_skips_off_friday():
    anchor = date(2024, 5, 3)
    off_friday = date(2024, 5, 10)
    assert holiday_deduction_hours(off_friday, 8, True, anchor) == 0


def test_holiday_deduction_skips_when_nine_eighty_disabled():
    anchor = date(2024, 5, 3)
    nine_hour_day = date(2024, 5, 6)
    assert holiday_deduction_hours(nine_hour_day, 8, False, anchor) == 0


def test_normalize_holiday_payload_filters_outside_window():
    payload = [
        {"date": "2024-05-01", "name": "Test", "hours": 8},
        {"date": "2024-06-01", "name": "Out of range", "hours": 8},
    ]
    normalized = normalize_holiday_payload(payload)
    filtered = filter_holidays_in_window(normalized, date(2024, 5, 1), date(2024, 5, 31))
    assert len(filtered) == 1
    assert filtered[0]["date"] == date(2024, 5, 1)
