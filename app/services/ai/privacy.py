import re

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:0\d{1,2}[-.\s]?)?\d{3,4}[-.\s]?\d{4}(?!\d)"
)


def mask_personal_data(text: str) -> str:
    masked = EMAIL_PATTERN.sub("[email]", text)
    return PHONE_PATTERN.sub("[phone]", masked)
