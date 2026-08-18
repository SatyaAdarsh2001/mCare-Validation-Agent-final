# ============================================================
# AI Service - OpenRouter Integration
# ============================================================
# PURPOSE:
#   Centralized AI communication layer for mCare ValidationAgent.
#
# FEATURES:
#   - OpenRouter integration
#   - Purpose-specific structured JSON
#   - Cost-aware token limits
#   - Mock fallback
#   - LLM vs mock logging
#   - Robust JSON parsing
#
# PHI SAFETY:
#   This service should only receive PHI-safe prompts
#   prepared by CorrectionAgent.
# ============================================================

import os
import json
import logging
import requests

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# MOCK RESPONSES
# ============================================================

MOCK_RESPONSES = {

    "comment": (
        "Member was cooperative and engaged throughout the "
        "assessment process. All questions were addressed "
        "thoroughly and member verbalized understanding."
    ),

    "rationale": (
        "Clinical rationale is based on the information "
        "provided during the assessment and current care plan."
    ),

    "concern": (
        "No immediate concerns were identified based on "
        "the available assessment information."
    ),

    "barrier": (
        "Potential barriers should be reviewed based on "
        "the member's documented assessment responses."
    ),

    "plan": (
        "Care team will provide appropriate follow-up "
        "based on findings identified during assessment."
    ),

    "goal": (
        "Member will maintain current level of function "
        "and progress will be reviewed during follow-up."
    ),

    "skill": (
        "Caregiver demonstrated appropriate understanding "
        "of the required care techniques."
    ),

    "strain": (
        "Caregiver support needs should be reviewed "
        "based on the documented assessment findings."
    ),

    "discharge": (
        "Discharge planning should include coordination "
        "of required services and caregiver support."
    ),

    "observation": (
        "Assessment findings were documented based on "
        "the information provided during the visit."
    ),

    "additional": (
        "No additional concerns were identified beyond "
        "those already documented."
    ),

    "default": (
        "Based on the available assessment information, "
        "the current care plan should be reviewed as appropriate."
    )
}


