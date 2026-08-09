# ============================================================
# AGENT 3: Format Validator Agent
# ============================================================
# PURPOSE:
#   The core validation engine. Finds ALL data quality issues
#   in the submission using rules-based logic (NO AI here).
#   This agent catches 90-95% of all errors.
#
# ANALOGY FOR PPT:
#   Think of this as the "quality inspector" on a assembly
#   line. Goes through every single answer, checks it against
#   the template rules, and flags anything that doesn't meet
#   the standard. Fast, systematic, no guessing.
#
# VALIDATION CHECKS:
#   1. Required field empty or missing
#   2. Question in template but no answer submitted
#   3. Invalid date format
#   4. Non-numeric value in numeric field
#   5. Button group answer not in valid options
#   6. Max length exceeded
#   7. Conditional rule violations (if Q_x=Yes → Q_y required)
#   8. Textblock questions skipped (they never need answers)
#
# INPUT:  IntakeContext from Agent 1
# OUTPUT: List of ValidationIssue dicts
# ============================================================

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class FormatValidatorAgent:

    def process(self, intake_context: dict) -> list:
        """
        Main method called by app.py
        Validates all answers against template rules
        Returns list of issues found
        """
        issues = []

        try:
            submitted_answers  = intake_context.get(
                "submitted_answers", {}
            )
            template_questions = intake_context.get(
                "template_questions", {}
            )
            conditional_rules  = intake_context.get(
                "conditional_rules", []
            )

            logger.info(
                f"Format Validator: Checking {len(template_questions)}"
                f" questions against {len(submitted_answers)} answers"
            )

            # ── Step 1: Build conditional state ────────────
            # Evaluate which questions are enabled/required
            # based on the answers given
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

                # Check if this question is enabled
                is_enabled = self._is_question_enabled(
                    q_id, question, conditional_state
                )

                # Get the submitted answer for this question
                answer_data = submitted_answers.get(q_id)
                value = ""
                if answer_data:
                    value = answer_data.get("value", "")
                if value is None:
                    value = ""

                # Get validation rules from template
                validation_rules = question.get(
                    "validationRules", {}
                )
                q_name = self._clean_question_name(
                    question.get("name", q_id)
                )
                q_type = question.get("type", "text")

                if not is_enabled:
                    # Skip validation for disabled questions
                    # EXCEPT: numeric fields with submitted
                    # answers still need format validation
                    # Example: Q44 (Total Points) is disabled
                    # but still submitted — check whitespace
                    if answer_data and q_type == "number":
                        numeric_issue = self._validate_numeric(
                            q_id, q_name, value
                        )
                        if numeric_issue:
                            issues.append(numeric_issue)
                    continue

                # ── Check A: Required field validation ─────
                required = validation_rules.get("required", False)

                # Also check if conditional rule made it required
                if q_id in conditional_state.get("required", []):
                    required = True

                if required and self._is_empty(value):
                    issues.append(self._create_issue(
                        question_id    = q_id,
                        question_name  = q_name,
                        error_type     = "UserError",
                        severity       = "High",
                        description    = (
                            f"Required field is empty. "
                            f"'{q_name}' must be completed "
                            f"before submission."
                        ),
                        original_value = value,
                        question_type  = q_type
                    ))
                    continue

                # Skip remaining checks if field is empty
                # and not required
                if self._is_empty(value):
                    continue

                # ── Check B: Date format validation ────────
                if q_type == "date":
                    date_issue = self._validate_date(
                        q_id, q_name, value
                    )
                    if date_issue:
                        issues.append(date_issue)
                    continue

                # ── Check C: Numeric field validation ──────
                if q_type == "number":
                    numeric_issue = self._validate_numeric(
                        q_id, q_name, value
                    )
                    if numeric_issue:
                        issues.append(numeric_issue)
                    continue

                # ── Check D: Button group validation ───────
                if q_type == "buttongroup":
                    options = question.get("options", [])
                    option_issue = self._validate_option(
                        q_id, q_name, value, options
                    )
                    if option_issue:
                        issues.append(option_issue)
                    continue

                # ── Check E: Max length validation ─────────
                max_length = validation_rules.get("maxLength", 0)
                if max_length and max_length > 0:
                    if len(str(value)) > max_length:
                        issues.append(self._create_issue(
                            question_id    = q_id,
                            question_name  = q_name,
                            error_type     = "UserError",
                            severity       = "Medium",
                            description    = (
                                f"Answer exceeds maximum length of "
                                f"{max_length} characters. "
                                f"Current length: {len(str(value))}."
                            ),
                            original_value = value,
                            question_type  = q_type
                        ))

            # ── Step 3: Check for unknown question IDs ──────
            for q_id in submitted_answers:
                if q_id not in template_questions:
                    issues.append(self._create_issue(
                        question_id    = q_id,
                        question_name  = q_id,
                        error_type     = "TemplateIssue",
                        severity       = "Low",
                        description    = (
                            f"Answer submitted for question '{q_id}' "
                            f"which does not exist in template. "
                            f"This may indicate a template version "
                            f"mismatch."
                        ),
                        original_value = submitted_answers[q_id].get(
                            "value", ""
                        ),
                        question_type  = "unknown"
                    ))

            logger.info(
                f"Format Validator: Found {len(issues)} issues"
            )
            return issues

        except Exception as e:
            logger.error(
                f"Format Validator error: {str(e)}", exc_info=True
            )
            return [{
                "questionId"    : "SYSTEM",
                "questionName"  : "Format Validator",
                "errorType"     : "SystemIssue",
                "severity"      : "High",
                "description"   : f"Validator failed: {str(e)}",
                "originalValue" : "",
                "correctedValue": None,
                "autoFixed"     : False,
                "suggestion"    : "Contact support team",
                "questionType"  : "unknown"
            }]

    # ── Private Validation Methods ──────────────────────────

    def _evaluate_conditional_rules(
        self,
        rules: list,
        submitted_answers: dict
    ) -> dict:
        """
        Evaluates all conditional rules from the template.

        Real mCare example from WI RN 10 Day Assessment:
        R4: statement = "Q20$selectedOptionIds == '1'"
            pass: Q21 enabled = true
            fail: Q21 enabled = false, Q21 value = ""

        This means: if Q20 = Yes (option id 1) → Q21 is enabled
        AND required (because it was conditionally activated)
        """
        state = {
            "enabled" : [],
            "disabled": [],
            "required": []
        }

        for rule in rules:
            statement   = rule.get("statement", "")
            action_sets = rule.get("actionSets", [])

            # Evaluate the rule statement
            rule_passes = self._evaluate_statement(
                statement, submitted_answers
            )

            for action_set in action_sets:
                # Get actions based on pass/fail
                actions = action_set.get(
                    "pass" if rule_passes else "fail", []
                )

                for action in actions:
                    prop      = action.get("property", "")
                    questions = action.get("questions", [])
                    value     = action.get("value")

                    if prop == "enabled":
                        if value is True:
                            state["enabled"].extend(questions)
                            # When a question becomes enabled
                            # by a conditional rule → mark required
                            # This is how mCare conditional logic works:
                            # Q20=Yes → Q21 becomes enabled AND required
                            state["required"].extend(questions)
                        elif value is False:
                            state["disabled"].extend(questions)

        return state

    def _evaluate_statement(
        self,
        statement: str,
        submitted_answers: dict
    ) -> bool:
        """
        Evaluates a conditional rule statement.

        Real mCare statement formats:
        - "Q20$selectedOptionIds == '1'"  (button selected)
        - "Q44 > 0"                       (numeric comparison)
        - "1 == 1"                        (always true)
        - "( '$memberLOB' == '10' )"      (member attribute)
        """
        try:
            # Always true statement
            if statement.strip() == "1 == 1":
                return True

            # Member LOB statements — not available in validation
            # Default to false (safe default)
            if "$member" in statement:
                return False

            # Q{id}$selectedOptionIds == '{optionId}' pattern
            # Example: "Q20$selectedOptionIds == '1'"
            selected_pattern = re.search(
                r"(Q\w+)\$selectedOptionIds\s*==\s*'(\w+)'",
                statement
            )
            if selected_pattern:
                q_id      = selected_pattern.group(1)
                option_id = selected_pattern.group(2)
                answer_data = submitted_answers.get(q_id, {})
                value       = answer_data.get("value", "")

                # In mCare: Yes = option id 1, No = option id 2
                if option_id == "1" and value == "Yes":
                    return True
                if option_id == "2" and value == "No":
                    return True
                return False

            # Q{id} > 0 pattern (numeric comparison)
            numeric_pattern = re.search(
                r"(Q\w+)\s*([><=!]+)\s*(\d+)",
                statement
            )
            if numeric_pattern:
                q_id     = numeric_pattern.group(1)
                operator = numeric_pattern.group(2)
                compare  = float(numeric_pattern.group(3))
                answer_data = submitted_answers.get(q_id, {})
                value    = answer_data.get("value", "0")

                try:
                    num_value = float(value) if value else 0
                    if operator == ">"  : return num_value > compare
                    if operator == ">=" : return num_value >= compare
                    if operator == "<"  : return num_value < compare
                    if operator == "<=" : return num_value <= compare
                    if operator == "==" : return num_value == compare
                    if operator == "!=" : return num_value != compare
                except (ValueError, TypeError):
                    return False

            return False

        except Exception:
            return False

    def _is_question_enabled(
        self,
        q_id: str,
        question: dict,
        conditional_state: dict
    ) -> bool:
        """
        Determines if a question is currently enabled.
        Considers both template default and conditional rules.
        """
        # If explicitly disabled by a rule → disabled
        if q_id in conditional_state.get("disabled", []):
            return False

        # If explicitly enabled by a rule → enabled
        if q_id in conditional_state.get("enabled", []):
            return True

        # Use template default
        return question.get("enabled", True)

    def _validate_date(
        self, q_id: str, q_name: str, value: str
    ) -> dict | None:
        """
        Validates date fields.
        Accepts: MM/DD/YYYY, YYYY-MM-DD, ISO 8601 formats
        """
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
            question_id    = q_id,
            question_name  = q_name,
            error_type     = "UserError",
            severity       = "High",
            description    = (
                f"Invalid date format: '{value}'. "
                f"Expected format: MM/DD/YYYY or YYYY-MM-DD."
            ),
            original_value = value,
            question_type  = "date"
        )

    def _validate_numeric(
        self, q_id: str, q_name: str, value: str
    ) -> dict | None:
        """
        Validates numeric fields.
        Catches whitespace, letters, special characters.

        Real mCare error:
        'Incorrect format or the value is not of a numeric
         value. Question Id: 672'
        """
        cleaned = str(value).strip()

        if not cleaned:
            return None

        try:
            float(cleaned)
            # Valid number but has whitespace → flag for auto-fix
            if cleaned != str(value):
                return self._create_issue(
                    question_id    = q_id,
                    question_name  = q_name,
                    error_type     = "UserError",
                    severity       = "Low",
                    description    = (
                        f"Numeric field contains extra whitespace: "
                        f"'{value}'. Will be auto-corrected to "
                        f"'{cleaned}'."
                    ),
                    original_value = value,
                    question_type  = "number"
                )
            return None
        except ValueError:
            return self._create_issue(
                question_id    = q_id,
                question_name  = q_name,
                error_type     = "UserError",
                severity       = "High",
                description    = (
                    f"Invalid numeric value: '{value}'. "
                    f"Field '{q_name}' must contain numbers only. "
                    f"Remove any spaces, letters, or special "
                    f"characters."
                ),
                original_value = value,
                question_type  = "number"
            )

    def _validate_option(
        self,
        q_id: str,
        q_name: str,
        value: str,
        options: list
    ) -> dict | None:
        """
        Validates buttongroup answers.
        Answer must match one of the defined option values.
        """
        if not options:
            return None

        valid_values = [
            str(opt.get("value", "")) for opt in options
        ]

        if value not in valid_values:
            return self._create_issue(
                question_id    = q_id,
                question_name  = q_name,
                error_type     = "UserError",
                severity       = "Medium",
                description    = (
                    f"Invalid selection: '{value}'. "
                    f"Valid options are: "
                    f"{', '.join(valid_values)}."
                ),
                original_value = value,
                question_type  = "buttongroup"
            )

        return None

    def _is_empty(self, value) -> bool:
        """
        Checks if a value is empty.
        Catches: None, "", "   " (whitespace only)
        """
        if value is None:
            return True
        return str(value).strip() == ""

    def _clean_question_name(self, name: str) -> str:
        """
        Removes HTML tags from question names.
        Real mCare template has HTML in question names.
        """
        clean = re.sub(r'<[^>]+>', '', name)
        clean = ' '.join(clean.split())
        if len(clean) > 80:
            clean = clean[:77] + "..."
        return clean.strip() or name

    def _create_issue(
        self,
        question_id   : str,
        question_name : str,
        error_type    : str,
        severity      : str,
        description   : str,
        original_value: str,
        question_type : str
    ) -> dict:
        """
        Creates a standard ValidationIssue dict.
        """
        return {
            "questionId"    : question_id,
            "questionName"  : question_name,
            "errorType"     : error_type,
            "severity"      : severity,
            "description"   : description,
            "originalValue" : original_value,
            "correctedValue": None,
            "autoFixed"     : False,
            "suggestion"    : None,
            "questionType"  : question_type
        }