# ============================================================
# Molina.mCare.ValidationAgent - Main Application Entry Point
# ============================================================
# This is the main Flask application that:
# 1. Creates the API server
# 2. Defines the endpoints Angular frontend will call
# 3. Orchestrates all 5 agents in sequence
# ============================================================

import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import all 5 agents
from agents.intake_agent import IntakeAgent
from agents.classifier_agent import ClassifierAgent
from agents.format_validator import FormatValidatorAgent
from agents.correction_agent import CorrectionAgent
from agents.report_agent import ReportAgent

# Import AI service
from services.ai_service import AIService

# ── Setup Logging ──────────────────────────────────────────
# Logs help us trace what each agent does during validation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ── Create Flask App ───────────────────────────────────────
app = Flask(__name__)

# Enable CORS so Angular (running on port 4200) can call
# this API (running on port 5000) without browser blocking
CORS(app, origins="*")

# ── Initialize Services ────────────────────────────────────
ai_service = AIService()

# ── Initialize Agents ──────────────────────────────────────
intake_agent     = IntakeAgent()
classifier_agent = ClassifierAgent()
validator_agent  = FormatValidatorAgent()
correction_agent = CorrectionAgent(ai_service)
report_agent     = ReportAgent()


# ============================================================
# ENDPOINT 1: Health Check
# GET /api/health
# Angular calls this to check if backend is running
# ============================================================
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "Molina.mCare.ValidationAgent",
        "version": "1.0.0",
        "ai_provider": os.getenv('AI_MODEL', 'openai/gpt-4o')
    }), 200

@app.route('/')
@app.route('/ui')
def serve_ui():
    return """
    <html>
    <body>
    <h1>Molina mCare Validation Agent</h1>
    <p>Backend is running!</p>
    <a href="/api/health">Check Health</a>
    </body>
    </html>
    """
# ============================================================
# ENDPOINT 2: Validate Assessment
# POST /api/validate
# This is the main endpoint - Angular sends the assessment
# payload + template here, and gets back validation results
# ============================================================
@app.route('/api/validate', methods=['POST'])
def validate_assessment():
    try:
        # ── Step 1: Get request body ───────────────────────
        request_data = request.get_json()

        if not request_data:
            return jsonify({
                "error": "Request body is required"
            }), 400

        logger.info("=" * 60)
        logger.info("New validation request received")
        logger.info("=" * 60)

        # ── Step 2: Run Agent 1 - Intake ───────────────────
        # Parses the raw JSON, extracts submission + template
        # Builds lookup dictionaries for fast access
        logger.info("Agent 1: Intake Agent starting...")
        intake_result = intake_agent.process(request_data)

        if intake_result.get("error"):
            return jsonify({
                "status": "error",
                "message": intake_result["error"]
            }), 400

        logger.info(f"Agent 1 complete: {intake_result['summary']}")

        # ── Step 3: Run Agent 2 - Classifier ───────────────
        # Determines if this is a UserError, TemplateIssue,
        # or SystemIssue — escalates immediately if needed
        logger.info("Agent 2: Classifier Agent starting...")
        classification = classifier_agent.process(intake_result)

        if classification.get("escalate"):
            # Template or System issue — skip validation
            # Route to appropriate support team
            logger.info(f"Agent 2: Escalating - {classification['reason']}")
            return jsonify(
                report_agent.build_escalation_response(classification)
            ), 200

        logger.info(f"Agent 2 complete: {classification['error_type']}")

        # ── Step 4: Run Agent 3 - Format Validator ─────────
        # Finds ALL validation issues using rules (no AI)
        # Checks required fields, data types, conditional logic
        logger.info("Agent 3: Format Validator starting...")
        issues = validator_agent.process(intake_result)
        logger.info(f"Agent 3 complete: {len(issues)} issues found")

        # ── Step 5: Run Agent 4 - Correction ───────────────
        # Tier 1: Auto-fixes deterministic issues
        # Tier 2: Calls AI for complex clinical fields
        logger.info("Agent 4: Correction Agent starting...")
        corrected_issues, corrected_answers = correction_agent.process(
            issues, intake_result
        )
        logger.info("Agent 4 complete")

        # ── Step 6: Run Agent 5 - Report ───────────────────
        # Packages everything into clean JSON response
        # Determines final status and writes summary
        logger.info("Agent 5: Report Agent starting...")
        final_response = report_agent.process(
            intake_result,
            corrected_issues,
            corrected_answers
        )
        logger.info(f"Agent 5 complete: status={final_response['status']}")
        logger.info("=" * 60)

        return jsonify(final_response), 200

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500


# ============================================================
# Run the Flask development server
# ============================================================
if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    logger.info(f"Starting Molina.mCare.ValidationAgent on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)