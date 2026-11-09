from pydantic import BaseModel


class StudentCourseRow(BaseModel):
    student_id: int
    identifier: str
    full_name: str
    sessions_counted: int
    present: int
    pending_review: int
    percentage: float | None
    eligible: bool | None


class CourseReport(BaseModel):
    course_id: int
    course_code: str
    academic_year: str
    semester: int
    sessions_counted: int
    sessions_open_or_scheduled: int
    threshold_percent: float
    rows: list[StudentCourseRow]


class MyCourseSummary(BaseModel):
    course_id: int
    course_code: str
    course_title: str
    sessions_counted: int
    present: int
    pending_review: int
    percentage: float | None
    eligible: bool | None


class AdminOverview(BaseModel):
    users_by_role: dict[str, int]
    courses: int
    venues: int
    sessions_by_status: dict[str, int]
    attendance_by_status: dict[str, int]
    audit_events_last_7_days: int
