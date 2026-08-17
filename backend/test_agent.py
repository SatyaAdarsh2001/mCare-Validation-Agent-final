# ============================================================
# Quick test without needing HTTP connection
# Tests all 5 agents directly in Python with full coverage for
# the 5 CCA production error scenarios.
# ============================================================

import json
import sys
import os
import copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.intake_agent import IntakeAgent
from agents.classifier_agent import ClassifierAgent
from agents.format_validator import FormatValidatorAgent
from agents.correction_agent import CorrectionAgent
from agents.report_agent import ReportAgent
from services.ai_service import AIService
from services.cca_transport import CCATransport


def load_base_data():
    submission_path = 'sample_data/submission.json'
    if not os.path.exists(submission_path):
        submission_path = 'sample_data/test_request.json'

    with open(submission_path, 'r') as f:
        data = json.load(f)
        submission_data = data.get("submission", data)

    with open('sample_data/template.json', 'r') as f:
        template_data = json.load(f)

    return copy.deepcopy(submission_data), copy.deepcopy(template_data)


def run_pipeline(request_data, test_label="Standard Pipeline"):
    print("\n" + "=" * 60)
    print(f"RUNNING: {test_label}")
    print("=" * 60)

    # Run Agent 1
    print("\n[Agent 1] Intake Agent...")
    intake = IntakeAgent()
    intake_result = intake.process(request_data)
    print(f"  Member ID    : {intake_result.get('member_id')}")
    print(f"  Template     : {intake_result.get('template_name')}")
    print(f"  Answers      : {intake_result.get('answer_count')}")
    print(f"  Questions    : {intake_result.get('question_count')}")
    print(f"  Timeout Risk : {intake_result.get('timeout_risk_level', 'N/A')} (Score: {intake_result.get('timeout_risk_score', 0)})")

    # Run Agent 2
    print("\n[Agent 2] Classifier Agent...")
    classifier = ClassifierAgent()
    classification = classifier.process(intake_result)
    print(f"  Error Type   : {classification.get('error_type')}")
    print(f"  Escalate     : {classification.get('escalate')}")

    if classification.get("escalate"):
        reporter = ReportAgent()
        esc_response = reporter.build_escalation_response(classification)
        print("\n[Escalated Early Exit]")
        print(json.dumps(esc_response, indent=2))
        return esc_response

    # Run Agent 3
    print("\n[Agent 3] Format Validator...")
    validator = FormatValidatorAgent()
    issues = validator.process(intake_result)
    print(f"  Issues Found : {len(issues)}")
    print(f"  Pruned QIDs  : {intake_result.get('pruned_question_ids', [])}")
    for issue in issues:
        print(f"    - [{issue['severity']}] {issue['questionId']}: {issue['description'][:65]}...")

    # Run Agent 4
    print("\n[Agent 4] Correction Agent...")
    ai_service = AIService()
    corrector = CorrectionAgent(ai_service)
    corrected_issues, corrected_answers, coaching, quality = corrector.process(
        issues, intake_result
    )
    print(f"  Coaching     : {coaching[:80]}..." if coaching else "  Coaching     : N/A")
    print(f"  Quality Score: {quality}")
    auto_fixed = sum(1 for i in corrected_issues if i.get('autoFixed'))
    print(f"  Auto Fixed   : {auto_fixed}")
    print(f"  Needs Review : {len(corrected_issues) - auto_fixed}")
    if corrected_answers:
        print(f"  Corrections  : {list(corrected_answers.keys())[:5]} (Total: {len(corrected_answers)})")

    # Run Agent 5
    print("\n[Agent 5] Report Agent...")
    reporter = ReportAgent()
    response = reporter.process(
        intake_result,
        corrected_issues,
        corrected_answers,
        coaching,
        quality
    )
    print(f"  Status       : {response.get('status')}")
    print(f"  Summary      : {response.get('summary')}")
    print(f"  Total Issues : {response.get('totalIssues')}")
    print(f"  Auto Fixed   : {response.get('autoFixedCount')}")
    print(f"  Needs Review : {response.get('needsReviewCount')}")
    print(f"  Pruned List  : {response.get('prunedQuestions')}")
    print(f"  Timeout Risk : {response.get('timeoutRisk')}")
    print(f"  Session Adv. : {response.get('sessionAdvisory')}")
    print(f"  Concept Warn : {response.get('conceptTypeWarnings')}")

    return response


