"""
Fact Checker — verifies generated content claims against source data.

CRITICAL: Blocks document output if any claim is unverifiable.
False declarations in public grant applications carry criminal liability
under D.P.R. 445/2000 arts. 76, 483 c.p., 495 c.p.

Usage:
    from engine.generators.fact_checker import check_claims, FactCheckResult

    result = check_claims(generated_content.claims, company_profile, skills_matrix)
    if not result.all_verified:
        raise DocumentBlockedError(result.unverified_claims)
"""
from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from engine.generators.content_generator import ClaimRecord

logger = logging.getLogger(__name__)

CONTEXT_DIR = Path(__file__).parent.parent.parent / "context"


class DocumentBlockedError(Exception):
    """Raised when fact checker blocks document due to unverified claims."""

    def __init__(self, unverified: list[ClaimRecord]):
        self.unverified = unverified
        claims_str = "\n".join(f"  - {c.claim} (source: {c.source})" for c in unverified)
        super().__init__(
            f"Document blocked: {len(unverified)} unverifiable claim(s):\n{claims_str}\n"
            "Human intervention required before document can be used."
        )


@dataclass
class FactCheckResult:
    """Result of fact checking a list of claims."""
    total_claims: int
    verified_count: int
    unverified_count: int
    verified_claims: list[ClaimRecord] = field(default_factory=list)
    unverified_claims: list[ClaimRecord] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def all_verified(self) -> bool:
        return self.unverified_count == 0

    @property
    def verification_rate(self) -> float:
        if self.total_claims == 0:
            return 1.0
        return self.verified_count / self.total_claims

    def summary(self) -> str:
        status = "✅ PASS" if self.all_verified else "❌ BLOCKED"
        return (
            f"Fact Check {status}: {self.verified_count}/{self.total_claims} claims verified "
            f"({self.verification_rate:.0%})"
        )


def _flatten_dict(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dict to {path: value} for lookup."""
    result = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_dict(v, full_key))
        elif isinstance(v, list):
            # Store both the list as string and individual items
            result[full_key] = json.dumps(v, ensure_ascii=False)
            for i, item in enumerate(v):
                if isinstance(item, (str, int, float)):
                    result[f"{full_key}[{i}]"] = str(item)
                elif isinstance(item, dict):
                    result.update(_flatten_dict(item, f"{full_key}[{i}]"))
        else:
            result[full_key] = str(v) if v is not None else ""
    return result


def _load_source_data() -> dict[str, dict[str, str]]:
    """Load and flatten all source JSON files for verification."""
    sources: dict[str, dict[str, str]] = {}

    for filename in ["company_profile.json", "skills_matrix.json"]:
        path = CONTEXT_DIR / filename
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sources[filename] = _flatten_dict(data)
                logger.debug(f"Loaded {len(sources[filename])} fields from {filename}")
            except Exception as e:
                logger.error(f"Failed to load {filename}: {e}")

    return sources


def _verify_claim(claim: ClaimRecord, sources: dict[str, dict[str, str]]) -> bool:
    """
    Verify a single claim against source data.

    Verification logic:
    1. Parse claim.source to find file → field path
    2. Look up value in flattened source dict
    3. Check that claim.value_used appears in the found value
    """
    if not claim.source or not claim.value_used:
        # Cannot verify claims without source or value
        logger.warning(f"Unverifiable claim (no source/value): {claim.claim[:80]}")
        return False

    # Parse source: "company_profile.json → field.path"
    source_parts = claim.source.split("→")
    if len(source_parts) < 2:
        logger.warning(f"Malformed source ref: {claim.source}")
        return False

    filename = source_parts[0].strip()
    field_path = source_parts[1].strip()

    # Map to loaded source
    source_data = sources.get(filename, {})
    if not source_data:
        logger.warning(f"Source file not loaded: {filename}")
        return False

    # Look up field (exact or prefix match)
    found_value = source_data.get(field_path)

    if found_value is None:
        # Try case-insensitive partial key match
        field_lower = field_path.lower()
        for k, v in source_data.items():
            if k.lower() == field_lower or k.lower().endswith(f".{field_lower}"):
                found_value = v
                break

    if found_value is None:
        logger.warning(f"Field not found in source: {filename} → {field_path}")
        return False

    # Check value used is present in source value
    # Normalize for comparison (strip, lowercase)
    value_clean = claim.value_used.strip().lower()
    found_clean = found_value.strip().lower()

    # Accept if value appears anywhere in the source value string
    if value_clean in found_clean:
        return True

    # Also accept if source value appears in claim value (abbreviations)
    if found_clean in value_clean:
        return True

    # Try numeric match (remove formatting)
    try:
        if re.sub(r"[^\d]", "", value_clean) and re.sub(r"[^\d]", "", value_clean) in re.sub(r"[^\d]", "", found_clean):
            return True
    except Exception:
        pass

    logger.warning(
        f"Claim value mismatch: expected '{value_clean}' from {field_path}, "
        f"found '{found_clean[:80]}'"
    )
    return False


def check_claims(
    claims: list[ClaimRecord],
    company_profile: dict[str, Any] | None = None,
    skills_matrix: dict[str, Any] | None = None,
) -> FactCheckResult:
    """
    Verify all claims against source data.

    Args:
        claims: List of ClaimRecord from content_generator
        company_profile: Optional pre-loaded profile (if None, loads from file)
        skills_matrix: Optional pre-loaded matrix (if None, loads from file)

    Returns:
        FactCheckResult with verification status for each claim
    """
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    sources = _load_source_data()

    # If pre-loaded data provided, merge into sources
    if company_profile:
        sources["company_profile.json"] = {
            **sources.get("company_profile.json", {}),
            **_flatten_dict(company_profile),
        }
    if skills_matrix:
        sources["skills_matrix.json"] = {
            **sources.get("skills_matrix.json", {}),
            **_flatten_dict(skills_matrix),
        }

    verified: list[ClaimRecord] = []
    unverified: list[ClaimRecord] = []

    for claim in claims:
        is_valid = _verify_claim(claim, sources)
        claim.verified = is_valid
        claim.verified_at = now

        if is_valid:
            verified.append(claim)
            logger.debug(f"✅ Verified: {claim.claim[:60]}")
        else:
            unverified.append(claim)
            logger.warning(f"❌ Unverified: {claim.claim[:60]}")

    result = FactCheckResult(
        total_claims=len(claims),
        verified_count=len(verified),
        unverified_count=len(unverified),
        verified_claims=verified,
        unverified_claims=unverified,
        checked_at=now,
    )

    logger.info(result.summary())
    return result


def assert_all_verified(
    claims: list[ClaimRecord],
    company_profile: dict[str, Any] | None = None,
    skills_matrix: dict[str, Any] | None = None,
) -> FactCheckResult:
    """
    Like check_claims() but raises DocumentBlockedError if any claim fails.
    Use this before generating final (non-draft) documents.

    Raises:
        DocumentBlockedError: If any claim cannot be verified
    """
    result = check_claims(claims, company_profile, skills_matrix)
    if not result.all_verified:
        raise DocumentBlockedError(result.unverified_claims)
    return result
