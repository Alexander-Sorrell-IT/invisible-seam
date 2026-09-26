from __future__ import annotations

import re
from pathlib import Path

from invisible_seam.extractors.config_extractor import json_schema_default
from invisible_seam.models import Claim, Seam, SeamCandidate

_SEAM_COUNTER: list[int] = [1]

_AMBIGUOUS_PATTERNS = re.compile(r"\b(might|may|optionally|possibly|sometimes)\b", re.IGNORECASE)


def classify(candidate: SeamCandidate, claim: Claim) -> Seam:
    """Classifies a conflict as FIXABLE or PARADOX. Returns a Seam."""
    seam_id = f"S{_SEAM_COUNTER[0]:03d}"
    _SEAM_COUNTER[0] += 1

    assertion_a = f"{claim.claim}"
    assertion_b = f"{candidate.behavior}"

    # determine classification
    if claim.type == "type-hint":
        classification = "FIXABLE"
        question = None
    elif claim.type == "config-fallback":
        # PARADOX: if the claim contains "default" (schema provides a default) AND
        # a separate required-claim exists for the same field — detected by matching
        # field name in both assertion_a and assertion_b
        field_match = re.search(r"'(\w+)'", claim.claim)
        field = field_match.group(1) if field_match else ""
        is_required_claim = "requires" in claim.claim.lower()
        is_default_claim = "default" in claim.claim.lower()
        # A required-claim paired with a default value in the schema = PARADOX
        # because you can't be both required and have a default
        schema_has_default, schema_value = (
            json_schema_default(claim.source_file, field) if field else (False, None)
        )
        if is_required_claim and schema_has_default:
            # the contradiction is inside the spec itself: no code change can settle it
            classification = "PARADOX"
            question = (
                f"The schema marks '{field}' required AND gives it a default of "
                f"{schema_value!r}. Must callers always supply '{field}', or may it be omitted?"
            )
        else:
            classification = "FIXABLE"
            question = None
    elif claim.type == "doc-code":
        if _AMBIGUOUS_PATTERNS.search(claim.claim):
            classification = "PARADOX"
            question = (
                f"The documentation at {claim.source_file.name}:{claim.source_line} is ambiguous — "
                f"does '{claim.claim}' represent a guarantee or a suggestion?"
            )
        else:
            classification = "FIXABLE"
            question = None
    else:
        classification = "FIXABLE"
        question = None

    return Seam(
        id=seam_id,
        classification=classification,  # type: ignore[arg-type]
        assertion_a=assertion_a,
        source_a=claim.source_file,
        line_a=claim.source_line,
        assertion_b=assertion_b,
        source_b=candidate.behavior_file,
        line_b=candidate.behavior_line,
        check=None,
        verdict="CERTAIN",
        question=question,
    )