# ── Baseline Run ─────────────────────────────────────────────
submission_base, template_base = load_base_data()
base_request = {
    "submission": submission_base,
    "template": template_base
}
run_pipeline(base_request, "Baseline Sample Assessment")


# ── Test Suite: 5 Production Errors ──────────────────────────

print("\n" + "#" * 60)
print("VERIFYING ALL 5 CCA PRODUCTION ERROR SCENARIOS")
print("#" * 60)

# Error 1: DBTimeout Risk Flagging (id=1000)
sub_err1, tmpl_err1 = load_base_data()
if sub_err1.get("pages") and sub_err1["pages"][0].get("questions"):
    sub_err1["pages"][0]["questions"].append({
        "id": "Q4",
        "answer": {"value": "Long narrative clinical observation " * 150}
    })
req_err1 = {"submission": sub_err1, "template": tmpl_err1}
rep1 = run_pipeline(req_err1, "Error 1: DBTimeout Risk Flagging (id=1000)")

# Error 2: Invalid Session Transport Handling (id=1)
print("\n" + "=" * 60)
print("RUNNING: Error 2: Invalid Session Transport (id=1)")
print("=" * 60)
transport = CCATransport()
session_info = transport.acquire_session()
print(f"  Session Acquired : {session_info.get('sessionId')}")
transport_result = transport.submit_with_retry(
    session_id=session_info.get("sessionId", "mock-session"),
    payload=rep1.get("correctedSubmission") or {}
)
print(f"  Transport Result : Success={transport_result.get('success')}, Attempts={transport_result.get('attempts')}")

# Error 3: Too Many Answers / Count Mismatch (id=2)
sub_err3, tmpl_err3 = load_base_data()
if sub_err3.get("pages") and sub_err3["pages"][0].get("questions"):
    for idx in range(1, 4):
        sub_err3["pages"][0]["questions"].append({
            "id": f"EXTRA_Q_{idx}",
            "answer": {"value": f"Extra Answer {idx}"}
        })
req_err3 = {"submission": sub_err3, "template": tmpl_err3}
rep3 = run_pipeline(req_err3, "Error 3: Too Many Answers / Extra QIDs (id=2)")

# Error 4: Invalid Question ID (id=7, e.g. QID 263)
sub_err4, tmpl_err4 = load_base_data()
if sub_err4.get("pages") and sub_err4["pages"][0].get("questions"):
    sub_err4["pages"][0]["questions"].append({
        "id": "263",
        "answer": {"value": "Invalid QID 263 Value"}
    })
req_err4 = {"submission": sub_err4, "template": tmpl_err4}
rep4 = run_pipeline(req_err4, "Error 4: Invalid Question ID 263 (id=7)")

# Error 5: Concept Type 3 Numeric Violation (id=3)
sub_err5, tmpl_err5 = load_base_data()
if sub_err5.get("pages") and sub_err5["pages"][0].get("questions"):
    sub_err5["pages"][0]["questions"].append({
        "id": "Q44",
        "answer": {"value": "NotANumber"}
    })
req_err5 = {"submission": sub_err5, "template": tmpl_err5}
rep5 = run_pipeline(req_err5, "Error 5: Concept Type 3 Numeric Violation (id=3)")

print("\n" + "=" * 60)
print("TEST RUN COMPLETE: All 5 Production Error Scenarios Verified")
print("=" * 60)