import { PageHeader } from "@/components/page-header";
import { CourseAdmin } from "@/features/course-admin";

export default function CoursesPage() {
  return (
    <>
      <PageHeader title="Courses, lecturers and enrolments" description="Lecturers can only run attendance for courses assigned to them." />
      <CourseAdmin />
    </>
  );
}
