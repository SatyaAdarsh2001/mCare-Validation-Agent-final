# ============================================================
# AGENT 4: Correction Agent
# ============================================================
# PURPOSE:
#   Takes the list of issues from Agent 3 and attempts to
#   fix them. Uses two-tier strategy:
#
#   TIER 1 - Deterministic Auto-Fix (no AI):
#     - Whitespace in numeric fields → strip it
#     - Date format inconsistencies → standardize
#     - These are 100% safe to auto-apply
#
#   TIER 2 - AI Suggestions (requires human review):
#     - Empty required textarea/clinical fields
#     - AI reads context from other answers and suggests
#       professionally written clinical text
#     - NEVER auto-filled → Care Manager must review
#     - NO PHI sent to AI (anonymized context only)
#
# ANALOGY FOR PPT:
#   Think of this as a "smart assistant" sitting next to
#   the Care Manager. For simple mistakes like extra spaces
#   it fixes silently. For empty clinical fields it says
#   "Here's a suggested response based on what you filled
#   elsewhere — please review and approve."
#
# INPUT:  issues list from Agent 3 + IntakeContext
# OUTPUT: updated issues list + corrected_answers dict
# ============================================================

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Clinical Field Keywords ─────────────────────────────────
# These textarea fields need AI suggestions when empty
# Identified by keywords in their question names
CLINICAL_KEYWORDS = [
    "conclusion", "summary", "barrier", "concern",
    "rationale", "plan", "goal", "comment", "observation",
    "assessment", "note", "recommendation", "intervention",
    "skill", "strain", "discharge", "additional"
]