class AIService:

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(self):

        self.api_key = os.getenv(
            "OPENROUTER_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "AI_MODEL",
            "openrouter/free"
        )

        self.api_url = (
            "https://openrouter.ai/api/v1/chat/completions"
        )

        self.timeout = int(
            os.getenv(
                "AI_TIMEOUT",
                "10"
            )
        )

        self.suggestion_max_tokens = int(
            os.getenv(
                "AI_SUGGESTION_MAX_TOKENS",
                "120"
            )
        )

        self.coaching_max_tokens = int(
            os.getenv(
                "AI_COACHING_MAX_TOKENS",
                "120"
            )
        )

        self.score_max_tokens = int(
            os.getenv(
                "AI_SCORE_MAX_TOKENS",
                "80"
            )
        )

        if self.api_key:

            logger.info(
                "AI Service initialized: "
                f"provider=OpenRouter, "
                f"model={self.model}, "
                f"key=***{self.api_key[-6:]}"
            )

        else:

            logger.warning(
                "AI Service: No API key found. "
                "Using mock responses."
            )

    # ========================================================
    # PUBLIC - SIMPLE SUGGESTION
    # ========================================================

    def get_suggestion(
        self,
        prompt: str
    ) -> str:

        result = self.get_structured_response(
            prompt=prompt,
            purpose="suggestion"
        )

        suggestion = result.get(
            "suggestion",
            ""
        )

        if suggestion:
            return suggestion

        return self._get_mock_response(prompt)

    # ========================================================
    # PUBLIC - STRUCTURED RESPONSE
    # ========================================================

    def get_structured_response(
        self,
        prompt: str,
        default_score: int = 7,
        purpose: str = "suggestion"
    ) -> dict:

        if not self.api_key:

            logger.info(
                "AI Service: No API key -> MOCK"
            )

            return self._get_mock_structured_response(
                prompt,
                default_score,
                purpose
            )

        try:

            return self._call_openrouter_structured(
                prompt=prompt,
                default_score=default_score,
                purpose=purpose
            )

        except requests.exceptions.Timeout:

            logger.warning(
                "AI Service: Request timeout -> MOCK"
            )

        except requests.exceptions.ConnectionError:

            logger.warning(
                "AI Service: Connection error -> MOCK"
            )

        except Exception as e:

            logger.error(
                f"AI Service: Unexpected error: {str(e)} -> MOCK"
            )

        return self._get_mock_structured_response(
            prompt,
            default_score,
            purpose
        )

    # ========================================================
    # OPENROUTER
    # ========================================================

    def _call_openrouter_structured(
        self,
        prompt: str,
        default_score: int,
        purpose: str
    ) -> dict:

        if purpose == "score":

            max_tokens = self.score_max_tokens

        elif purpose == "coaching":

            max_tokens = self.coaching_max_tokens

        else:

            max_tokens = self.suggestion_max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://mcare-validation.com",
            "X-Title": "mCare.ValidationAgent"
        }

        system_prompt = self._build_system_prompt(
            purpose
        )

        payload = {
            "model": self.model,

            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            "max_tokens": max_tokens,

            "temperature": 0.1
        }

        logger.info(
            "AI Service: REAL LLM CALL -> "
            f"model={self.model}, "
            f"purpose={purpose}, "
            f"max_tokens={max_tokens}"
        )

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:

            logger.error(
                "OpenRouter error: "
                f"status={response.status_code}, "
                f"body={response.text[:500]}"
            )

            return self._get_mock_structured_response(
                prompt,
                default_score,
                purpose
            )

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            raise ValueError(
                "OpenRouter response contained no choices"
            )

        message = choices[0].get(
            "message",
            {}
        )

        content = message.get(
            "content",
            ""
        )

        if not content:

            raise ValueError(
                "OpenRouter response contained empty content"
            )

        content = content.strip()

        logger.info(
            "AI Service: LLM response received "
            f"({len(content)} chars)"
        )

        parsed = self._parse_structured_json(
            content=content,
            default_score=default_score,
            purpose=purpose
        )

        if parsed is None:

            logger.warning(
                "AI Service: Invalid JSON -> MOCK"
            )

            return self._get_mock_structured_response(
                prompt,
                default_score,
                purpose
            )

        parsed["source"] = "llm"

        return parsed

    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    def _build_system_prompt(
        self,
        purpose: str
    ) -> str:

        if purpose == "score":

            return (
                "You are a healthcare documentation quality "
                "evaluator. "
                "Never include PHI. "
                "Do not invent facts. "
                "Evaluate only the information provided. "
                "Use concise language. "
                "Return ONLY valid JSON. "
                "Do not use markdown.\n\n"

                '{"score":7,'
                '"feedback":"brief feedback",'
                '"confidence":0.8}\n\n'

                "score must be an integer from 1 to 10. "
                "confidence must be between 0 and 1. "
                "Keep feedback under 20 words."
            )

        if purpose == "coaching":

            return (
                "You are a healthcare documentation coaching "
                "assistant. "
                "Never include PHI. "
                "Do not invent facts. "
                "Use concise clinical language. "
                "Return ONLY valid JSON. "
                "Do not use markdown.\n\n"

                '{"suggestion":"brief suggestion",'
                '"score":7,'
                '"feedback":"brief feedback",'
                '"confidence":0.8}\n\n'

                "Keep suggestion under 30 words. "
                "Keep feedback under 20 words. "
                "score must be 1 to 10. "
                "confidence must be 0 to 1."
            )

        return (
            "You are a healthcare documentation assistant. "
            "Never include PHI. "
            "Do not invent facts. "
            "Use concise clinical language. "
            "Return ONLY valid JSON. "
            "Do not use markdown.\n\n"

            '{"suggestion":"brief documentation suggestion",'
            '"score":7,'
            '"feedback":"brief feedback",'
            '"confidence":0.8}\n\n'

            "Keep suggestion under 30 words. "
            "Keep feedback under 20 words. "
            "score must be 1 to 10. "
            "confidence must be 0 to 1."
        )

    # ========================================================
    # JSON PARSER
    # ========================================================

    def _parse_structured_json(
        self,
        content: str,
        default_score: int,
        purpose: str
    ) -> dict | None:

        cleaned = content.strip()

        if cleaned.startswith("```"):

            lines = cleaned.splitlines()

            lines = lines[1:]

            if lines and lines[-1].strip() == "```":

                lines = lines[:-1]

            cleaned = "\n".join(
                lines
            ).strip()

        try:

            data = json.loads(
                cleaned
            )

        except json.JSONDecodeError as e:

            logger.error(
                f"JSON parsing failed: {e}"
            )

            return None

        if not isinstance(
            data,
            dict
        ):

            return None

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        if purpose == "score":

            try:

                score = int(
                    data.get(
                        "score",
                        default_score
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                score = default_score

            score = max(
                1,
                min(
                    10,
                    score
                )
            )

            feedback = str(
                data.get(
                    "feedback",
                    ""
                )
            ).strip()

            if not feedback:

                feedback = (
                    "Assessment quality evaluated "
                    "from available information."
                )

            try:

                confidence = float(
                    data.get(
                        "confidence",
                        0.75
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                confidence = 0.75

            confidence = max(
                0.0,
                min(
                    1.0,
                    confidence
                )
            )

            return {
                "score": score,
                "feedback": feedback,
                "confidence": round(
                    confidence,
                    2
                )
            }

        # ----------------------------------------------------
        # SUGGESTION / COACHING
        # ----------------------------------------------------

        suggestion = str(
            data.get(
                "suggestion",
                ""
            )
        ).strip()

        if not suggestion:

            return None

        try:

            score = int(
                data.get(
                    "score",
                    default_score
                )
            )

        except (
            TypeError,
            ValueError
        ):

            score = default_score

        score = max(
            1,
            min(
                10,
                score
            )
        )

        feedback = str(
            data.get(
                "feedback",
                ""
            )
        ).strip()

        if not feedback:

            feedback = (
                "AI-generated documentation feedback."
            )

        try:

            confidence = float(
                data.get(
                    "confidence",
                    0.75
                )
            )

        except (
            TypeError,
            ValueError
        ):

            confidence = 0.75

        confidence = max(
            0.0,
            min(
                1.0,
                confidence
            )
        )

        return {
            "suggestion": suggestion,
            "score": score,
            "feedback": feedback,
            "confidence": round(
                confidence,
                2
            )
        }

    # ========================================================
    # MOCK STRUCTURED RESPONSE
    # ========================================================

    def _get_mock_structured_response(
        self,
        prompt: str,
        default_score: int = 7,
        purpose: str = "suggestion"
    ) -> dict:

        if purpose == "score":

            return {
                "score": default_score,
                "feedback": (
                    "Mock quality score used because "
                    "the real LLM was unavailable."
                ),
                "confidence": 0.50,
                "source": "mock"
            }

        suggestion = self._get_mock_response(
            prompt
        )

        return {
            "suggestion": suggestion,
            "score": default_score,
            "feedback": (
                "Mock AI response used because "
                "the real LLM was unavailable."
            ),
            "confidence": 0.50,
            "source": "mock"
        }

    # ========================================================
    # MOCK TEXT
    # ========================================================

    def _get_mock_response(
        self,
        prompt: str
    ) -> str:

        prompt_lower = prompt.lower()

        for keyword, response in MOCK_RESPONSES.items():

            if keyword == "default":
                continue

            if keyword in prompt_lower:

                logger.info(
                    f"Mock response matched '{keyword}'"
                )

                return response

        return MOCK_RESPONSES[
            "default"
        ]

    # ========================================================
    # HEALTH CHECK
    # ========================================================

    def health_check(self) -> dict:

        return {
            "provider": "OpenRouter",
            "model": self.model,
            "api_key_set": bool(
                self.api_key
            ),
            "timeout_secs": self.timeout,
            "suggestion_max_tokens": (
                self.suggestion_max_tokens
            ),
            "coaching_max_tokens": (
                self.coaching_max_tokens
            ),
            "score_max_tokens": (
                self.score_max_tokens
            )
        }