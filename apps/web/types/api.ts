// Types mirror the FastAPI response models (apps/api/app/schemas). The API is the source of truth.

export type Role = "student" | "lecturer" | "super_admin";
export type SessionStatus = "scheduled" | "open" | "closed" | "cancelled";
export type AttendanceStatus = "verified" | "flagged" | "rejected" | "manual";
export type ManualReason = "no_phone" | "phone_dead" | "network_failure" | "app_problem" | "other";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Device {
  id: number;
  device_id: string;
  label: string | null;
  is_active: boolean;
  created_at: string;
}

export interface User {
  id: number;
  identifier: string;
  email: string | null;
  full_name: string;
  department: string | null;
  level: number | null;
  role: Role;
  is_active: boolean;
  linked: boolean;
  created_at: string;
}

export interface Me extends User {
  active_device: Device | null;
}

export interface Course {
  id: number;
  code: string;
  title: string;
  department: string | null;
}

export interface MyCourse extends Course {
  academic_year: string;
  semester: number;
  role_in_course: "lecturer" | "coordinator" | "student";
}

export interface Venue {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  default_radius_m: number;
}

export interface ClassSession {
  id: string;
  course_id: number;
  lecturer_id: number;
  venue_id: number | null;
  academic_year: string;
  semester: number;
  start_lat: number | null;
  start_lng: number | null;
  radius_m: number;
  slot_seconds: number;
  starts_at: string;
  ends_at: string;
  status: SessionStatus;
  course_code: string | null;
  venue_name: string | null;
  attendance_count: number | null;
}

export interface QRSeed {
  session_id: string;
  secret: string;
  starts_at: string;
  ends_at: string;
  slot_seconds: number;
  server_time: string;
}

export interface RosterEntry {
  student_id: number;
  identifier: string;
  full_name: string;
  status: AttendanceStatus | "not_marked";
  attendance_id: number | null;
  flag_reason: string | null;
  manual_reason: ManualReason | null;
  distance_m: number | null;
  received_at: string | null;
}

export interface SessionRoster {
  session_id: string;
  session_status: string;
  counts: Record<string, number>;
  entries: RosterEntry[];
}

export interface ManualMarkResult {
  marked: string[];
  already_present: string[];
  not_enrolled: string[];
}

export type ScanOutcome = "recorded" | "flagged" | "duplicate" | "rejected";

export interface ScanResult {
  client_uuid: string;
  outcome: ScanOutcome;
  code: string;
  message: string;
  attendance_status: AttendanceStatus | null;
  flag_reason: string | null;
  distance_m: number | null;
  session_id: string | null;
  course_code: string | null;
}

export interface ScanPayload {
  client_uuid: string;
  qr_payload: string;
  device_id: string;
  device_time: string;
  scan_lat: number | null;
  scan_lng: number | null;
  accuracy_m: number | null;
}

export interface MyAttendance {
  id: number;
  session_id: string;
  course_code: string;
  course_title: string;
  session_starts_at: string;
  status: AttendanceStatus;
  flag_reason: string | null;
  marked_manually: boolean;
  received_at: string;
}

export interface MyCourseSummary {
  course_id: number;
  course_code: string;
  course_title: string;
  sessions_counted: number;
  present: number;
  pending_review: number;
  percentage: number | null;
  eligible: boolean | null;
}

export interface StudentCourseRow {
  student_id: number;
  identifier: string;
  full_name: string;
  sessions_counted: number;
  present: number;
  pending_review: number;
  percentage: number | null;
  eligible: boolean | null;
}

export interface CourseReport {
  course_id: number;
  course_code: string;
  academic_year: string;
  semester: number;
  sessions_counted: number;
  sessions_open_or_scheduled: number;
  threshold_percent: number;
  rows: StudentCourseRow[];
}

export interface AdminOverview {
  users_by_role: Record<string, number>;
  courses: number;
  venues: number;
  sessions_by_status: Record<string, number>;
  attendance_by_status: Record<string, number>;
  audit_events_last_7_days: number;
}

export interface AuditEvent {
  id: number;
  actor_id: number | null;
  action: string;
  target_type: string;
  target_id: string;
  reason: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface Enrollment {
  student_id: number;
  identifier: string;
  full_name: string;
  academic_year: string;
  semester: number;
}

export interface Assignment {
  id: number;
  lecturer_id: number;
  lecturer_identifier: string;
  lecturer_name: string;
  course_id: number;
  academic_year: string;
  semester: number;
  is_coordinator: boolean;
}

export interface EnrollResult {
  enrolled: number;
  already_enrolled: number;
  unknown_identifiers: string[];
  not_students: string[];
}

export interface ImportResult {
  created: number;
  skipped_existing: number;
  errors: { row: number; message: string }[];
}
