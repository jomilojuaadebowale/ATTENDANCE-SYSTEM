from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    title: str = Field(min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=120)


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=120)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    department: str | None


class TermParams(BaseModel):
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}/\d{4}$")
    semester: int | None = Field(default=None, ge=1, le=2)


class EnrollRequest(TermParams):
    identifiers: list[str] = Field(min_length=1, max_length=2000, description="Matric numbers")


class EnrollResult(BaseModel):
    enrolled: int
    already_enrolled: int
    unknown_identifiers: list[str]
    not_students: list[str]


class EnrollmentOut(BaseModel):
    student_id: int
    identifier: str
    full_name: str
    academic_year: str
    semester: int


class AssignmentCreate(TermParams):
    lecturer_identifier: str = Field(min_length=2, max_length=50)
    is_coordinator: bool = False


class AssignmentOut(BaseModel):
    id: int
    lecturer_id: int
    lecturer_identifier: str
    lecturer_name: str
    course_id: int
    academic_year: str
    semester: int
    is_coordinator: bool


class MyCourseOut(CourseOut):
    academic_year: str
    semester: int
    role_in_course: str  # "lecturer" | "coordinator" | "student"
