"""
Media validation: allowed content types, file extensions, and URL format.
"""

import re
from typing import Tuple

# Allowed content types by category
ALLOWED_IMAGE_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
    }
)
ALLOWED_VIDEO_TYPES = frozenset(
    {
        "video/mp4",
        "video/webm",
        "video/quicktime",  # .mov
    }
)
ALLOWED_DOC_TYPES = frozenset(
    {
        "application/pdf",
    }
)
ALLOWED_OTHER_TYPES = frozenset(
    {
        "application/octet-stream",  # fallback
    }
)

TYPE_TO_CONTENT_TYPES = {
    "image": ALLOWED_IMAGE_TYPES,
    "video": ALLOWED_VIDEO_TYPES,
    "doc": ALLOWED_DOC_TYPES,
    "other": ALLOWED_IMAGE_TYPES
    | ALLOWED_VIDEO_TYPES
    | ALLOWED_DOC_TYPES
    | ALLOWED_OTHER_TYPES,
}

# Extensions allowed per type
EXT_BY_TYPE = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
    "video": {".mp4", ".webm", ".mov"},
    "doc": {".pdf"},
    "other": {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".mp4",
        ".webm",
        ".mov",
        ".pdf",
    },
}

# Max sizes (bytes) - 50MB for video, 10MB for image/doc
MAX_SIZE_IMAGE = 10 * 1024 * 1024
MAX_SIZE_VIDEO = 50 * 1024 * 1024
MAX_SIZE_DOC = 10 * 1024 * 1024

MAX_SIZE_BY_TYPE = {
    "image": MAX_SIZE_IMAGE,
    "video": MAX_SIZE_VIDEO,
    "doc": MAX_SIZE_DOC,
    "other": MAX_SIZE_VIDEO,
}

# Filename: alphanumeric, dots, hyphens, underscores. Reject path traversal.
_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,200}\.[a-zA-Z0-9]{1,10}$")


def validate_content_type(
    content_type: str | None, media_type: str
) -> Tuple[bool, str | None]:
    """
    Validate content_type for uploads. Returns (valid, error_message).
    """
    if not content_type or not content_type.strip():
        return True, None  # optional; storage may infer
    ct = content_type.strip().lower().split(";")[0].strip()
    allowed = TYPE_TO_CONTENT_TYPES.get(media_type, TYPE_TO_CONTENT_TYPES["other"])
    if ct not in allowed:
        return (
            False,
            f"content_type '{content_type}' not allowed for type '{media_type}'",
        )
    return True, None


def validate_filename(filename: str | None, media_type: str) -> Tuple[bool, str | None]:
    """
    Validate filename extension and format. Returns (valid, error_message).
    """
    if not filename or not filename.strip():
        return False, "filename required"
    fn = filename.strip()
    if ".." in fn or "/" in fn or "\\" in fn:
        return False, "invalid filename"
    if not _FILENAME_RE.match(fn):
        return (
            False,
            "filename must be alphanumeric with valid extension (e.g. photo.jpg)",
        )
    ext = "." + fn.rsplit(".", 1)[-1].lower()
    allowed = EXT_BY_TYPE.get(media_type, EXT_BY_TYPE["other"])
    if ext not in allowed:
        return False, f"extension {ext} not allowed for type '{media_type}'"
    return True, None


def validate_size(size_bytes: int | None, media_type: str) -> Tuple[bool, str | None]:
    """
    Validate file size. Returns (valid, error_message).
    """
    if size_bytes is None:
        return True, None
    if size_bytes < 0:
        return False, "size_bytes must be non-negative"
    max_sz = MAX_SIZE_BY_TYPE.get(media_type, MAX_SIZE_VIDEO)
    if size_bytes > max_sz:
        return (
            False,
            f"file too large (max {max_sz // (1024 * 1024)}MB for {media_type})",
        )
    return True, None


def infer_media_type_from_content_type(content_type: str | None) -> str:
    """
    Infer media type from content_type for validation.
    """
    if not content_type:
        return "other"
    ct = content_type.strip().lower().split(";")[0].strip()
    if ct in ALLOWED_IMAGE_TYPES:
        return "image"
    if ct in ALLOWED_VIDEO_TYPES:
        return "video"
    if ct in ALLOWED_DOC_TYPES:
        return "doc"
    return "other"


def infer_media_type_from_filename(filename: str | None) -> str:
    """
    Infer media type from filename extension.
    """
    if not filename or "." not in filename:
        return "other"
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext in EXT_BY_TYPE["image"]:
        return "image"
    if ext in EXT_BY_TYPE["video"]:
        return "video"
    if ext in EXT_BY_TYPE["doc"]:
        return "doc"
    return "other"
