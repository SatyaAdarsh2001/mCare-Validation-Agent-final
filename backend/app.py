# ============================================================
# Molina.mCare.ValidationAgent - Main Application Entry Point
# ============================================================

import os
import json
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from agents.intake_agent import IntakeAgent
from agents.classifier_agent import ClassifierAgent
from agents.format_validator import FormatValidatorAgent
from agents.correction_agent import CorrectionAgent
from agents.report_agent import ReportAgent
from services.ai_service import AIService
from services.cca_transport import CCATransport

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins="*")

ai_service       = AIService()
intake_agent     = IntakeAgent()
classifier_agent = ClassifierAgent()
validator_agent  = FormatValidatorAgent()
correction_agent = CorrectionAgent(ai_service)
report_agent     = ReportAgent()
cca_transport    = CCATransport()

# ── Helper: Pipeline Orchestrator ───────────────────────────
def _run_validation_pipeline(request_data: dict) -> tuple[dict, int]:
    """
    Executes the 5-agent sequence:
    Agent 1 (Intake) -> Agent 2 (Classifier) -> Agent 3 (Format Validator)
    -> Agent 4 (Correction) -> Agent 5 (Report)
    """
    logger.info("Agent 1: Intake Agent starting...")
    intake_result = intake_agent.process(request_data)

    if intake_result.get("error"):
        return {
            "status": "error",
            "message": intake_result["error"]
        }, 400

    logger.info(f"Agent 1 complete: {intake_result.get('summary', '')}")

    logger.info("Agent 2: Classifier Agent starting...")
    classification = classifier_agent.process(intake_result)

    if classification.get("escalate"):
        logger.info(f"Agent 2: Escalating - {classification.get('reason')}")
        return report_agent.build_escalation_response(classification), 200

    logger.info(f"Agent 2 complete: {classification.get('error_type')}")

    logger.info("Agent 3: Format Validator starting...")
    issues = validator_agent.process(intake_result)
    logger.info(f"Agent 3 complete: {len(issues)} issues found")

    logger.info("Agent 4: Correction Agent starting...")
    corrected_issues, corrected_answers, coaching_summary, quality_score = (
        correction_agent.process(issues, intake_result)
    )
    logger.info("Agent 4 complete")

    logger.info("Agent 5: Report Agent starting...")
    final_response = report_agent.process(
        intake_result,
        corrected_issues,
        corrected_answers,
        coaching_summary,
        quality_score
    )
    logger.info(f"Agent 5 complete: status={final_response.get('status')}")

    return final_response, 200

# ── Serve Angular UI ───────────────────────────────────────
FRONTEND_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "frontend", "dist", "frontend", "browser"
)

@app.route('/ui')
def serve_ui():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/ui/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/<path:filename>')
def serve_root_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# ── Health Check ───────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "Molina.mCare.ValidationAgent",
        "version": "1.0.0",
        "ai_provider": os.getenv('AI_MODEL', 'openai/gpt-4o'),
        "cca_configured": cca_transport.is_configured()
    }), 200

# ── Validate Assessment (Read-Only) ────────────────────────
@app.route('/api/validate', methods=['POST'])
def validate_assessment():
    try:
        request_data = request.get_json()

        if not request_data:
            return jsonify({"error": "Request body is required"}), 400

        logger.info("=" * 60)
        logger.info("New validation request received (/api/validate)")
        logger.info("=" * 60)

        response_data, status_code = _run_validation_pipeline(request_data)
        logger.info("=" * 60)

        return jsonify(response_data), status_code

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

# ── Submit Assessment (Validate + Transmit with Retry) ──────
@app.route('/api/submit', methods=['POST'])
def submit_assessment():
    try:
        request_data = request.get_json()

        if not request_data:
            return jsonify({"error": "Request body is required"}), 400

        logger.info("=" * 60)
        logger.info("New submission request received (/api/submit)")
        logger.info("=" * 60)

        # Step 1: Run validation pipeline
        response_data, status_code = _run_validation_pipeline(request_data)

        # Halt submission if pipeline failed or escalated
        if status_code != 200 or response_data.get("status") == "escalated":
            return jsonify(response_data), status_code

        # Step 2: Acquire session
        session_info = cca_transport.acquire_session()
        session_id = session_info.get("sessionId", "")

        # Step 3: Transmit payload with retry logic (catches timeout & session expiry)
        payload_to_submit = response_data.get("correctedSubmission") or request_data
        transport_result = cca_transport.submit_with_retry(
            session_id=session_id,
            payload=payload_to_submit
        )

        response_data["transport"] = transport_result
        logger.info(f"Submission complete: transport_success={transport_result.get('success')}")
        logger.info("=" * 60)

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Unexpected error during submission: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Internal server error: {str(e)}"
        }), 500

@app.route('/api/sample-data/prod-errors', methods=['GET'])
def get_prod_errors_sample():
    file_path = os.path.join(os.path.dirname(__file__), "sample_data", "prod_errors_submission.json")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": f"Failed to load sample: {str(e)}"}), 500
        
if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    logger.info(f"Starting Molina.mCare.ValidationAgent on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