class CorrectionAgent:

    def __init__(self, ai_service):
        """
        ai_service is injected from app.py
        This is called Dependency Injection — makes testing easy
        and allows swapping AI providers without changing this file
        """
        self.ai_service = ai_service

    def process(
        self,
        issues: list,
        intake_context: dict
    ) -> tuple:
        """
        Main method called by app.py
        Returns: (updated_issues, corrected_answers)

        corrected_answers dict format:
        { "Q1": "corrected value", "Q8": "corrected value" }
        """
        updated_issues     = []
        corrected_answers  = {}

        template_name = intake_context.get(
            "template_name", "Assessment"
        )
        member_id = intake_context.get("member_id", "UNKNOWN")
        submitted_answers = intake_context.get(
            "submitted_answers", {}
        )

        logger.info(
            f"Correction Agent: Processing {len(issues)} issues"
        )

        for issue in issues:
            q_id       = issue.get("questionId", "")
            q_name     = issue.get("questionName", "")
            q_type     = issue.get("questionType", "")
            orig_value = issue.get("originalValue", "")
            error_type = issue.get("errorType", "")

            # Only attempt correction for UserErrors
            # TemplateIssue and SystemIssue go to support teams
            if error_type != "UserError":
                updated_issues.append(issue)
                continue

            # ── TIER 1: Deterministic Auto-Fix ─────────────

            # Fix 1: Whitespace in numeric fields
            # "  72  " → "72"
            # Real mCare error: "value is not of a numeric value"
            if q_type == "number":
                fixed = self._fix_numeric_whitespace(orig_value)
                if fixed and fixed != orig_value:
                    issue = issue.copy()
                    issue["correctedValue"] = fixed
                    issue["autoFixed"]      = True
                    issue["suggestion"]     = (
                        f"Auto-corrected: Removed whitespace. "
                        f"'{orig_value}' → '{fixed}'"
                    )
                    corrected_answers[q_id] = fixed
                    logger.info(
                        f"Tier 1 fix: {q_id} numeric "
                        f"'{orig_value}' → '{fixed}'"
                    )
                    updated_issues.append(issue)
                    continue

            # Fix 2: Date format standardization
            # "20/01/2025" → "01/20/2025"
            # Handles common date entry mistakes
            if q_type == "date":
                fixed = self._fix_date_format(orig_value)
                if fixed and fixed != orig_value:
                    issue = issue.copy()
                    issue["correctedValue"] = fixed
                    issue["autoFixed"]      = True
                    issue["suggestion"]     = (
                        f"Auto-corrected: Date format standardized. "
                        f"'{orig_value}' → '{fixed}'"
                    )
                    corrected_answers[q_id] = fixed
                    logger.info(
                        f"Tier 1 fix: {q_id} date "
                        f"'{orig_value}' → '{fixed}'"
                    )
                    updated_issues.append(issue)
                    continue

            # Fix 3: Whitespace-only textarea
            # "   " → stripped, but still empty → needs review
            if q_type in ["textarea", "text"]:
                stripped = str(orig_value).strip()
                if stripped and stripped != orig_value:
                    # Had content but with extra whitespace
                    issue = issue.copy()
                    issue["correctedValue"] = stripped
                    issue["autoFixed"]      = True
                    issue["suggestion"]     = (
                        "Auto-corrected: Removed extra whitespace."
                    )
                    corrected_answers[q_id] = stripped
                    updated_issues.append(issue)
                    continue

            # ── TIER 2: AI Suggestions ──────────────────────
            # For empty required clinical textarea fields
            # AI generates contextually relevant suggestions
            # Care Manager MUST review — never auto-applied
            if q_type in ["textarea", "text"] and \
               self._is_clinical_field(q_name):

                logger.info(
                    f"Tier 2: Calling AI for {q_id} - {q_name}"
                )

                # Build context from OTHER answers
                # This gives AI relevant information
                # WITHOUT sending PHI
                context_summary = self._build_safe_context(
                    submitted_answers,
                    exclude_q_id=q_id
                )

                # Build the AI prompt
                prompt = self._build_ai_prompt(
                    question_name  = q_name,
                    template_name  = template_name,
                    context_summary = context_summary
                )

                # Call AI service (OpenRouter → GPT-4o)
                ai_suggestion = self.ai_service.get_suggestion(
                    prompt
                )

                if ai_suggestion:
                    issue = issue.copy()
                    issue["correctedValue"] = None  # NOT auto-applied
                    issue["autoFixed"]      = False
                    issue["suggestion"]     = (
                        f"AI Suggestion: {ai_suggestion}"
                    )
                    logger.info(
                        f"Tier 2: AI suggestion generated for {q_id}"
                    )

            updated_issues.append(issue)

        logger.info(
            f"Correction Agent: "
            f"{sum(1 for i in updated_issues if i['autoFixed'])} "
            f"auto-fixed, "
            f"{sum(1 for i in updated_issues if not i['autoFixed'])} "
            f"need review"
        )

        return updated_issues, corrected_answers

    # ── Private Methods ─────────────────────────────────────

    def _fix_numeric_whitespace(self, value: str) -> str | None:
        """
        Strips whitespace from numeric fields.
        "  72  " → "72"
        "7 2"    → cannot fix → returns None
        """
        if not value:
            return None

        cleaned = str(value).strip()

        # Check if it's valid after stripping
        try:
            float(cleaned)
            return cleaned
        except ValueError:
            return None  # Still invalid after stripping

    def _fix_date_format(self, value: str) -> str | None:
        """
        Attempts to standardize date formats.
        Tries to parse various formats and return MM/DD/YYYY.
        """
        if not value:
            return None

        # Formats to try parsing
        formats_to_try = [
            "%d/%m/%Y",           # 20/01/2025 (wrong order)
            "%Y/%m/%d",           # 2025/01/20
            "%m-%d-%Y",           # 01-20-2025
            "%Y-%m-%dT%H:%M:%SZ", # ISO 8601
            "%Y-%m-%dT%H:%M:%S",
        ]

        for fmt in formats_to_try:
            try:
                parsed = datetime.strptime(
                    str(value).strip(), fmt
                )
                # Return in standard mCare format
                return parsed.strftime("%m/%d/%Y")
            except ValueError:
                continue

        return None  # Cannot fix

    def _is_clinical_field(self, question_name: str) -> bool:
        """
        Determines if a field is a clinical text field
        that warrants an AI suggestion.
        Checks question name against clinical keywords.
        """
        name_lower = question_name.lower()
        return any(
            keyword in name_lower
            for keyword in CLINICAL_KEYWORDS
        )

    def _build_safe_context(
        self,
        submitted_answers: dict,
        exclude_q_id: str
    ) -> str:
        """
        Builds a safe context summary from other answers.

        PRIVACY RULE:
        - NEVER include member names, DOB, Medicaid ID
        - Only include Yes/No answers and non-sensitive values
        - This context helps AI give relevant suggestions
          without exposing PHI

        Example output:
        "Q8: Yes, Q10: No, Q12: Yes, Q20: No"
        """
        # Questions that contain PHI — always exclude
        PHI_QUESTIONS = ["Q1", "Q2", "Q3", "Q4"]

        context_parts = []

        for q_id, answer_data in submitted_answers.items():
            # Skip the question we're generating suggestion for
            if q_id == exclude_q_id:
                continue

            # Skip PHI fields
            if q_id in PHI_QUESTIONS:
                continue

            value = answer_data.get("value", "")

            # Only include Yes/No/N/A answers for context
            # Skip long text (could contain PHI)
            if value in ["Yes", "No", "N/A"] and value:
                context_parts.append(f"{q_id}: {value}")

        # Limit context to 10 answers to keep prompt short
        limited = context_parts[:10]

        return ", ".join(limited) if limited else "No context available"

    def _build_ai_prompt(
        self,
        question_name   : str,
        template_name   : str,
        context_summary : str
    ) -> str:
        """
        Builds the prompt sent to AI (OpenRouter → GPT-4o).

        Key principles:
        1. No PHI in the prompt
        2. Clear instruction for clinical professional tone
        3. Context from other answers for relevance
        4. Short output requested (2-3 sentences)
        """
        return f"""You are a healthcare documentation assistant 
helping complete a clinical assessment form.

Assessment Type: {template_name}
Field to Complete: {question_name}

Context from other answers in this assessment:
{context_summary}

Task: Write 2-3 professional sentences appropriate for 
this clinical field. 

Requirements:
- Use professional healthcare/clinical language
- Be specific and relevant to the field name
- Do NOT include patient names, dates of birth, or IDs
- Be concise (2-3 sentences maximum)
- Write as if a registered nurse is documenting

Generate the clinical text for '{question_name}':"""