import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class QuestionStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ImportStatus(str, enum.Enum):
    PROCESSING = "processing"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    FAILED = "failed"


class AttemptType(str, enum.Enum):
    FULL_PAPER = "full_paper"
    TOPIC_PRACTICE = "topic_practice"
    SECTION_PRACTICE = "section_practice"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"
