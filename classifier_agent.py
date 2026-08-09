# ============================================================
# AGENT 2: Classifier Agent
# ============================================================
# PURPOSE:
#   Second agent in the pipeline. Looks at the IntakeContext
#   and determines WHO is responsible for the problem:
#   - UserError    → Care Manager made a mistake (90-95%)
#   - TemplateIssue → Template config is wrong
#   - SystemIssue  → Infrastructure/DB/timeout problem
#
# ANALOGY FOR PPT:
#   Think of this as the "triage nurse" in an ER.
#   Before any treatment starts, she quickly assesses:
#   "Is this a patient problem, a hospital problem,
#    or an equipment problem?" and routes accordingly.
#
# KEY BEHAVIOR:
#   If TemplateIssue or SystemIssue is detected → ESCALATE
#   immediately. Don't waste time validating bad data.
#   Only UserError continues to Agent 3.
#
# INPUT:  IntakeContext from Agent 1
# OUTPUT: Classification result dict
# ============================================================

import logging

logger = logging.getLogger(__name__)

# ── System Issue Keywords ───────────────────────────────────
# If submission contains these words it's a system problem
# not a user problem. These come from real mCare error logs.
SYSTEM_ERROR_KEYWORDS = [
    "timeout",
    "dbtimeoutexception",
    "connection refused",
    "server error",
    "500",
    "session expired",
    "service unavailable",
    "gateway timeout",
    "database error",
    "null reference"
]


class ClassifierAgent:

    def process(self, intake_context: dict) -> dict:
        """
        Main method called by app.py
        Classifies the error type and decides if escalation needed
        """
        try:
            logger.info("Classifier Agent: Analyzing request...")

            # ── Check 1: System Issue Detection ────────────
            # Look for system error keywords in the submission
            # These indicate infrastructure problems, not user mistakes
            system_issue = self._check_system_issue(intake_context)
            if system_issue:
                logger.warning(
                    f"Classifier: SYSTEM ISSUE detected - {system_issue}"
                )
                return {
                    "escalate"    : True,
                    "error_type"  : "SystemIssue",
                    "reason"      : system_issue,
                    "routed_to"   : "Infrastructure Support Team",
                    "details"     : (
                        f"System error detected: {system_issue}. "
                        f"Care Manager cannot resolve this."
                    )
                }

            # ── Check 2: Template Issue Detection ──────────
            # Compare answer count vs template question count
            # If they don't match → template configuration problem
            template_issue = self._check_template_issue(intake_context)
            if template_issue:
                logger.warning(
                    f"Classifier: TEMPLATE ISSUE detected - {template_issue}"
                )
                return {
                    "escalate"  : True,
                    "error_type": "TemplateIssue",
                    "reason"    : template_issue,
                    "routed_to" : "Template Configuration Team",
                    "details"   : (
                        f"Template configuration issue: {template_issue}. "
                        f"Engineering team must fix this."
                    )
                }

            # ── Check 3: Missing Template ───────────────────
            # If template has no questions at all → bad template
            question_count = intake_context.get("question_count", 0)
            if question_count == 0:
                logger.warning("Classifier: Template has no questions")
                return {
                    "escalate"  : True,
                    "error_type": "TemplateIssue",
                    "reason"    : "Template contains no questions",
                    "routed_to" : "Template Configuration Team",
                    "details"   : (
                        "Template loaded but contains zero questions. "
                        "Template may be corrupted or misconfigured."
                    )
                }

            # ── Check 4: Missing Member ID ──────────────────
            # Every submission must have a member ID
            member_id = intake_context.get("member_id", "")
            if not member_id or member_id.strip() == "":
                logger.warning("Classifier: Missing Member ID")
                return {
                    "escalate"  : True,
                    "error_type": "SystemIssue",
                    "reason"    : "Member ID is missing from submission",
                    "routed_to" : "Infrastructure Support Team",
                    "details"   : (
                        "Submission received without a Member ID. "
                        "This indicates a system-level problem in "
                        "how mCare built the payload."
                    )
                }

            # ── All Checks Passed: UserError ────────────────
            # No system or template issues found
            # Proceed to Format Validator (Agent 3)
            logger.info(
                "Classifier: No escalation needed. "
                "Classified as UserError → proceeding to validation"
            )
            return {
                "escalate"  : False,
                "error_type": "UserError",
                "reason"    : None,
                "routed_to" : None,
                "details"   : (
                    "No system or template issues detected. "
                    "Proceeding with user error validation."
                )
            }

        except Exception as e:
            logger.error(
                f"Classifier Agent error: {str(e)}", exc_info=True
            )
            # If classifier itself fails → treat as system issue
            return {
                "escalate"  : True,
                "error_type": "SystemIssue",
                "reason"    : f"Classifier Agent failed: {str(e)}",
                "routed_to" : "Infrastructure Support Team",
                "details"   : str(e)
            }

    # ── Private Methods ─────────────────────────────────────

    def _check_system_issue(self, intake_context: dict) -> str | None:
        """
        Checks if submission contains system error indicators.
        Returns error description if found, None if clean.
        """
        # Check source field for error keywords
        source = str(
            intake_context.get("source", "")
        ).lower()

        # Check registrar field
        registrar = str(
            intake_context.get("registrar", "")
        ).lower()

        # Check score field (sometimes contains error messages)
        score = str(
            intake_context.get("score", "")
        ).lower()

        # Combine all text fields to search
        combined_text = f"{source} {registrar} {score}"

        for keyword in SYSTEM_ERROR_KEYWORDS:
            if keyword in combined_text:
                return (
                    f"System error keyword detected: '{keyword}'"
                )

        return None

    def _check_template_issue(self, intake_context: dict) -> str | None:
        """
        Compares answer count vs template question count.
        A big mismatch indicates template configuration problem.
        Returns issue description if found, None if clean.

        Real mCare error example:
        'Too many answers. Answer count: 122.
         Template Question count: 120.'
        """
        answer_count   = intake_context.get("answer_count", 0)
        question_count = intake_context.get("question_count", 0)

        # No answers submitted at all
        if answer_count == 0:
            return None  # Let validator handle empty submission

        # Answers significantly exceed template questions
        # Small difference (1-2) can happen due to textblocks
        # Large difference = template mismatch
        if question_count > 0:
            difference = answer_count - question_count

            if difference > 5:
                return (
                    f"Too many answers. "
                    f"Answer count: {answer_count}. "
                    f"Template Question count: {question_count}."
                )

        return None