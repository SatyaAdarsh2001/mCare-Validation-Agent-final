# ============================================================
# AGENT 5: Report Agent — Phase 2 Enhanced
# ============================================================
# PURPOSE:
#   Packages the final validation response, adds CCA transport
#   advisories (session requirements, timeout risk scoring),
#   surfaces pruned out-of-template question IDs, and builds the
#   sanitized payload for downstream CCA submission.
# ============================================================

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ReportAgent:

    def process(
        self,
        intake_context    : dict,
        issues            : list,
        corrected_answers : dict,
        coaching_summary  : str = "",
        quality_score     : dict = None
    ) -> dict:
        try:
            logger.info("Report Agent: Building final response...")

            total_issues       = sum(1 for i in issues if not i.get("pruned"))
            auto_fixed_count   = sum(1 for i in issues if i.get("autoFixed") is True and not i.get("pruned"))
            needs_review_count = sum(1 for i in issues if i.get("autoFixed") is False and not i.get("pruned"))

            status  = self._determine_status(total_issues, auto_fixed_count, needs_review_count)
            summary = self._write_summary(status, total_issues, auto_fixed_count, needs_review_count)

            # Build corrected submission (always generated if answers are available)
            corrected_submission = self._build_corrected_submission(
                intake_context, corrected_answers
            )

            # Count concept type issues for reporting telemetry
            concept_type_warnings = sum(
                1 for i in issues if "concept type" in str(i.get("description", "")).lower()
            )

            clean_issues = self._clean_issues(issues)

            response = {
                "status"             : status,
                "summary"            : summary,
                "totalIssues"        : total_issues,
                "autoFixedCount"     : auto_fixed_count,
                "needsReviewCount"   : needs_review_count,
                "issues"             : clean_issues,
                "correctedSubmission": corrected_submission,
                "escalation"         : None,
                "validatedAt"        : datetime.now(timezone.utc).isoformat(),
                "templateName"       : intake_context.get("template_name", ""),
                "memberId"           : intake_context.get("member_id", ""),
                "coachingSummary"    : coaching_summary or "",
                "qualityScore"       : quality_score or {"score": 0, "feedback": ""},
                # ── CCA Production Error Additions ─────────
                "prunedQuestions"    : list(set(intake_context.get("pruned_question_ids", []))),
                "timeoutRisk"        : {
                    "score"         : intake_context.get("timeout_risk_score", 0),
                    "level"         : intake_context.get("timeout_risk_level", "low"),
                    "recommendation": (
                        "Loader should retry with 1s/2s/4s backoff."
                        if intake_context.get("timeout_risk_level") == "high"
                        else "Standard submission parameters acceptable."
                    )
                },
                "sessionAdvisory"    : intake_context.get("session_advisory", {
                    "sessionRequired"  : True,
                    "recommendedAction": "Acquire or verify valid session token before submit."
                }),
                "conceptTypeWarnings": concept_type_warnings
            }

            logger.info(
                f"Report Agent: Status={status} | "
                f"Total={total_issues} | AutoFixed={auto_fixed_count} | "
                f"NeedsReview={needs_review_count} | "
                f"Pruned={len(response['prunedQuestions'])} | "
                f"TimeoutRisk={response['timeoutRisk']['level']}"
            )

            return response

        except Exception as e:
            logger.error(f"Report Agent error: {str(e)}", exc_info=True)
            return {
                "status"             : "error",
                "summary"            : f"Report Agent failed: {str(e)}",
                "totalIssues"        : 0,
                "autoFixedCount"     : 0,
                "needsReviewCount"   : 0,
                "issues"             : [],
                "correctedSubmission": None,
                "escalation"         : None,
                "coachingSummary"    : "",
                "qualityScore"       : {"score": 0, "feedback": ""},
                "prunedQuestions"    : [],
                "timeoutRisk"        : {"score": 0, "level": "low", "recommendation": ""},
                "sessionAdvisory"    : {"sessionRequired": True, "recommendedAction": ""},
                "conceptTypeWarnings": 0
            }

    def build_escalation_response(self, classification: dict) -> dict:
        error_type = classification.get("error_type", "SystemIssue")
        reason     = classification.get("reason", "Unknown issue")
        routed_to  = classification.get("routed_to", "Support Team")
        details    = classification.get("details", "")

        issue_name = "Template Configuration Issue" \
            if error_type == "TemplateIssue" else "System Issue Detected"

        return {
            "status"             : "escalated",
            "summary"            : (
                f"{issue_name} detected. "
                f"This is NOT a data entry problem. "
                f"Routed to: {routed_to}."
            ),
            "totalIssues"        : 1,
            "autoFixedCount"     : 0,
            "needsReviewCount"   : 1,
            "issues"             : [{
                "questionId"    : "N/A",
                "questionName"  : issue_name,
                "errorType"     : error_type,
                "severity"      : "High",
                "description"   : reason,
                "originalValue" : "",
                "correctedValue": None,
                "autoFixed"     : False,
                "suggestion"    : f"Contact {routed_to}. Do not attempt to resubmit."
            }],
            "correctedSubmission": None,
            "escalation"         : {
                "type"    : error_type,
                "routedTo": routed_to,
                "details" : details
            },
            "validatedAt"        : datetime.now(timezone.utc).isoformat(),
            "templateName"       : "",
            "memberId"           : "",
            "coachingSummary"    : "",
            "qualityScore"       : {"score": 0, "feedback": ""},
            "prunedQuestions"    : [],
            "timeoutRisk"        : {"score": 0, "level": "low", "recommendation": ""},
            "sessionAdvisory"    : {"sessionRequired": False, "recommendedAction": "Resolve escalation."},
            "conceptTypeWarnings": 0
        }

    # ── Private Methods ─────────────────────────────────────

    def _determine_status(
        self, total_issues: int, auto_fixed_count: int, needs_review_count: int
    ) -> str:
        if total_issues == 0:
            return "valid"
        if auto_fixed_count > 0 and needs_review_count == 0:
            return "auto_corrected"
        return "needs_review"

    def _write_summary(
        self, status: str, total_issues: int,
        auto_fixed_count: int, needs_review_count: int
    ) -> str:
        if status == "valid":
            return "Assessment passed all validation checks. Ready to submit to CCA."
        if status == "auto_corrected":
            return (
                f"Found {total_issues} issue(s) — all automatically corrected. "
                f"Please review before submitting."
            )
        parts = []
        if auto_fixed_count   > 0: parts.append(f"{auto_fixed_count} auto-corrected")
        if needs_review_count > 0: parts.append(f"{needs_review_count} require your attention")
        return (
            f"Found {total_issues} issue(s): {' | '.join(parts)}. "
            f"Please review before submitting to CCA."
        )

    def _build_corrected_submission(
        self, intake_context: dict, corrected_answers: dict
    ) -> dict:
        original = intake_context.get("original_submission", {})
        pruned_ids = set(intake_context.get("pruned_question_ids", []))

        corrected = {
            "MemberId"     : original.get("MemberId", ""),
            "StateID"      : original.get("StateID", ""),
            "templateGuid" : original.get("templateGuid", ""),
            "version"      : original.get("version", 1),
            "source"       : original.get("source", ""),
            "score"        : original.get("score", ""),
            "completedDate": original.get("completedDate", ""),
            "caseId"       : original.get("caseId", ""),
            "Registrar"    : original.get("Registrar", ""),
            "pages"        : []
        }

        for page in original.get("pages", []):
            corrected_page = {"id": page.get("id", ""), "questions": []}
            for question in page.get("questions", []):
                q_id = str(question.get("id", ""))

                # Exclude invalid/duplicate questions from final pages payload
                if q_id in pruned_ids:
                    continue

                original_answer = question.get("answer", {})
                original_value  = original_answer.get("value", "") if original_answer else ""
                final_value     = corrected_answers.get(q_id, original_value)

                corrected_page["questions"].append({
                    "id"    : question.get("id", q_id),
                    "answer": {"value": final_value}
                })

            if corrected_page["questions"]:
                corrected["pages"].append(corrected_page)

        return corrected

    def _clean_issues(self, issues: list) -> list:
        return [{
            "questionId"    : i.get("questionId", ""),
            "questionName"  : i.get("questionName", ""),
            "errorType"     : i.get("errorType", ""),
            "severity"      : i.get("severity", ""),
            "description"   : i.get("description", ""),
            "originalValue" : i.get("originalValue", ""),
            "correctedValue": i.get("correctedValue"),
            "autoFixed"     : i.get("autoFixed", False),
            "suggestion"    : i.get("suggestion"),
            "pruned"        : i.get("pruned", False)
        } for i in issues]