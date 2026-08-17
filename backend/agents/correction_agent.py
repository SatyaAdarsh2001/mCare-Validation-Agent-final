# ============================================================
# AGENT 4: Correction Agent — Phase 2 Enhanced
# ============================================================
# PURPOSE:
#   Performs Tier-1 deterministic auto-fixes (whitespace, dates),
#   handles auto-pruning of out-of-template IDs (CCA Error 3 & 4),
#   adds timeout risk guidance (CCA Error 1), and triggers Tier-2
#   AI clinical suggestions.
# ============================================================

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

CLINICAL_KEYWORDS = [
    "conclusion", "summary", "barrier", "concern",
    "rationale", "plan", "goal", "comment", "observation",
    "assessment", "note", "recommendation", "intervention",
    "skill", "strain", "discharge", "additional"
]


class CorrectionAgent:

    def __init__(self, ai_service):
        self.ai_service = ai_service

    def process(self, issues: list, intake_context: dict) -> tuple:
        updated_issues = []
        corrected_answers = {}

        template_name = intake_context.get("template_name", "Assessment")
        template_version = intake_context.get("version", "?")
        submitted_answers = intake_context.get("submitted_answers", {})
        pruned_ids = set(intake_context.get("pruned_question_ids", []))

        logger.info(f"Correction Agent: Processing {len(issues)} issues")

        # ── Step 1: Initialize corrected answers excluding pruned IDs ──
        for q_id, answer_data in submitted_answers.items():
            if q_id not in pruned_ids:
                val = answer_data.get("value", "") if isinstance(answer_data, dict) else answer_data
                corrected_answers[q_id] = val

        # ── Step 2: Process issues (Auto-Fix & AI Suggestion) ─────────
        for issue in issues:
            q_id = issue.get("questionId", "")
            q_name = issue.get("questionName", "")
            q_type = issue.get("questionType", "")
            orig_value = issue.get("originalValue", "")
            error_type = issue.get("errorType", "")

            # Auto-resolve issues for pruned invalid/duplicate questions (Errors 3 & 4)
            # NOTE: autoFixed stays False here on purpose — nothing was
            # "corrected", the field was removed. These are surfaced
            # separately via prunedQuestions/Template Sanitize Notice,
            # not counted in autoFixedCount.
            if q_id in pruned_ids:
                issue = issue.copy()
                issue["autoFixed"] = False
                issue["pruned"] = True
                issue["correctedValue"] = None
                issue["suggestion"] = (
                    f"Auto-pruned: question '{q_id}' not in template version {template_version}."
                )
                updated_issues.append(issue)
                continue

            if error_type != "UserError":
                updated_issues.append(issue)
                continue

            # ── TIER 1: Deterministic Auto-Fix ─────────────

            if q_type == "number":
                fixed = self._fix_numeric_whitespace(orig_value)
                if fixed is not None and fixed != orig_value:
                    issue = issue.copy()
                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True
                    issue["suggestion"] = (
                        f"Auto-corrected: Standardized numeric format/whitespace. "
                        f"'{orig_value}' → '{fixed}'"
                    )
                    corrected_answers[q_id] = fixed
                    updated_issues.append(issue)
                    continue

            if q_type == "date":
                fixed = self._fix_date_format(orig_value)
                if fixed and fixed != orig_value:
                    issue = issue.copy()
                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True
                    issue["suggestion"] = (
                        f"Auto-corrected: Date format standardized. "
                        f"'{orig_value}' → '{fixed}'"
                    )
                    corrected_answers[q_id] = fixed
                    updated_issues.append(issue)
                    continue

            if q_type in ["textarea", "text"]:
                stripped = str(orig_value).strip()
                if stripped != orig_value:
                    issue = issue.copy()
                    issue["correctedValue"] = stripped
                    issue["autoFixed"] = True
                    issue["suggestion"] = "Auto-corrected: Removed extra whitespace."
                    corrected_answers[q_id] = stripped
                    updated_issues.append(issue)
                    continue

            # ── TIER 2: AI Suggestions ──────────────────────

            if q_type in ["textarea", "text"] and self._is_clinical_field(q_name):
                logger.info(f"Tier 2: Calling AI for {q_id} - {q_name}")

                context_summary = self._build_safe_context(
                    submitted_answers, exclude_q_id=q_id
                )
                prompt = self._build_ai_prompt(
                    question_name=q_name,
                    template_name=template_name,
                    context_summary=context_summary
                )
                ai_suggestion = self.ai_service.get_suggestion(prompt)

                if ai_suggestion:
                    issue = issue.copy()
                    issue["correctedValue"] = None
                    issue["autoFixed"] = False
                    issue["suggestion"] = f"AI Suggestion: {ai_suggestion}"
                    logger.info(f"Tier 2: AI suggestion generated for {q_id}")

            updated_issues.append(issue)

        # NOTE: DB Timeout Risk is intentionally NOT injected as a fake
        # "issue" here. It's a pre-submission predictive signal only —
        # it belongs to the Submit flow (see app.py /api/submit and the
        # frontend's post-submit toast), not the Validate results list.

        # ── Phase 2: Enhanced AI Features ──────────────────

        # Duplicate text detection
        updated_issues = self._check_duplicate_text(
            updated_issues, submitted_answers
        )

        # Care Manager Coaching + Quality Score
        coaching_summary = ""
        quality_score = {"score": 0, "feedback": ""}

        if getattr(self.ai_service, "api_key", None):
            coaching_summary = self._get_coaching_summary(
                intake_context, self.ai_service
            )
            quality_score = self._get_quality_score(
                updated_issues, intake_context, self.ai_service
            )

        auto_fixed = sum(1 for i in updated_issues if i.get("autoFixed"))
        needs_review = sum(1 for i in updated_issues if not i.get("autoFixed"))
        logger.info(
            f"Correction Agent: {auto_fixed} auto-fixed, "
            f"{needs_review} need review"
        )

        return updated_issues, corrected_answers, coaching_summary, quality_score

    # ── Private Methods ─────────────────────────────────────

    def _fix_numeric_whitespace(self, value: str) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        if cleaned == "":
            return ""
        try:
            float(cleaned)
            return cleaned
        except ValueError:
            return None

    def _fix_date_format(self, value: str) -> str | None:
        if not value:
            return None
        formats_to_try = [
            "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y",
            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats_to_try:
            try:
                parsed = datetime.strptime(str(value).strip(), fmt)
                return parsed.strftime("%m/%d/%Y")
            except ValueError:
                continue
        return None

    def _is_clinical_field(self, question_name: str) -> bool:
        name_lower = question_name.lower()
        return any(kw in name_lower for kw in CLINICAL_KEYWORDS)

    def _build_safe_context(
        self, submitted_answers: dict, exclude_q_id: str
    ) -> str:
        PHI_QUESTIONS = ["Q1", "Q2", "Q3", "Q4"]
        context_parts = []
        for q_id, answer_data in submitted_answers.items():
            if q_id == exclude_q_id or q_id in PHI_QUESTIONS:
                continue
            value = answer_data.get("value", "") if isinstance(answer_data, dict) else answer_data
            if value in ["Yes", "No", "N/A"]:
                context_parts.append(f"{q_id}: {value}")
        return ", ".join(context_parts[:10]) or "No context available"

    def _build_ai_prompt(
        self,
        question_name: str,
        template_name: str,
        context_summary: str
    ) -> str:
        return (
            f"You are a healthcare documentation assistant.\n"
            f"Assessment: {template_name}\n"
            f"Field: {question_name}\n"
            f"Context: {context_summary}\n\n"
            f"Write 2-3 professional clinical sentences for "
            f"'{question_name}'. No PHI. Nurse documentation style:"
        )

    def _get_coaching_summary(
        self, intake_context: dict, ai_service
    ) -> str:
        submitted_answers = intake_context.get("submitted_answers", {})
        template_name = intake_context.get("template_name", "Assessment")
        template_questions = intake_context.get("template_questions", {})
        PHI_QUESTIONS = ["Q1", "Q2", "Q3", "Q4"]

        context_parts = []
        for q_id, answer_data in submitted_answers.items():
            if q_id in PHI_QUESTIONS:
                continue
            value = answer_data.get("value", "") if isinstance(answer_data, dict) else answer_data
            if value in ["Yes", "No", "N/A"]:
                q_name = template_questions.get(q_id, {}).get("name", q_id)
                clean = re.sub(r'<[^>]+>', '', q_name)[:60]
                context_parts.append(f"{clean}: {value}")

        context = "\n".join(context_parts[:15])

        prompt = (
            f"You are a clinical care manager reviewing a {template_name}.\n"
            f"Assessment responses (no PHI):\n{context}\n\n"
            f"Write a 3-sentence clinical coaching summary covering:\n"
            f"1. Key risk areas\n2. Priority actions\n3. Overall status\n"
            f"Be concise and clinical:"
        )
        return ai_service.get_suggestion(prompt)

    def _get_quality_score(
        self, issues: list, intake_context: dict, ai_service
    ) -> dict:
        total_q = intake_context.get("question_count", 1)
        answered = intake_context.get("answer_count", 0)
        high_issues = sum(1 for i in issues if i.get("severity") == "High")
        auto_fixed = sum(1 for i in issues if i.get("autoFixed"))

        prompt = (
            f"Rate this healthcare assessment quality 1-10.\n"
            f"Template: {intake_context.get('template_name', 'Assessment')}\n"
            f"Questions: {total_q}, Answered: {answered}, "
            f"High Issues: {high_issues}, Auto-Fixed: {auto_fixed}\n\n"
            f"Respond ONLY in this exact format:\n"
            f"SCORE: [1-10]\n"
            f"FEEDBACK: [one sentence]"
        )

        response = ai_service.get_suggestion(prompt)
        score = 7
        feedback = "Assessment requires attention before submission."

        try:
            for line in response.split("\n"):
                if line.startswith("SCORE:"):
                    score = int(line.replace("SCORE:", "").strip())
                elif line.startswith("FEEDBACK:"):
                    feedback = line.replace("FEEDBACK:", "").strip()
        except Exception:
            pass

        return {"score": score, "feedback": feedback}

    def _check_duplicate_text(
        self, issues: list, submitted_answers: dict
    ) -> list:
        textarea_values = {}
        for q_id, answer_data in submitted_answers.items():
            value = answer_data.get("value", "") if isinstance(answer_data, dict) else answer_data
            value_str = str(value).strip()
            if len(value_str) > 30:
                if value_str in textarea_values:
                    issues.append({
                        "questionId": q_id,
                        "questionName": q_id,
                        "errorType": "UserError",
                        "severity": "Medium",
                        "description": (
                            f"Duplicate text detected. Identical content "
                            f"as {textarea_values[value_str]}. "
                            f"CCA may flag duplicate responses."
                        ),
                        "originalValue": value_str[:50] + "...",
                        "correctedValue": None,
                        "autoFixed": False,
                        "suggestion": "Provide field-specific clinical observations.",
                        "questionType": "textarea"
                    })
                else:
                    textarea_values[value_str] = q_id
        return issues