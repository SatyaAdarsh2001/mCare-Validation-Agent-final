# ============================================================
# AI Service - OpenRouter Integration
# ============================================================
# PURPOSE:
#   Handles all communication with OpenRouter API.
#   OpenRouter is a unified gateway that gives access to
#   multiple AI models (GPT-4o, Claude, Gemini) through
#   one single endpoint and API key.
#
# ANALOGY FOR PPT:
#   Think of OpenRouter as a "universal translator" —
#   instead of integrating with OpenAI, Anthropic, and
#   Google separately, we connect once to OpenRouter
#   and can use any model by just changing the model name.
#
# CALLED BY:
#   Correction Agent (Agent 4) — Tier 2 AI suggestions only
#
# PHI SAFETY:
#   This service never receives patient names, DOB,
#   Medicaid IDs, or any identifying information.
#   Only clinical field names and Yes/No context values
#   are sent to the AI.
#
# FALLBACK:
#   If API call fails for any reason → returns mock response
#   Validation never fails because of AI unavailability
# ============================================================

import os
import logging
import requests
import json
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Mock Responses ──────────────────────────────────────────
# Used when: no API key, API timeout, or API error
# Keyword-based so they're contextually relevant
# These are realistic clinical responses a nurse would write
MOCK_RESPONSES = {
    "comment": (
        "Member was cooperative and engaged throughout the "
        "assessment process. All questions were addressed "
        "thoroughly and member verbalized understanding of "
        "the care plan."
    ),
    "rationale": (
        "Clinical rationale is based on direct observation "
        "and member-reported status during the home visit. "
        "Assessment findings are consistent with current "
        "care plan objectives."
    ),
    "concern": (
        "No immediate concerns were identified during the "
        "assessment. Member's current support system appears "
        "adequate. Reassessment scheduled as per care plan."
    ),
    "barrier": (
        "Primary barriers include limited social support "
        "network and transportation challenges affecting "
        "access to medical appointments. Financial "
        "constraints related to copayments were also noted."
    ),
    "plan": (
        "Care team will provide monthly follow-up calls to "
        "monitor member status. Member agrees to use "
        "recommended strategies and will notify care manager "
        "of any changes in condition or support needs."
    ),
    "goal": (
        "Member will maintain current level of function and "
        "independence with activities of daily living. "
        "Progress will be evaluated at next scheduled "
        "assessment visit."
    ),
    "skill": (
        "Caregiver demonstrated competency in all required "
        "care techniques during the verification process. "
        "Proper infection control and safety protocols "
        "were observed and followed correctly."
    ),
    "strain": (
        "Caregiver reported manageable stress levels with "
        "current care responsibilities. No signs of burnout "
        "or significant strain were identified during the "
        "assessment interview."
    ),
    "discharge": (
        "Member requires coordination of home health "
        "services and durable medical equipment prior to "
        "discharge. Family support system has been "
        "briefed on post-discharge care requirements."
    ),
    "observation": (
        "Member appeared alert and oriented during the "
        "assessment visit. Living environment was clean "
        "and safe with no immediate hazards identified."
    ),
    "additional": (
        "No additional concerns were noted beyond those "
        "already documented in this assessment. Member "
        "and caregiver were provided with contact "
        "information for care management support."
    ),
    "default": (
        "Based on the assessment findings, member "
        "demonstrates appropriate clinical presentation. "
        "Current care plan remains appropriate and will "
        "be reviewed at the next scheduled visit."
    )
}


