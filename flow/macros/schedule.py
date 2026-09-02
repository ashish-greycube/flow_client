from __future__ import annotations

import datetime

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime


def validate_schedule_time(value) -> None:
	if value in (None, ""):
		return
	seconds = _time_to_seconds(value)
	if not 0 <= seconds < 24 * 60 * 60:
		frappe.throw(_("Schedule Time must be a valid time of day."))


def validate_cron_expression(value: str | None) -> None:
	from croniter import CroniterBadCronError, croniter

	if not (value or "").strip():
		frappe.throw(_("Cron Expression is required for Cron schedules."))
	try:
		croniter(value)
	except (CroniterBadCronError, ValueError) as exc:
		frappe.throw(_("Invalid cron expression: {0}").format(exc), title=_("Invalid Cron"))


def compute_next_run(
	frequency: str,
	schedule_time=None,
	from_dt=None,
	cron_expression: str | None = None,
) -> datetime.datetime:
	base = get_datetime(from_dt) if from_dt else now_datetime()
	if frequency == "Cron":
		validate_cron_expression(cron_expression)
		from croniter import croniter

		return croniter(cron_expression, base).get_next(datetime.datetime)
	seconds = _time_to_seconds(schedule_time)
	candidate = base.replace(
		hour=seconds // 3600,
		minute=(seconds % 3600) // 60,
		second=0,
		microsecond=0,
	)
	while candidate <= base:
		if frequency == "Weekly":
			candidate = add_to_date(candidate, days=7)
		elif frequency == "Monthly":
			candidate = add_to_date(candidate, months=1)
		else:
			candidate = add_to_date(candidate, days=1)
	return candidate


def _time_to_seconds(value) -> int:
	if value in (None, ""):
		return 9 * 60 * 60
	if isinstance(value, datetime.timedelta):
		return int(value.total_seconds())
	if isinstance(value, datetime.time):
		return value.hour * 3600 + value.minute * 60 + value.second
	try:
		parts = str(value).split(":")
		if len(parts) not in (2, 3):
			raise ValueError
		hour, minute = int(parts[0]), int(parts[1])
		second = int(float(parts[2])) if len(parts) == 3 else 0
		if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
			raise ValueError
		return hour * 3600 + minute * 60 + second
	except (TypeError, ValueError):
		frappe.throw(_("Schedule Time must be a valid time of day."))
	return 9 * 60 * 60
