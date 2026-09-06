"""Application identifiers: slugs, scoped Application node ids, seed ids."""

from __future__ import annotations

import re

SEED_APPLICATION_ID = "sunrise-coffee"
SEED_APPLICANT_NAME = "Sunrise Coffee Roasters LLC"


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w]+", "-", str(value).strip().lower()).strip("-")
    return slug or "application"


def reason_subject(applicant_name: str) -> str:
    subject = re.sub(r"[^A-Za-z0-9]", "", applicant_name)
    return subject or "Applicant"


def application_node_id(application_id: str) -> str:
    return f"{application_id}::application"
