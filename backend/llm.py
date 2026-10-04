"""THE only file that talks to an LLM. To switch provider, add a class here
with the same methods and change get_llm().

Two providers with the same methods:
  GeminiProvider  calls Google Gemini
  NullProvider    always returns None, so callers use their fallback

Every method returns None when the LLM is unavailable or fails. Callers must
check for None and fall back; nothing here ever raises to the caller.
More methods (parse_text, clarify) are added in later steps.
"""

import json
import re

from backend.config import ATTRIBUTES, CONFIG, GEMINI_API_KEY

TAG_PROMPT = """You are helping a fabric and saree wholesaler catalogue their stock.
Look at the photo and describe the main product in it.
Answer with ONLY a JSON object with exactly these keys. Each value MUST be one
of the allowed values listed (copy it exactly). If unsure, pick the closest.

{allowed}
"""


def _allowed_values_text():
    return "\n".join(f'"{attr}": one of {values}' for attr, values in ATTRIBUTES.items())


def _parse_json(text):
    """Pull the first {...} block out of the model's answer."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class NullProvider:
    name = "none"
    available = False
    last_error = "No LLM configured (GEMINI_API_KEY is empty)"

    def tag_image(self, jpeg_bytes):
        return None


class GeminiProvider:
    name = "gemini"
    available = True

    def __init__(self, api_key):
        self.api_key = api_key
        self.model = CONFIG["llm"]["model"]
        self.timeout_ms = int(CONFIG["llm"]["timeout_seconds"] * 1000)
        self._client = None
        self.last_error = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=self.timeout_ms),
            )
        return self._client

    def _generate(self, contents):
        """One Gemini call that returns parsed JSON, or None on any failure."""
        try:
            from google.genai import types

            response = self._get_client().models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
            result = _parse_json(response.text)
            if result is None:
                self.last_error = "Gemini answered, but not with valid JSON"
            else:
                self.last_error = None
            return result
        except Exception as e:  # network, quota, bad key, timeout: never crash the app
            self.last_error = f"{type(e).__name__}: {str(e)[:200]}"
            print(f"[llm] Gemini call failed: {self.last_error}")
            return None

    def tag_image(self, jpeg_bytes):
        from google.genai import types

        prompt = TAG_PROMPT.format(allowed=_allowed_values_text())
        image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")
        return self._generate([image_part, prompt])


_llm = None


def get_llm():
    """The LLM the app should use. Same object every time."""
    global _llm
    if _llm is None:
        if CONFIG["llm"]["provider"] == "gemini" and GEMINI_API_KEY:
            _llm = GeminiProvider(GEMINI_API_KEY)
        else:
            _llm = NullProvider()
    return _llm
