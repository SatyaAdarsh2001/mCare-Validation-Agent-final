# ============================================================
# AGENT 1: Intake Agent
# ============================================================
# PURPOSE:
#   First agent in the pipeline. Receives the raw request
#   containing submission payload + template JSON.
#   Parses, organizes, and prepares data for all other agents.
#
# ANALOGY FOR PPT:
#   Think of this as the "receptionist" — takes the incoming
#   assessment, reads it carefully, organizes all the info
#   into a clean structured format before passing it forward.
#
# INPUT:  Raw request JSON from Angular
# OUTPUT: IntakeContext (structured dict used by all agents)
# ============================================================

import logging

logger = logging.getLogger(__name__)


class IntakeAgent:

    def process(self, request_data: dict) -> dict:
        """
        Main method called by app.py
        Parses the raw request and returns IntakeContext
        """
        try:
            logger.info("Intake Agent: Parsing request...")

            # ── Step 1: Extract top-level sections ─────────
            # Request must have both 'submission' and 'template'
            submission = request_data.get("submission")
            template   = request_data.get("template")

            # Validate both sections exist
            if not submission:
                return {"error": "Missing 'submission' in request body"}
            if not template:
                return {"error": "Missing 'template' in request body"}

            # ── Step 2: Extract submission fields ───────────
            # These are the actual answers the Care Manager filled
            member_id    = submission.get("MemberId", "")
            state_id     = submission.get("StateID", "")
            template_guid = submission.get("templateGuid", "")
            version      = submission.get("version", 1)
            source       = submission.get("source", "")
            score        = submission.get("score", "")
            completed_date = submission.get("completedDate", "")
            case_id      = submission.get("caseId", "")
            registrar    = submission.get("Registrar", "")
            pages        = submission.get("pages", [])

            # ── Step 3: Extract template fields ────────────
            template_id   = template.get("id")
            template_name = template.get("name", "Unknown Assessment")
            template_rules = template.get("rules", [])
            template_pages = template.get("pages", [])

            # ── Step 4: Build submitted_answers dictionary ──
            # Key: question ID (e.g. "Q1")
            # Value: the answer value string
            # This gives O(1) lookup speed when validating
            #
            # Real mCare payload structure:
            # pages → [{ id, questions → [{ id, answer: { value } }] }]
            submitted_answers = {}

            for page in pages:
                page_id = page.get("id", "")
                questions = page.get("questions", [])

                for q in questions:
                    q_id    = q.get("id", "")        # e.g. "Q1"
                    answer  = q.get("answer", {})
                    value   = answer.get("value", "") if answer else ""

                    if q_id:
                        submitted_answers[q_id] = {
                            "value"  : value,
                            "page_id": page_id
                        }

            logger.info(
                f"Intake: Found {len(submitted_answers)} answered questions"
            )

            # ── Step 5: Build template_questions dictionary ─
            # Key: question ID (e.g. "Q1")
            # Value: full question definition including rules
            #
            # Real mCare template structure:
            # pages → sections → subsections → questions
            template_questions = {}

            for t_page in template_pages:
                t_page_id = t_page.get("id", "")
                sections  = t_page.get("sections", [])

                for section in sections:
                    subsections = section.get("subsections", [])

                    for subsection in subsections:
                        questions = subsection.get("questions", [])

                        for q in questions:
                            q_id = q.get("id", "") # e.g. "Q1", "T1"

                            if q_id:
                                template_questions[q_id] = {
                                    "id"             : q_id,
                                    "name"           : q.get("name", ""),
                                    "type"           : q.get("type", ""),
                                    "enabled"        : q.get("enabled", True),
                                    "hidden"         : q.get("hidden", False),
                                    "validationRules": q.get(
                                        "validationRules", {}
                                    ),
                                    "options"        : q.get("options", []),
                                    "page_id"        : t_page_id
                                }

            logger.info(
                f"Intake: Found {len(template_questions)} template questions"
            )

            # ── Step 6: Build conditional rules lookup ──────
            # From template "rules" array
            # These define: if Q_x = value → Q_y becomes required
            # Example from WI RN 10 Day:
            #   R4: if Q20 (hospitalized) = Yes → Q21 enabled
            conditional_rules = []

            for rule in template_rules:
                conditional_rules.append({
                    "id"         : rule.get("id", ""),
                    "questions"  : rule.get("questions", []),
                    "actionSets" : rule.get("actionSets", []),
                    "statement"  : rule.get("statement", ""),
                    "type"       : rule.get("type", "")
                })

            logger.info(
                f"Intake: Found {len(conditional_rules)} conditional rules"
            )

            # ── Step 7: Count validation ────────────────────
            # Used by Classifier Agent to detect template issues
            # If answers >> template questions = possible issue
            answer_count   = len(submitted_answers)
            question_count = len([
                q for q_id, q in template_questions.items()
                if not q_id.startswith("T")  # exclude textblocks
            ])

            # ── Step 8: Return IntakeContext ────────────────
            # This dict is passed to ALL subsequent agents
            intake_context = {
                # Submission metadata
                "member_id"      : member_id,
                "state_id"       : state_id,
                "template_guid"  : template_guid,
                "version"        : version,
                "source"         : source,
                "score"          : score,
                "completed_date" : completed_date,
                "case_id"        : case_id,
                "registrar"      : registrar,

                # Template metadata
                "template_id"    : template_id,
                "template_name"  : template_name,

                # Core data structures (used by all agents)
                "submitted_answers"  : submitted_answers,
                "template_questions" : template_questions,
                "conditional_rules"  : conditional_rules,

                # Raw data (kept for building corrected response)
                "original_submission": submission,
                "original_template"  : template,

                # Counts for classifier
                "answer_count"   : answer_count,
                "question_count" : question_count,

                # Summary for logging
                "summary": (
                    f"Member: {member_id} | "
                    f"Template: {template_name} | "
                    f"Answers: {answer_count} | "
                    f"Questions: {question_count}"
                ),

                # No error
                "error": None
            }

            return intake_context

        except Exception as e:
            logger.error(f"Intake Agent error: {str(e)}", exc_info=True)
            return {
                "error": f"Intake Agent failed: {str(e)}"
            }