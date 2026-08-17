# ============================================================
# AGENT 3: Format Validator Agent
# ============================================================

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Trizetto Concept Type mappings
CONCEPT_TYPE_MAP = {
    "textblock": 0,
    "text": 1,
    "textarea": 1,
    "buttongroup": 1,
    "date": 2,
    "number": 3
}


class FormatValidatorAgent:

    def process(self, intake_context: dict) -> list:
        issues = []

        try:
            submitted_answers = intake_context.get("submitted_answers", {})
            template_questions = intake_context.get("template_questions", {})
            conditional_rules = intake_context.get("conditional_rules", [])

            # Initialize pruned question list for CCA Error 3 & 4
            intake_context["pruned_question_ids"] = []

            logger.info(
                f"Format Validator: Checking {len(template_questions)}"
                f" questions against {len(submitted_answers)} answers"
            )

            # ── Step 1: Build conditional state ────────────
            conditional_state = self._evaluate_conditional_rules(
                conditional_rules,
                submitted_answers
            )

            # ── Step 2: Validate each template question ─────
            for q_id, question in template_questions.items():

                # Skip textblock questions — display only
                if question.get("type") == "textblock":
                    continue

                # Skip hidden questions
                if question.get("hidden", False):
                    continue

                # Check if question is currently enabled by template/rules
                is_enabled = self._is_question_enabled(
                    q_id, question, conditional_state
                )

                # Get submitted answer
                answer_data = submitted_answers.get(q_id)
                value = ""
                if answer_data:
                    value = answer_data.get("value", "")
                if value is None:
                    value = ""

                # Normalize whitespace-only input
                if isinstance(value, str) and value.strip() == "":
                    value = ""
                if q_id not in submitted_answers:
                 continue    

                validation_rules = question.get("validationRules", {})
                q_name = self._clean_question_name(question.get("name", q_id))
                q_type = question.get("type", "text")
                concept_type = question.get("conceptType", CONCEPT_TYPE_MAP.get(q_type, 1))

                # If disabled, skip required checks entirely
                if not is_enabled:
                    if answer_data and concept_type == 3 and value != "":
                        numeric_issue = self._validate_numeric(q_id, q_name, value, concept_type)
                        if numeric_issue:
                            issues.append(numeric_issue)
                    continue

                # ── Check A: Required field validation ─────
                required = validation_rules.get("required", False)

                if q_id in conditional_state.get("required", []):
                    required = True

                if required and self._is_empty(value):
                    issues.append(self._create_issue(
                        question_id=q_id,
                        question_name=q_name,
                        error_type="UserError",
                        severity="High",
                        description=(
                            f"Required field is empty. "
                            f"'{q_name}' must be completed before submission."
                        ),
                        original_value=value,
                        question_type=q_type
                    ))
                    continue

                # Skip remaining checks if field is empty and not required
                if self._is_empty(value):
                    continue

                # ── Check B: Date format validation ────────
                if q_type == "date" or concept_type == 2:
                    date_issue = self._validate_date(q_id, q_name, value, concept_type)
                    if date_issue:
                        issues.append(date_issue)
                    continue

                # ── Check C: Numeric field validation ──────
                if q_type == "number" or concept_type == 3:
                    numeric_issue = self._validate_numeric(q_id, q_name, value, concept_type)
                    if numeric_issue:
                        issues.append(numeric_issue)
                    continue

                # ── Check D: Button group validation ───────
                if q_type == "buttongroup":
                    options = question.get("options", [])
                    option_issue = self._validate_option(q_id, q_name, value, options)
                    if option_issue:
                        issues.append(option_issue)
                    continue

                # ── Check E: Max length validation ─────────
                max_length = validation_rules.get("maxLength", 0)
                if max_length and max_length > 0:
                    if len(str(value)) > max_length:
                        issues.append(self._create_issue(
                            question_id=q_id,
                            question_name=q_name,
                            error_type="UserError",
                            severity="Medium",
                            description=(
                                f"Answer exceeds maximum length of {max_length} characters. "
                                f"Current length: {len(str(value))}."
                            ),
                            original_value=value,
                            question_type=q_type
                        ))

            # ── Step 3: Check for unknown/out-of-template IDs ──
            for q_id, answer_info in submitted_answers.items():
                if q_id not in template_questions:
                    intake_context["pruned_question_ids"].append(q_id)
                    issues.append(self._create_issue(
                        question_id=q_id,
                        question_name=q_id,
                        error_type="TemplateIssue",
                        severity="Medium",
                        description=(
                            f"Question ID '{q_id}' does not exist in template version "
                            f"{intake_context.get('version', 'unknown')}. Auto-pruned from submission."
                        ),
                        original_value=answer_info.get("value", "") if isinstance(answer_info, dict) else "",
                        question_type="unknown"
                    ))

            logger.info(
                f"Format Validator: Found {len(issues)} issues "
                f"(Pruned IDs: {len(intake_context['pruned_question_ids'])})"
            )
            return issues

        except Exception as e:
            logger.error(f"Format Validator error: {str(e)}", exc_info=True)
            return [{
                "questionId": "SYSTEM",
                "questionName": "Format Validator",
                "errorType": "SystemIssue",
                "severity": "High",
                "description": f"Validator failed: {str(e)}",
                "originalValue": "",
                "correctedValue": None,
                "autoFixed": False,
                "suggestion": "Contact support team",
                "questionType": "unknown"
            }]

    # ── Private Validation Methods ──────────────────────────

    def _evaluate_conditional_rules(self, rules: list, submitted_answers: dict) -> dict:
        state = {
            "enabled": [],
            "disabled": [],
            "required": []
        }

        for rule in rules:
            statement = rule.get("statement", "")
            action_sets = rule.get("actionSets", [])
            rule_passes = self._evaluate_statement(statement, submitted_answers)

            for action_set in action_sets:
                actions = action_set.get("pass" if rule_passes else "fail", [])
                for action in actions:
                    prop = action.get("property", "")
                    questions = action.get("questions", [])
                    value = action.get("value")

                    if prop == "enabled":
                        if value is True:
                            state["enabled"].extend(questions)
                            state["required"].extend(questions)
                        elif value is False:
                            state["disabled"].extend(questions)

        return state

    def _evaluate_statement(self, statement: str, submitted_answers: dict) -> bool:
        try:
            if statement.strip() == "1 == 1":
                return True

            if "$member" in statement:
                return False

            # Pattern: Q{id}$selectedOptionIds == '{optionId}'
            selected_pattern = re.search(
                r"(Q\w+)\$selectedOptionIds\s*==\s*'(\w+)'",
                statement
            )
            if selected_pattern:
                q_id = selected_pattern.group(1)
                option_id = selected_pattern.group(2)
                answer_data = submitted_answers.get(q_id, {})
                value = answer_data.get("value", "") if isinstance(answer_data, dict) else str(answer_data)

                # Option ID 1 = Yes, Option ID 2 = No
                if option_id == "1" and value == "Yes":
                    return True
                if option_id == "2" and value == "No":
                    return True
                return False

            # Pattern: Q{id} > 0
            numeric_pattern = re.search(
                r"(Q\w+)\s*([><=!]+)\s*(\d+)",
                statement
            )
            if numeric_pattern:
                q_id = numeric_pattern.group(1)
                operator = numeric_pattern.group(2)
                compare = float(numeric_pattern.group(3))
                answer_data = submitted_answers.get(q_id, {})
                value = answer_data.get("value", "0") if isinstance(answer_data, dict) else str(answer_data)

                try:
                    num_value = float(value) if value else 0
                    if operator == ">": return num_value > compare
                    if operator == ">=": return num_value >= compare
                    if operator == "<": return num_value < compare
                    if operator == "<=": return num_value <= compare
                    if operator == "==": return num_value == compare
                    if operator == "!=": return num_value != compare
                except (ValueError, TypeError):
                    return False

            return False
        except Exception:
            return False

    def _is_question_enabled(self, q_id: str, question: dict, conditional_state: dict) -> bool:
        if q_id in conditional_state.get("disabled", []):
            return False
        if q_id in conditional_state.get("enabled", []):
            return True
        return question.get("enabled", True)

    def _validate_date(self, q_id: str, q_name: str, value: str, concept_type: int = 2) -> dict | None:
        date_formats = [
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in date_formats:
            try:
                datetime.strptime(str(value).strip(), fmt)
                return None
            except ValueError:
                continue

        return self._create_issue(
            question_id=q_id,
            question_name=q_name,
            error_type="UserError",
            severity="High",
            description=(
                f"Invalid date format: '{value}'. Expected format MM/DD/YYYY "
                f"(Trizetto concept type {concept_type})."
            ),
            original_value=value,
            question_type="date"
        )

    def _validate_numeric(self, q_id: str, q_name: str, value: str, concept_type: int = 3) -> dict | None:
        cleaned = str(value).strip()
        if not cleaned:
            return None

        try:
            float(cleaned)
            if cleaned != str(value):
                return self._create_issue(
                    question_id=q_id,
                    question_name=q_name,
                    error_type="UserError",
                    severity="Low",
                    description=(
                        f"Numeric field contains extra whitespace: '{value}'. "
                        f"Will be auto-corrected to '{cleaned}'."
                    ),
                    original_value=value,
                    question_type="number"
                )
            return None
        except ValueError:
            return self._create_issue(
                question_id=q_id,
                question_name=q_name,
                error_type="UserError",
                severity="High",
                description=(
                    f"Incorrect format: '{value}' is non-numeric. "
                    f"Field '{q_name}' violates Trizetto concept type {concept_type} (numeric)."
                ),
                original_value=value,
                question_type="number"
            )

    def _validate_option(self, q_id: str, q_name: str, value: str, options: list) -> dict | None:
        if not options:
            return None
        valid_values = [str(opt.get("value", "")) for opt in options]
        if str(value) not in valid_values:
            return self._create_issue(
                question_id=q_id,
                question_name=q_name,
                error_type="UserError",
                severity="Medium",
                description=(
                    f"Invalid selection: '{value}'. "
                    f"Valid options are: {', '.join(valid_values)}."
                ),
                original_value=value,
                question_type="buttongroup"
            )
        return None

    def _is_empty(self, value) -> bool:
        if value is None:
            return True
        return str(value).strip() == ""

    def _clean_question_name(self, name: str) -> str:
        clean = re.sub(r'<[^>]+>', '', name)
        clean = ' '.join(clean.split())
        if len(clean) > 80:
            clean = clean[:77] + "..."
        return clean.strip() or name

    def _create_issue(
        self,
        question_id: str,
        question_name: str,
        error_type: str,
        severity: str,
        description: str,
        original_value: str,
        question_type: str
    ) -> dict:
        return {
            "questionId": question_id,
            "questionName": question_name,
            "errorType": error_type,
            "severity": severity,
            "description": description,
            "originalValue": original_value,
            "correctedValue": None,
            "autoFixed": False,
            "suggestion": None,
            "questionType": question_type
        }