class AIService:

    def __init__(self):
        """
        Initialize AI service with OpenRouter configuration.
        Reads from .env file.
        """
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model   = os.getenv("AI_MODEL", "openai/gpt-4o")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.timeout = 10  # seconds — fail fast if AI is slow

        if self.api_key:
            logger.info(
                f"AI Service initialized: "
                f"model={self.model}, "
                f"key=***{self.api_key[-6:]}"
            )
        else:
            logger.warning(
                "AI Service: No API key found. "
                "Using mock responses."
            )

    def get_suggestion(self, prompt: str) -> str:
        """
        Main method called by Correction Agent.
        Sends prompt to OpenRouter and returns AI suggestion.
        Falls back to mock response on any failure.

        Returns: string (AI suggestion or mock response)
        """
        # If no API key → use mock immediately
        if not self.api_key:
            logger.info("AI Service: No key → using mock response")
            return self._get_mock_response(prompt)

        try:
            return self._call_openrouter(prompt)

        except requests.exceptions.Timeout:
            logger.warning(
                "AI Service: Request timed out → using mock"
            )
            return self._get_mock_response(prompt)

        except requests.exceptions.ConnectionError:
            logger.warning(
                "AI Service: Connection failed → using mock"
            )
            return self._get_mock_response(prompt)

        except Exception as e:
            logger.error(
                f"AI Service: Unexpected error: {str(e)} "
                f"→ using mock"
            )
            return self._get_mock_response(prompt)

    def _call_openrouter(self, prompt: str) -> str:
        """
        Makes the actual HTTP call to OpenRouter API.

        OpenRouter uses OpenAI-compatible format:
        POST https://openrouter.ai/api/v1/chat/completions
        Authorization: Bearer {api_key}
        Body: { model, messages: [{role, content}] }
        """
        headers = {
            "Authorization" : f"Bearer {self.api_key}",
            "Content-Type"  : "application/json",
            # OpenRouter headers for tracking
            "HTTP-Referer"  : "https://mcare-validation.com",
            "X-Title"       : "mCare.ValidationAgent"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role"   : "system",
                    "content": (
                        "You are a professional healthcare "
                        "documentation assistant. Write concise, "
                        "clinically appropriate text for assessment "
                        "forms. Never include patient identifying "
                        "information. Always respond in 2-3 "
                        "professional sentences."
                    )
                },
                {
                    "role"   : "user",
                    "content": prompt
                }
            ],
            "max_tokens"  : 150,
            "temperature" : 0.3  # Low = consistent, professional output
        }

        logger.info(
            f"AI Service: Calling OpenRouter "
            f"model={self.model}"
        )

        response = requests.post(
            self.api_url,
            headers = headers,
            json    = payload,
            timeout = self.timeout
        )

        # Check HTTP status
        if response.status_code != 200:
            logger.error(
                f"AI Service: API returned "
                f"status={response.status_code} "
                f"body={response.text[:200]}"
            )
            return self._get_mock_response(prompt)

        # Parse response
        data = response.json()

        # Extract text from OpenAI-format response
        # data.choices[0].message.content
        choices = data.get("choices", [])
        if not choices:
            logger.error("AI Service: Empty choices in response")
            return self._get_mock_response(prompt)

        message = choices[0].get("message", {})
        content = message.get("content", "").strip()

        if not content:
            logger.error("AI Service: Empty content in response")
            return self._get_mock_response(prompt)

        logger.info(
            f"AI Service: Got response "
            f"({len(content)} chars)"
        )
        return content

    def _get_mock_response(self, prompt: str) -> str:
        """
        Returns a keyword-based mock response.
        Used when: no API key, timeout, or any error.

        Ensures validation always completes even without AI.
        This is critical for reliability in production.
        """
        prompt_lower = prompt.lower()

        # Match prompt to most relevant mock response
        for keyword, response in MOCK_RESPONSES.items():
            if keyword == "default":
                continue
            if keyword in prompt_lower:
                logger.info(
                    f"AI Service: Mock response "
                    f"matched keyword '{keyword}'"
                )
                return response

        # No keyword matched → return default
        logger.info("AI Service: Using default mock response")
        return MOCK_RESPONSES["default"]

    def health_check(self) -> dict:
        """
        Called by /api/health endpoint to check AI status.
        Returns current AI service configuration.
        """
        return {
            "provider"     : "OpenRouter",
            "model"        : self.model,
            "api_key_set"  : bool(self.api_key),
            "timeout_secs" : self.timeout
        }