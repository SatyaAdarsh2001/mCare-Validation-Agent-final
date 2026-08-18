# ============================================================
# AGENT 4: Correction Agent
# ============================================================
# PURPOSE:
#   Tier 1:
#     - Numeric whitespace correction
#     - Date correction
#     - Text whitespace correction
#     - Textarea whitespace correction
#     - Button group option correction
#     - Duplicate detection
#
#   Tier 2:
#     - AI clinical suggestions
#     - AI coaching summary
#     - AI quality score
#
# PHI SAFETY:
#   Only safe/limited assessment context is sent to AIService.
# ============================================================

import logging
import re
from datetime import datetime


logger = logging.getLogger(__name__)


CLINICAL_KEYWORDS = [
    "conclusion",
    "summary",
    "barrier",
    "concern",
    "rationale",
    "plan",
    "goal",
    "comment",
    "observation",
    "assessment",
    "note",
    "recommendation",
    "intervention",
    "skill",
    "strain",
    "discharge",
    "additional"
]


class CorrectionAgent:

    def __init__(
        self,
        ai_service
    ):

        self.ai_service = ai_service

    # ========================================================
    # MAIN PROCESS
    # ========================================================

    def process(
        self,
        issues: list,
        intake_context: dict
    ) -> tuple:

        updated_issues = []

        corrected_answers = {}

        template_name = intake_context.get(
            "template_name",
            "Assessment"
        )

        template_version = intake_context.get(
            "version",
            "?"
        )

        submitted_answers = intake_context.get(
            "submitted_answers",
            {}
        )

        pruned_ids = set(
            intake_context.get(
                "pruned_question_ids",
                []
            )
        )

        logger.info(
            "Correction Agent: "
            f"Processing {len(issues)} issues"
        )

        # ====================================================
        # INITIALIZE CORRECTED ANSWERS
        # ====================================================

        for q_id, answer_data in submitted_answers.items():

            if q_id in pruned_ids:
                continue

            value = self._extract_value(
                answer_data
            )

            corrected_answers[q_id] = value

        # ====================================================
        # PROCESS ISSUES
        # ====================================================

        for original_issue in issues:

            issue = original_issue.copy()

            q_id = issue.get(
                "questionId",
                ""
            )

            q_name = issue.get(
                "questionName",
                ""
            )

            q_type = str(
                issue.get(
                    "questionType",
                    ""
                )
            ).lower()

            orig_value = issue.get(
                "originalValue",
                ""
            )

            error_type = issue.get(
                "errorType",
                ""
            )

            # ------------------------------------------------
            # PRUNED QUESTION
            # ------------------------------------------------

            if q_id in pruned_ids:

                issue["autoFixed"] = False
                issue["pruned"] = True
                issue["correctedValue"] = None

                issue["suggestion"] = (
                    f"Auto-pruned: question '{q_id}' "
                    f"not in template version "
                    f"{template_version}."
                )

                updated_issues.append(issue)

                continue

            # ------------------------------------------------
            # ONLY USER ERRORS REQUIRE CORRECTION
            # ------------------------------------------------

            if error_type != "UserError":

                updated_issues.append(issue)

                continue

            # =================================================
            # TIER 1 - NUMBER
            # =================================================

            if q_type == "number":

                fixed = self._fix_numeric_whitespace(
                    orig_value
                )

                if (
                    fixed is not None
                    and fixed != orig_value
                ):

                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True

                    issue["suggestion"] = (
                        "Auto-corrected: Standardized "
                        "numeric format/whitespace."
                    )

                    corrected_answers[q_id] = fixed

                    updated_issues.append(issue)

                    continue

            # =================================================
            # TIER 1 - DATE
            # =================================================

            if q_type == "date":

                fixed = self._fix_date_format(
                    orig_value
                )

                if (
                    fixed
                    and fixed != orig_value
                ):

                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True

                    issue["suggestion"] = (
                        "Auto-corrected: Date format "
                        "standardized."
                    )

                    corrected_answers[q_id] = fixed

                    updated_issues.append(issue)

                    continue

            # =================================================
            # TIER 1 - TEXT
            # =================================================

            if q_type == "text":

                fixed = self._fix_text_whitespace(
                    orig_value
                )

                if (
                    fixed is not None
                    and fixed != str(orig_value)
                ):

                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True

                    issue["suggestion"] = (
                        "Auto-corrected: Removed "
                        "extra whitespace."
                    )

                    corrected_answers[q_id] = fixed

                    updated_issues.append(issue)

                    continue

            # =================================================
            # TIER 1 - TEXTAREA
            # =================================================

            if q_type == "textarea":

                fixed = self._fix_text_whitespace(
                    orig_value
                )

                if (
                    fixed is not None
                    and fixed != str(orig_value)
                ):

                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True

                    issue["suggestion"] = (
                        "Auto-corrected: Removed "
                        "extra whitespace."
                    )

                    corrected_answers[q_id] = fixed

                    updated_issues.append(issue)

                    continue

            # =================================================
            # TIER 1 - BUTTON GROUP
            # =================================================

            if q_type == "buttongroup":

                fixed = self._fix_option_whitespace(
                    orig_value
                )

                if (
                    fixed is not None
                    and fixed != str(orig_value)
                ):

                    issue["correctedValue"] = fixed
                    issue["autoFixed"] = True

                    issue["suggestion"] = (
                        "Auto-corrected: Standardized "
                        "option value."
                    )

                    corrected_answers[q_id] = fixed

                    updated_issues.append(issue)

                    continue

            # =================================================
            # TIER 2 - AI CLINICAL SUGGESTION
            # =================================================

            if (
                q_type in [
                    "textarea",
                    "text"
                ]
                and self._is_clinical_field(
                    q_name
                )
            ):

                logger.info(
                    "Tier 2: Calling AI for "
                    f"{q_id} - {q_name}"
                )

                context_summary = (
                    self._build_safe_context(
                        submitted_answers,
                        exclude_q_id=q_id
                    )
                )

                prompt = self._build_ai_prompt(
                    question_name=q_name,
                    template_name=template_name,
                    context_summary=context_summary
                )

                try:

                    ai_result = (
                        self.ai_service
                        .get_structured_response(
                            prompt=prompt,
                            default_score=7,
                            purpose="suggestion"
                        )
                    )

                except Exception as e:

                    logger.error(
                        "Tier 2 AI suggestion failed "
                        f"for {q_id}: {str(e)}"
                    )

                    ai_result = {}

                suggestion = ai_result.get(
                    "suggestion",
                    ""
                )

                if suggestion:

                    issue["correctedValue"] = None
                    issue["autoFixed"] = False

                    issue["suggestion"] = (
                        f"AI Suggestion: {suggestion}"
                    )

                    issue["aiScore"] = ai_result.get(
                        "score",
                        7
                    )

                    issue["aiFeedback"] = ai_result.get(
                        "feedback",
                        ""
                    )

                    issue["aiConfidence"] = ai_result.get(
                        "confidence",
                        0.5
                    )

                    issue["aiSource"] = ai_result.get(
                        "source",
                        "unknown"
                    )

                    logger.info(
                        "Tier 2 AI suggestion generated: "
                        f"question={q_id}, "
                        f"source={issue['aiSource']}"
                    )

            updated_issues.append(issue)

        # ====================================================
        # DUPLICATE TEXT DETECTION
        # ====================================================

        updated_issues = self._check_duplicate_text(
            updated_issues,
            submitted_answers
        )

        # ====================================================
        # COACHING SUMMARY
        # ====================================================

        coaching_summary = ""

        try:

            coaching_summary = self._get_coaching_summary(
                intake_context
            )

        except Exception as e:

            logger.error(
                "Correction Agent: Coaching summary failed: "
                f"{str(e)}"
            )

        # ====================================================
        # QUALITY SCORE
        # ====================================================

        try:

            quality_score = self._get_quality_score(
                updated_issues,
                intake_context
            )

        except Exception as e:

            logger.error(
                "Correction Agent: Quality score failed: "
                f"{str(e)}"
            )

            quality_score = {
                "score": 0,
                "feedback": (
                    "AI quality scoring unavailable."
                ),
                "confidence": 0.0,
                "source": "error"
            }

        # ====================================================
        # COUNTS
        # ====================================================

        auto_fixed = sum(
            1
            for issue in updated_issues
            if issue.get("autoFixed")
        )

        needs_review = sum(
            1
            for issue in updated_issues
            if not issue.get("autoFixed")
        )

        logger.info(
            "Correction Agent: "
            f"{auto_fixed} auto-fixed, "
            f"{needs_review} need review, "
            f"quality_score={quality_score.get('score')}, "
            f"source={quality_score.get('source')}"
        )

        return (
            updated_issues,
            corrected_answers,
            coaching_summary,
            quality_score
        )

    # ========================================================
    # VALUE HELPER
    # ========================================================

    def _extract_value(
        self,
        answer_data
    ):

        if isinstance(
            answer_data,
            dict
        ):

            return answer_data.get(
                "value",
                ""
            )

        return answer_data

    # ========================================================
    # NUMBER
    # ========================================================

    def _fix_numeric_whitespace(
        self,
        value: str
    ) -> str | None:

        if value is None:
            return None

        cleaned = str(
            value
        ).strip()

        if cleaned == "":
            return ""

        try:

            float(cleaned)

            return cleaned

        except ValueError:

            return None

    # ========================================================
    # DATE
    # ========================================================

    def _fix_date_format(
        self,
        value: str
    ) -> str | None:

        if not value:
            return None

        cleaned = str(
            value
        ).strip()

        formats_to_try = [

            # DD/MM/YYYY
            "%d/%m/%Y",

            # YYYY/MM/DD
            "%Y/%m/%d",

            # MM/DD/YYYY
            "%m/%d/%Y",

            # MM-DD-YYYY
            "%m-%d-%Y",

            # DD-MM-YYYY
            "%d-%m-%Y",

            # YYYY-MM-DD
            "%Y-%m-%d",

            # ISO datetime
            "%Y-%m-%dT%H:%M:%SZ",

            "%Y-%m-%dT%H:%M:%S",

            "%Y-%m-%d %H:%M:%S"
        ]

        for fmt in formats_to_try:

            try:

                parsed = datetime.strptime(
                    cleaned,
                    fmt
                )

                return parsed.strftime(
                    "%m/%d/%Y"
                )

            except ValueError:

                continue

        return None

    # ========================================================
    # TEXT WHITESPACE
    # ========================================================

    def _fix_text_whitespace(
        self,
        value: str
    ) -> str | None:

        if value is None:
            return None

        value_str = str(
            value
        )

        # Remove leading/trailing whitespace
        cleaned = value_str.strip()

        # Replace tabs/newlines/multiple spaces
        # with a single space.
        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned
        )

        return cleaned

    # ========================================================
    # BUTTON GROUP
    # ========================================================

    def _fix_option_whitespace(
        self,
        value: str
    ) -> str | None:

        if value is None:
            return None

        cleaned = str(
            value
        ).strip()

        if cleaned == "":
            return ""

        # Remove duplicate whitespace
        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned
        )

        # Standard assessment options
        valid_options = {
            "yes": "Yes",
            "no": "No",
            "n/a": "N/A"
        }

        normalized = valid_options.get(
            cleaned.lower()
        )

        if normalized:
            return normalized

        # If it isn't one of the known options,
        # return cleaned value without changing
        # its actual content.
        return cleaned

    # ========================================================
    # CLINICAL FIELD
    # ========================================================

    def _is_clinical_field(
        self,
        question_name: str
    ) -> bool:

        name_lower = (
            str(question_name).lower()
        )

        return any(
            keyword in name_lower
            for keyword in CLINICAL_KEYWORDS
        )

    # ========================================================
    # SAFE CONTEXT
    # ========================================================

    def _build_safe_context(
        self,
        submitted_answers: dict,
        exclude_q_id: str
    ) -> str:

        PHI_QUESTIONS = {
            "Q1",
            "Q2",
            "Q3",
            "Q4"
        }

        context_parts = []

        for q_id, answer_data in submitted_answers.items():

            if (
                q_id == exclude_q_id
                or q_id in PHI_QUESTIONS
            ):

                continue

            value = self._extract_value(
                answer_data
            )

            if value in [
                "Yes",
                "No",
                "N/A"
            ]:

                context_parts.append(
                    f"{q_id}:{value}"
                )

        return (
            ",".join(
                context_parts[:8]
            )
            or "None"
        )

    # ========================================================
    # AI PROMPT
    # ========================================================

    def _build_ai_prompt(
        self,
        question_name: str,
        template_name: str,
        context_summary: str
    ) -> str:

        return (
            f"Assessment:{template_name}\n"
            f"Field:{question_name}\n"
            f"Context:{context_summary}\n\n"
            "Write 2 concise clinical sentences "
            "appropriate for this field. "
            "Do not invent facts."
        )

    # ========================================================
    # COACHING SUMMARY
    # ========================================================

    def _get_coaching_summary(
        self,
        intake_context: dict
    ) -> str:

        submitted_answers = intake_context.get(
            "submitted_answers",
            {}
        )

        template_name = intake_context.get(
            "template_name",
            "Assessment"
        )

        template_questions = intake_context.get(
            "template_questions",
            {}
        )

        PHI_QUESTIONS = {
            "Q1",
            "Q2",
            "Q3",
            "Q4"
        }

        context_parts = []

        for q_id, answer_data in submitted_answers.items():

            if q_id in PHI_QUESTIONS:
                continue

            value = self._extract_value(
                answer_data
            )

            if value not in [
                "Yes",
                "No",
                "N/A"
            ]:

                continue

            question_data = template_questions.get(
                q_id,
                {}
            )

            q_name = question_data.get(
                "name",
                q_id
            )

            clean = re.sub(
                r"<[^>]+>",
                "",
                str(q_name)
            )[:50]

            context_parts.append(
                f"{clean}:{value}"
            )

        context = "\n".join(
            context_parts[:8]
        )

        prompt = (
            f"Assessment:{template_name}\n"
            f"Responses:\n{context}\n\n"
            "Give a concise 2-sentence "
            "clinical coaching summary. "
            "Do not invent facts."
        )

        result = self.ai_service.get_structured_response(
            prompt=prompt,
            default_score=7,
            purpose="coaching"
        )

        return result.get(
            "suggestion",
            ""
        )

    # ========================================================
    # QUALITY SCORE
    # ========================================================

    def _get_quality_score(
        self,
        issues: list,
        intake_context: dict
    ) -> dict:

        total_q = intake_context.get(
            "question_count",
            1
        )

        answered = intake_context.get(
            "answer_count",
            0
        )

        high_issues = sum(
            1
            for issue in issues
            if issue.get("severity") == "High"
        )

        auto_fixed = sum(
            1
            for issue in issues
            if issue.get("autoFixed")
        )

        prompt = (
            f"Questions:{total_q}\n"
            f"Answered:{answered}\n"
            f"HighIssues:{high_issues}\n"
            f"AutoFixed:{auto_fixed}\n\n"
            "Rate assessment quality 1-10. "
            "Return score and one brief feedback sentence."
        )

        result = self.ai_service.get_structured_response(
            prompt=prompt,
            default_score=7,
            purpose="score"
        )

        return {
            "score": result.get(
                "score",
                7
            ),

            "feedback": result.get(
                "feedback",
                "Assessment requires attention before submission."
            ),

            "confidence": result.get(
                "confidence",
                0.5
            ),

            "source": result.get(
                "source",
                "unknown"
            )
        }

    # ========================================================
    # DUPLICATE TEXT
    # ========================================================

    def _check_duplicate_text(
        self,
        issues: list,
        submitted_answers: dict
    ) -> list:

        textarea_values = {}

        for q_id, answer_data in submitted_answers.items():

            value = self._extract_value(
                answer_data
            )

            value_str = str(
                value
            ).strip()

            if len(value_str) <= 30:
                continue

            if value_str in textarea_values:

                issues.append({
                    "questionId": q_id,
                    "questionName": q_id,
                    "errorType": "UserError",
                    "severity": "Medium",

                    "description": (
                        "Duplicate text detected. "
                        f"Identical content as "
                        f"{textarea_values[value_str]}."
                    ),

                    "originalValue": (
                        value_str[:50] + "..."
                    ),

                    "correctedValue": None,
                    "autoFixed": False,

                    "suggestion": (
                        "Provide field-specific "
                        "clinical observations."
                    ),

                    "questionType": "textarea"
                })

            else:

                textarea_values[value_str] = q_id

        return issues