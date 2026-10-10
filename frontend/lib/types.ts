// Mirrors backend Pydantic schemas field-for-field. Decimal fields (score,
// total_marks, positive_marks, negative_marks, average_score) serialize as
// JSON strings (confirmed against FastAPI's actual output), not numbers -
// keep them typed as `string` here and format for display at the point of
// rendering, never by changing the type.

export type UserRole = "student" | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Subject {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Topic {
  id: number;
  subject_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export type ExamTier = "Tier 1" | "Tier 2";

export interface Exam {
  id: number;
  year: number;
  tier: ExamTier;
  shift: number;
  exam_date: string | null;
  duration_minutes: number;
  total_questions: number;
  total_marks: string;
  is_published: boolean;
  source_pdf_name: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export type AttemptType = "full_paper" | "topic_practice" | "section_practice";
export type AttemptStatus = "in_progress" | "submitted" | "expired";
export type OptionLabel = "A" | "B" | "C" | "D";

export interface Attempt {
  id: number;
  exam_id: number | null;
  topic_id: number | null;
  subject_id: number | null;
  attempt_type: AttemptType;
  status: AttemptStatus;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  score: string | null;
  correct_count: number | null;
  wrong_count: number | null;
  unanswered_count: number | null;
  created_at: string;
}

export interface OptionForAttempt {
  label: string;
  text: string | null;
  image_url: string | null;
}

// Deliberately has no correct_option / solution_text / is_correct - the
// backend never sends them for an active attempt, so the type doesn't
// either. This makes "never display correct answers during an active
// attempt" a compile-time guarantee, not just a runtime convention.
export interface QuestionForAttempt {
  question_id: number;
  order_index: number;
  question_number: number | null;
  question_text: string;
  question_image_url: string | null;
  passage_text: string | null;
  positive_marks: string;
  negative_marks: string;
  options: OptionForAttempt[];
  selected_option: string | null;
  marked_for_review: boolean;
}

export interface AnswerPublic {
  question_id: number;
  selected_option: string | null;
  marked_for_review: boolean;
  answered_at: string | null;
}

export interface AttemptResult {
  attempt_id: number;
  exam_id: number | null;
  status: string;
  total_questions: number;
  attempted_count: number;
  correct_count: number;
  wrong_count: number;
  unanswered_count: number;
  score: string;
  accuracy: number;
  time_taken_seconds: number;
  started_at: string;
  submitted_at: string;
}

// Post-submission only - this is where correct_option/solution_text are
// allowed to appear, gated entirely by the backend's own 409-until-
// submitted rule.
export interface ReviewItem {
  question_id: number;
  order_index: number;
  question_number: number | null;
  question_text: string;
  question_image_url: string | null;
  passage_text: string | null;
  options: OptionForAttempt[];
  selected_option: string | null;
  correct_option: string | null;
  is_correct: boolean | null;
  solution_text: string | null;
}

export interface AttemptHistoryItem {
  attempt_id: number;
  attempt_type: AttemptType;
  status: AttemptStatus;
  exam_id: number | null;
  exam_year: number | null;
  exam_tier: string | null;
  exam_shift: number | null;
  topic_id: number | null;
  topic_name: string | null;
  subject_name: string | null;
  started_at: string;
  submitted_at: string | null;
  score: string | null;
  correct_count: number | null;
  wrong_count: number | null;
  unanswered_count: number | null;
}

export interface AttemptHistoryPage {
  items: AttemptHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AttemptHistorySummary {
  total_attempts: number;
  total_questions: number;
  total_correct: number;
  total_wrong: number;
  total_unanswered: number;
  average_score: string;
  accuracy: number;
  total_time_seconds: number;
}

export interface SectionPerformance {
  subject_id: number;
  subject_name: string;
  total_questions: number;
  correct_count: number;
  wrong_count: number;
  unanswered_count: number;
  accuracy: number;
}

// --- Admin-only (Phase 8) ---
// QuestionPublic from the admin API - a richer shape than the student-facing
// QuestionForAttempt: this one legitimately includes correct_option,
// solution_text and status, because admins are supposed to see them.

export type QuestionStatus = "draft" | "pending_review" | "published" | "archived";

export interface QuestionOption {
  id: number;
  label: string;
  text: string | null;
  image_url: string | null;
}

export interface Question {
  id: number;
  exam_id: number | null;
  subject_id: number | null;
  topic_id: number | null;
  question_number: number | null;
  question_text: string;
  question_image_url: string | null;
  passage_text: string | null;
  correct_option: string | null;
  positive_marks: string;
  negative_marks: string;
  solution_text: string | null;
  status: QuestionStatus;
  import_batch_id: number | null;
  created_at: string;
  updated_at: string;
  options: QuestionOption[];
}

// --- Admin-only (Phase 9: PDF import) ---

export type ImportStatus = "processing" | "pending_review" | "published" | "failed";

export interface ImportBatchSummary {
  id: number;
  filename: string;
  uploaded_by: number | null;
  exam_id: number | null;
  status: ImportStatus;
  error_log: string | null;
  created_at: string;
  updated_at: string;
  question_count: number;
  pending_review_count: number;
  published_count: number;
  missing_correct_option_count: number;
}
