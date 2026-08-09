# Quick test without needing HTTP connection
# Tests all 5 agents directly in Python
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.intake_agent import IntakeAgent
from agents.classifier_agent import ClassifierAgent
from agents.format_validator import FormatValidatorAgent
from agents.correction_agent import CorrectionAgent
from agents.report_agent import ReportAgent
from services.ai_service import AIService

# Load test request
with open('sample_data/submission.json', 'r') as f:
    submission_data = json.load(f)

# Load full template separately
with open('sample_data/template.json', 'r') as f:
    template_data = json.load(f)

# Combine into request
request_data = {
    "submission": submission_data,
    "template": template_data
}

# Run Agent 1
print("\n[Agent 1] Intake Agent...")
intake = IntakeAgent()
intake_result = intake.process(request_data)
print(f"  Members ID : {intake_result.get('member_id')}")
print(f"  Template   : {intake_result.get('template_name')}")
print(f"  Answers    : {intake_result.get('answer_count')}")
print(f"  Questions  : {intake_result.get('question_count')}")

# Run Agent 2
print("\n[Agent 2] Classifier Agent...")
classifier = ClassifierAgent()
classification = classifier.process(intake_result)
print(f"  Error Type : {classification.get('error_type')}")
print(f"  Escalate   : {classification.get('escalate')}")

# Run Agent 3
print("\n[Agent 3] Format Validator...")
validator = FormatValidatorAgent()
issues = validator.process(intake_result)
print(f"  Issues Found: {len(issues)}")
for issue in issues:
    print(f"    - [{issue['severity']}] {issue['questionId']}: "
          f"{issue['description'][:60]}...")
# DEBUG - check specific questions
print("\n[DEBUG] Checking specific questions:")

# Check Q21 - should be required because Q20=Yes
q21_answer = intake_result['submitted_answers'].get('Q21', {})
q20_answer = intake_result['submitted_answers'].get('Q20', {})
print(f"  Q20 value: '{q20_answer.get('value', '')}'")
print(f"  Q21 value: '{q21_answer.get('value', '')}'")

# Check Q44 - should fail numeric with whitespace
q44_answer = intake_result['submitted_answers'].get('Q44', {})
print(f"  Q44 value: '{q44_answer.get('value', '')}'")

# Check template Q44 definition
q44_template = intake_result['template_questions'].get('Q44', {})
print(f"  Q44 template type: '{q44_template.get('type', '')}'")
print(f"  Q44 enabled: '{q44_template.get('enabled', '')}'")

# Check conditional rules loaded
print(f"\n  Conditional rules count: {len(intake_result['conditional_rules'])}")
for rule in intake_result['conditional_rules'][:3]:
    print(f"  Rule {rule['id']}: {rule['statement']}")
# Run Agent 4
print("\n[Agent 4] Correction Agent...")
ai_service = AIService()
corrector = CorrectionAgent(ai_service)
corrected_issues, corrected_answers = corrector.process(
    issues, intake_result
)
auto_fixed = sum(1 for i in corrected_issues if i.get('autoFixed'))
print(f"  Auto Fixed  : {auto_fixed}")
print(f"  Needs Review: {len(corrected_issues) - auto_fixed}")
if corrected_answers:
    print(f"  Corrections : {corrected_answers}")

# Run Agent 5
print("\n[Agent 5] Report Agent...")
reporter = ReportAgent()
response = reporter.process(
    intake_result,
    corrected_issues,
    corrected_answers
)
print(f"  Status  : {response.get('status')}")
print(f"  Summary : {response.get('summary')}")
print(f"  Total   : {response.get('totalIssues')}")
print(f"  Fixed   : {response.get('autoFixedCount')}")
print(f"  Review  : {response.get('needsReviewCount')}")

print("\n" + "=" * 60)
print("Full Response:")
print("=" * 60)
print(json.dumps(response, indent=2))