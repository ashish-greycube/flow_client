"""Ready-made Flow Macros. They run on a prebuilt agent, ship unscheduled, and only read data."""

ATTENDANCE_AGENT = "Attendance & Leave Integrity Auditor"

ATTENDANCE_AUDIT_STEPS = [
	{
		"label": "Yesterday's attendance overview",
		"prompt": (
			"Audit attendance for yesterday. First check whether yesterday was a holiday in each "
			"company's default Holiday List; if it was a holiday for every company, reply "
			"'Yesterday was a holiday - no audit needed' and stop.\n"
			"Otherwise, for active employees (joined on or before yesterday and not relieved before it), "
			"give these key details per company and department:\n"
			"- total active employees\n"
			"- submitted Attendance counts by status: Present, Absent, On Leave, Half Day, Work From Home\n"
			"- present %\n"
			"- employees with no Attendance marked at all\n"
			"Show it as a table. Remember these numbers for the later steps."
		),
	},
	{
		"label": "Late arrivals and early exits",
		"prompt": (
			"From yesterday's submitted Attendance, list employees with Late Entry or Early Exit ticked. "
			"Show employee, department, shift, and check-in/check-out times from Employee Checkin if "
			"available. Flag anyone who was both late and left early. If more than 50 rows, show counts "
			"per department and the first 50 names. If nobody was late or early, say 'No late or early cases'."
		),
	},
	{
		"label": "Absent without leave",
		"prompt": (
			"Find employees who were away yesterday without approved leave, in three groups:\n"
			"1. Absent, no leave: Attendance status Absent and no approved Leave Application covering yesterday.\n"
			"2. Not marked, no leave: no Attendance at all (from the first step) and no approved Leave "
			"Application. Skip employees whose own Holiday List marks yesterday as a holiday.\n"
			"3. Leave pending approval: a Leave Application covering yesterday exists but is still Open.\n"
			"Show employee, department and reporting manager for each. If more than 50 rows in a group, "
			"show counts per department and the first 50 names. If a group is empty, say 'None'."
		),
	},
	{
		"label": "Summary for HR",
		"prompt": (
			"Write a short HR summary of yesterday using the previous steps:\n"
			"- one line on overall attendance (headcount, present %)\n"
			"- counts of late/early, absent without leave, not marked, and pending leave\n"
			"- a 'Follow up today' list, most urgent first: absent without leave, then not marked, "
			"then pending approvals\n"
			"Keep it under 15 lines. Group by company if there is more than one."
		),
	},
]

DEFAULT_MACROS = [
	{
		"doc": {
			"doctype": "Flow Macro",
			"macro_name": "Yesterday's Attendance Audit",
			"description": (
				"Daily HR check of yesterday's attendance: overview, late/early cases, absent without "
				"leave, and a follow-up summary. Read-only. Best run around 10:00, after auto-attendance."
			),
			"agent": ATTENDANCE_AGENT,
			"stop_on_error": 1,
			"steps": ATTENDANCE_AUDIT_STEPS,
            "enabled": 0,
			"auto_approve": 1
		},
		"match": ["macro_name"],
		"requires": [("Flow Agent", ATTENDANCE_AGENT)],
	},
]
