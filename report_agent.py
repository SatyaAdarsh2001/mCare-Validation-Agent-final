# ============================================================
# AGENT 5: Report Agent
# ============================================================
# PURPOSE:
#   Final agent in the pipeline. Takes all outputs from
#   previous agents and packages everything into a clean,
#   structured JSON response that Angular frontend displays.
#
# ANALOGY FOR PPT:
#   Think of this as the "report writer" who sits at the end
#   of the assembly line. Takes all the findings, counts them,
#   determines the overall verdict, writes a human-readable
#   summary, and hands the final report to the Care Manager.
#
# DETERMINES FINAL STATUS:
#   "valid"          → No issues found at all
#   "auto_corrected" → All issues were auto-fixed (safe to proceed)
#   "needs_review"   → Some issues need Care Manager attention
#   "escalated"      → Template or System problem
#
# INPUT:  IntakeContext + corrected issues + corrected answers
# OUTPUT: Final ValidationResponse JSON
# ============================================================

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ReportAgent:

    def process(
        self,
        intake_context    : dict,
        issues            : list,
        corrected_answers : dict
    ) -> dict:
        """
        Main method called by app.py for normal validation flow.
        Builds the complete ValidationResponse.
        """
        try:
            logger.info("Report Agent: Building final response...")

            # ── Step 1: Count issues by category ───────────
            total_issues      = len(issues)
            auto_fixed_count  = sum(
                1 for i in issues if i.get("autoFixed") is True
            )
            needs_review_count = sum(
                1 for i in issues if i.get("autoFixed") is False
            )

            # ── Step 2: Determine overall status ───────────
            # This is the key decision that drives the UI
            status = self._determine_status(
                total_issues,
                auto_fixed_count,
                needs_review_count
            )

            # ── Step 3: Write human-readable summary ────────
            summary = self._write_summary(
                status,
                total_issues,
                auto_fixed_count,
                needs_review_count
            )

            # ── Step 4: Build corrected submission ──────────
            # Only built if there are auto-corrections to apply
            # This is the clean payload ready to send to CCA
            corrected_submission = None
            if auto_fixed_count > 0 and corrected_answers:
                corrected_submission = self._build_corrected_submission(
                    intake_context,
                    corrected_answers
                )

            # ── Step 5: Clean up issues for response ────────
            # Remove internal fields not needed by frontend
            clean_issues = self._clean_issues(issues)

            # ── Step 6: Build final response ────────────────
            response = {
                # Overall validation verdict
                "status"           : status,
                "summary"          : summary,

                # Issue counts for dashboard cards
                "totalIssues"      : total_issues,
                "autoFixedCount"   : auto_fixed_count,
                "needsReviewCount" : needs_review_count,

                # Detailed issues list for UI display
                "issues"           : clean_issues,

                # Corrected payload (null if no auto-fixes)
                "correctedSubmission": corrected_submission,

                # Escalation info (null for normal flow)
                "escalation"       : None,

                # Metadata
                "validatedAt"      : datetime.now(
                    timezone.utc
                ).isoformat(),
                "templateName"     : intake_context.get(
                    "template_name", ""
                ),
                "memberId"         : intake_context.get(
                    "member_id", ""
                )
            }

            logger.info(
                f"Report Agent: Complete. "
                f"Status={status} | "
                f"Total={total_issues} | "
                f"AutoFixed={auto_fixed_count} | "
                f"NeedsReview={needs_review_count}"
            )

            return response

        except Exception as e:
            logger.error(
                f"Report Agent error: {str(e)}", exc_info=True
            )
            return {
                "status" : "error",
                "summary": f"Report Agent failed: {str(e)}",
                "totalIssues"      : 0,
                "autoFixedCount"   : 0,
                "needsReviewCount" : 0,
                "issues"           : [],
                "correctedSubmission": None,
                "escalation"       : None
            }

    def build_escalation_response(
        self,
        classification: dict
    ) -> dict:
        """
        Called by app.py when Classifier Agent detects
        a TemplateIssue or SystemIssue.
        Bypasses validation entirely — routes to support team.
        """
        error_type = classification.get("error_type", "SystemIssue")
        reason     = classification.get("reason", "Unknown issue")
        routed_to  = classification.get(
            "routed_to", "Support Team"
        )
        details    = classification.get("details", "")

        # Determine question name for the issue card
        if error_type == "TemplateIssue":
            issue_name = "Template Configuration Issue"
        else:
            issue_name = "System Issue Detected"

        return {
            "status" : "escalated",
            "summary": (
                f"{issue_name} detected. "
                f"This is NOT a data entry problem. "
                f"Routed to: {routed_to}."
            ),
            "totalIssues"      : 1,
            "autoFixedCount"   : 0,
            "needsReviewCount" : 1,
            "issues"           : [
                {
                    "questionId"    : "N/A",
                    "questionName"  : issue_name,
                    "errorType"     : error_type,
                    "severity"      : "High",
                    "description"   : reason,
                    "originalValue" : "",
                    "correctedValue": None,
                    "autoFixed"     : False,
                    "suggestion"    : (
                        f"Contact {routed_to}. "
                        f"Do not attempt to resubmit."
                    )
                }
            ],
            "correctedSubmission": None,
            "escalation"         : {
                "type"     : error_type,
                "routedTo" : routed_to,
                "details"  : details
            },
            "validatedAt"  : datetime.now(timezone.utc).isoformat(),
            "templateName" : "",
            "memberId"     : ""
        }

    # ── Private Methods ─────────────────────────────────────

    def _determine_status(
        self,
        total_issues      : int,
        auto_fixed_count  : int,
        needs_review_count: int
    ) -> str:
        """
        Determines the overall validation status.

        Logic:
        - No issues at all          → "valid"
        - All issues auto-fixed     → "auto_corrected"
        - Some need manual review   → "needs_review"

        This status drives the color coding in Angular UI:
        - valid          → Green
        - auto_corrected → Blue
        - needs_review   → Yellow
        - escalated      → Red
        """
        if total_issues == 0:
            return "valid"

        if auto_fixed_count > 0 and needs_review_count == 0:
            return "auto_corrected"

        return "needs_review"

    def _write_summary(
        self,
        status            : str,
        total_issues      : int,
        auto_fixed_count  : int,
        needs_review_count: int
    ) -> str:
        """
        Writes a human-readable summary message.
        This is displayed prominently in the Angular modal.
        Care Manager reads this first.
        """
        if status == "valid":
            return (
                "Assessment passed all validation checks. "
                "Ready to submit to CCA."
            )

        if status == "auto_corrected":
            return (
                f"Found {total_issues} issue(s) — all were "
                f"automatically corrected. "
                f"Please review the corrections before submitting."
            )

        # needs_review
        parts = []

        if auto_fixed_count > 0:
            parts.append(
                f"{auto_fixed_count} auto-corrected"
            )

        if needs_review_count > 0:
            parts.append(
                f"{needs_review_count} require your attention"
            )

        detail = " | ".join(parts)

        return (
            f"Found {total_issues} issue(s): {detail}. "
            f"Please review before submitting to CCA."
        )

    def _build_corrected_submission(
        self,
        intake_context   : dict,
        corrected_answers: dict
    ) -> dict:
        """
        Builds the corrected submission payload.
        Starts with original submission, applies auto-fixes.
        This is the clean payload ready to send to CCA.

        Structure matches real mCare CCAAssessmentRequestBody:
        {
          MemberId, StateID, templateGuid, version,
          pages: [{ id, questions: [{ id, answer: {value} }] }]
        }
        """
        original = intake_context.get("original_submission", {})

        # Deep copy original submission
        corrected = {
            "MemberId"    : original.get("MemberId", ""),
            "StateID"     : original.get("StateID", ""),
            "templateGuid": original.get("templateGuid", ""),
            "version"     : original.get("version", 1),
            "source"      : original.get("source", ""),
            "score"       : original.get("score", ""),
            "completedDate": original.get("completedDate", ""),
            "caseId"      : original.get("caseId", ""),
            "Registrar"   : original.get("Registrar", ""),
            "pages"       : []
        }

        # Rebuild pages with corrected answer values
        original_pages = original.get("pages", [])

        for page in original_pages:
            corrected_page = {
                "id"       : page.get("id", ""),
                "questions": []
            }

            for question in page.get("questions", []):
                q_id          = question.get("id", "")
                original_answer = question.get("answer", {})
                original_value  = original_answer.get("value", "") \
                    if original_answer else ""

                # Apply correction if available
                final_value = corrected_answers.get(
                    q_id, original_value
                )

                corrected_page["questions"].append({
                    "id"    : q_id,
                    "answer": {"value": final_value}
                })

            corrected["pages"].append(corrected_page)

        return corrected

    def _clean_issues(self, issues: list) -> list:
        """
        Removes internal fields from issues before
        sending to Angular frontend.
        Frontend only needs these fields:
        questionId, questionName, errorType, severity,
        description, originalValue, correctedValue,
        autoFixed, suggestion
        """
        clean = []

        for issue in issues:
            clean.append({
                "questionId"    : issue.get("questionId", ""),
                "questionName"  : issue.get("questionName", ""),
                "errorType"     : issue.get("errorType", ""),
                "severity"      : issue.get("severity", ""),
                "description"   : issue.get("description", ""),
                "originalValue" : issue.get("originalValue", ""),
                "correctedValue": issue.get("correctedValue"),
                "autoFixed"     : issue.get("autoFixed", False),
                "suggestion"    : issue.get("suggestion")
            })

        return clean