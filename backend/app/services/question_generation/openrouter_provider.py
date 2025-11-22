"""
OpenRouter provider for question generation.

This module implements the QuestionGenerationProvider interface using OpenRouter
for cloud-based LLM inference with support for multiple models.
"""

import json
import re
import uuid
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.schemas.question import GeneratedQuestion
from app.exceptions import OllamaConnectionException
from .base import QuestionGenerationProvider


# Configure logger
logger = logging.getLogger(__name__)


class OpenRouterProvider(QuestionGenerationProvider):
    """
    OpenRouter-based question generation provider.
    
    Uses OpenRouter API for cloud-based LLM inference, supporting multiple models
    from various providers (OpenAI, Anthropic, Google, etc.).
    """
    
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def __init__(self):
        """Initialize OpenRouter provider with API client."""
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.site_url = settings.openrouter_site_url
        self.site_name = settings.openrouter_site_name
        
        # Create HTTP client with timeout configuration
        self.client = httpx.Client(timeout=120.0)
        
        logger.info(
            "Initialized OpenRouter provider",
            extra={
                "model": self.model,
                "has_api_key": bool(self.api_key),
                "site_url": self.site_url or "not_set",
                "site_name": self.site_name or "not_set"
            }
        )
    
    def _extract_json_from_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract and parse JSON from LLM response.
        
        Handles cases where the model adds prose before/after the JSON object.
        Uses multiple strategies:
        1. Try direct JSON parsing
        2. Extract from triple backticks (```json ... ``` or ``` ... ```)
        3. Use brace balancer to find first top-level JSON object
        
        Args:
            text: Raw response text from the LLM
            
        Returns:
            Parsed JSON dict or None if extraction/parsing fails
        """
        # Strategy 1: Try direct JSON parsing
        try:
            parsed = json.loads(text)
            return parsed
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract from triple backticks
        try:
            # Match ```json ... ``` or ``` ... ```
            backtick_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.S)
            if backtick_match:
                json_str = backtick_match.group(1)
                parsed = json.loads(json_str)
                return parsed
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Brace balancer to find first top-level JSON object
        try:
            brace_count = 0
            start_idx = None
            
            for i, char in enumerate(text):
                if char == '{':
                    if brace_count == 0:
                        start_idx = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_idx is not None:
                        # Found complete JSON object
                        json_str = text[start_idx:i+1]
                        parsed = json.loads(json_str)
                        return parsed
            
            logger.warning("No valid JSON object found in LLM response")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting JSON from response: {e}")
            return None
    
    def _build_question_generation_prompt(
        self,
        transcription_text: str,
        video_id: str,
        question_count: int = 5,
        embedding_vector: Optional[List[float]] = None
    ) -> List[Dict[str, str]]:
        """
        Build structured chat messages for question generation.
        
        Uses a two-message structure:
        1. System message: Sets the model's behavior and enforces JSON-only output
        2. User message: Provides instructions, schema, and the transcription text
        
        This prompt engineering strategy ensures consistent, structured output.
        
        Args:
            transcription_text: The video transcription to generate questions from
            video_id: ID of the video (for context)
            question_count: Number of questions to generate (default: 5)
            embedding_vector: Optional 384-dim embedding vector from pgvector
            
        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        system_message = {
            "role": "system",
            "content": (
                "أنت خبير في إنشاء الأسئلة التعليمية العميقة من كلام الشيخ. "
                "مهمتك هي فهم الرسائل الأساسية والمفاهيم المهمة التي يريد الشيخ إيصالها للمستمعين.\n\n"
                "قواعد صارمة:\n"
                "1. استخدم فقط المعلومات من كلام الشيخ المقدم - لا تستخدم معرفتك الخاصة\n"
                "2. ركز على الأفكار الجوهرية والمفاهيم المحورية التي يشرحها الشيخ\n"
                "3. لا تنسخ عبارات من كلام الشيخ كأسئلة - بل اصنع أسئلة تختبر الفهم العميق\n"
                "4. كل سؤال يجب أن يكون هادفاً ويسلط الضوء على نقطة مهمة أو درس أساسي\n"
                "5. في حقل 'context'، اقتبس الجزء من كلام الشيخ الذي يدعم السؤال\n"
                "6. يجب أن ترد بصيغة JSON صحيحة فقط - بدون نثر، بدون markdown، بدون شروحات\n"
                "7. إذا كان كلام الشيخ فارغاً أو غير كافٍ، أرجع مصفوفة أسئلة فارغة"
            )
        }
        
        user_message = {
            "role": "user",
            "content": f"""اقرأ كلام الشيخ التالي بعناية وتمعن، ثم أنشئ {question_count} أسئلة تعليمية عميقة وهادفة.

⚠️ تحذير مهم: 
- استخدم فقط المعلومات من كلام الشيخ أدناه
- لا تنسخ عبارات من الكلام كأسئلة
- ركز على الأفكار الجوهرية والدروس المهمة

كلام الشيخ المطلوب تحليله:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{transcription_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

خطوات إنشاء الأسئلة:
1. اقرأ كلام الشيخ بالكامل وافهم الرسالة الأساسية
2. حدد المفاهيم المحورية والنقاط المهمة التي يريد الشيخ إيصالها
3. لكل مفهوم مهم، اصنع سؤالاً يختبر فهم المستمع لهذا المفهوم
4. تأكد أن السؤال هادف وليس مجرد نسخ لعبارة من الكلام

أمثلة على الأسئلة الجيدة:
✓ "ما الحكمة التي ذكرها الشيخ من وراء...؟"
✓ "كيف وضح الشيخ العلاقة بين... و...؟"
✓ "ما المبدأ الأساسي الذي أكد عليه الشيخ في حديثه عن...؟"
✓ "لماذا شدد الشيخ على أهمية...؟"

أمثلة على الأسئلة السيئة (تجنبها):
✗ "ما هو المطلوب من الشخص عندما يرغب في...؟" (نسخ حرفي)
✗ "ماذا قال الشيخ؟" (سؤال عام جداً)
✗ "هل ذكر الشيخ...؟" (سؤال نعم/لا)

أنواع الأسئلة:
- factual: أسئلة عن حقائق ومعلومات محددة ذكرها الشيخ
- conceptual: أسئلة عن المفاهيم والأفكار التي شرحها الشيخ
- analytical: أسئلة تتطلب تحليل وفهم العلاقات بين الأفكار

مستويات الصعوبة:
- easy: أسئلة مباشرة عن نقاط واضحة ذكرها الشيخ
- medium: أسئلة تتطلب فهم العلاقات بين الأفكار
- hard: أسئلة تتطلب تحليل عميق وربط بين مفاهيم متعددة

صيغة JSON المطلوبة (بدون أي نص إضافي):
{{
  "questions": [
    {{
      "question_text": "سؤال هادف يختبر فهم مفهوم مهم من كلام الشيخ",
      "difficulty": "easy",
      "question_type": "factual",
      "context": "اقتباس من كلام الشيخ يدعم هذا السؤال"
    }}
  ]
}}

أنشئ الآن {question_count} أسئلة عميقة وهادفة بصيغة JSON فقط. تذكر: ركز على الأفكار الجوهرية من كلام الشيخ."""
        }
        
        return [system_message, user_message]
    
    def _parse_response(
        self,
        response_text: str,
        video_id: str,
        requested_count: int = 5
    ) -> List[GeneratedQuestion]:
        """
        Parse OpenRouter response and convert to GeneratedQuestion objects.
        
        Extracts JSON from the response, validates structure, and creates
        GeneratedQuestion objects for each question. Handles malformed questions
        gracefully by logging warnings and continuing with valid questions.
        Limits output to requested_count if more questions are returned.
        
        Args:
            response_text: Raw response text from OpenRouter
            video_id: ID of the video (for GeneratedQuestion objects)
            requested_count: Number of questions requested (for limiting output)
            
        Returns:
            List of GeneratedQuestion objects (empty list if parsing fails)
        """
        # Extract JSON from response
        parsed_json = self._extract_json_from_response(response_text)
        if not parsed_json:
            logger.error(
                "Failed to extract JSON from OpenRouter response",
                extra={"response_preview": response_text[:500] if response_text else ""}
            )
            return []
        
        # Log the parsed JSON structure for debugging
        logger.info(
            "Parsed JSON from OpenRouter",
            extra={"json_keys": list(parsed_json.keys()), "json_preview": str(parsed_json)[:300]}
        )
        
        # Handle different response formats
        questions_list = None
        
        # Format 1: Standard format with 'questions' or 'أسئلة' key
        if 'questions' in parsed_json:
            questions_list = parsed_json['questions']
        elif 'أسئلة' in parsed_json:
            questions_list = parsed_json['أسئلة']
        # Format 2: Single question object (wrap in array)
        elif 'question' in parsed_json or 'question_text' in parsed_json:
            logger.warning("Model returned single question object instead of array, wrapping in array")
            questions_list = [parsed_json]
        # Format 3: Direct array of questions (no wrapper key)
        elif isinstance(parsed_json, list):
            logger.warning("Model returned direct array instead of object with 'questions' key")
            questions_list = parsed_json
        else:
            logger.error(
                "Response JSON has unexpected format",
                extra={"available_keys": list(parsed_json.keys()), "json_structure": str(parsed_json)[:500]}
            )
            return []
        
        if questions_list is None:
            logger.error("Failed to extract questions list from response")
            return []
        
        # Validate that questions_list is a list
        if not isinstance(questions_list, list):
            logger.error(f"Questions data is not a list: {type(questions_list)}")
            return []
        
        # Validate that questions array contains objects
        if not all(isinstance(q, dict) for q in questions_list):
            logger.error("Questions array contains non-object elements")
            return []
        
        # Limit to requested count if more are returned
        if len(questions_list) > requested_count:
            logger.info(f"Limiting {len(questions_list)} questions to requested count of {requested_count}")
            questions_list = questions_list[:requested_count]
        
        # Parse each question
        question_responses = []
        seen_questions = set()  # For deduplication
        
        for idx, question_dict in enumerate(questions_list):
            try:
                # Try different possible keys for question text
                question_text = (
                    question_dict.get('question_text') or
                    question_dict.get('question') or
                    question_dict.get('سؤال') or
                    question_dict.get('نص_السؤال') or
                    ''
                ).strip()
                
                # Validate question text
                if not question_text:
                    logger.warning(f"Question {idx} has empty text, skipping")
                    continue
                
                # Check if question is just punctuation
                if all(c in '?.!,;:' for c in question_text):
                    logger.warning(f"Question {idx} is malformed (only punctuation), skipping")
                    continue
                
                # Deduplicate questions
                if question_text.lower() in seen_questions:
                    logger.warning(f"Question {idx} is duplicate, skipping")
                    continue
                
                seen_questions.add(question_text.lower())
                
                question_response = GeneratedQuestion(
                    video_id=video_id,
                    question_text=question_text,
                    context=question_dict.get('context'),
                    difficulty=question_dict.get('difficulty'),
                    question_type=question_dict.get('question_type')
                )
                question_responses.append(question_response)
            except (KeyError, TypeError) as e:
                logger.warning(f"Failed to parse question {idx}: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(question_responses)} questions from OpenRouter response")
        return question_responses
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((
            httpx.RequestError,
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.HTTPStatusError
        ))
    )
    def generate_questions(
        self,
        video_id: str,
        transcription_text: str,
        question_count: int = 5,
        embedding_vector: Optional[List[float]] = None
    ) -> List[GeneratedQuestion]:
        """
        Generate questions using OpenRouter.
        
        Implements the QuestionGenerationProvider interface for OpenRouter-based
        question generation. Builds the prompt, calls the OpenRouter API,
        and parses the response into GeneratedQuestion objects.
        
        Args:
            video_id: ID of the video
            transcription_text: The transcription text to generate questions from
            question_count: Number of questions to generate (default: 5)
            embedding_vector: Optional 384-dim embedding vector from pgvector
            
        Returns:
            List of GeneratedQuestion objects (empty list on error)
            
        Raises:
            OllamaConnectionException: If OpenRouter is unavailable or fails
        """
        # Validate API key
        if not self.api_key:
            logger.error("OpenRouter API key not configured")
            raise OllamaConnectionException(
                "OpenRouter API key is not configured. Please set OPENROUTER_API_KEY environment variable.",
                details={"provider": "openrouter"}
            )
        
        # Validate inputs
        if not transcription_text or not transcription_text.strip():
            logger.warning("Empty transcription text provided")
            return []
        
        if question_count <= 0:
            logger.warning(f"Invalid question_count: {question_count}, defaulting to 5")
            question_count = 5
        
        # Truncate very long transcriptions to avoid exceeding model context
        MAX_TRANSCRIPTION_CHARS = 12000
        if len(transcription_text) > MAX_TRANSCRIPTION_CHARS:
            logger.warning(
                f"Transcription text ({len(transcription_text)} chars) exceeds limit, "
                f"truncating to {MAX_TRANSCRIPTION_CHARS} chars"
            )
            transcription_text = transcription_text[:MAX_TRANSCRIPTION_CHARS] + "\n\n[Transcript truncated for brevity]"
        
        try:
            # Build prompt messages
            messages = self._build_question_generation_prompt(
                transcription_text=transcription_text,
                video_id=video_id,
                question_count=question_count,
                embedding_vector=embedding_vector
            )
            
            # Prepare request headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Add optional headers if configured
            if self.site_url:
                headers["HTTP-Referer"] = self.site_url
            if self.site_name:
                headers["X-Title"] = self.site_name
            
            # Prepare request body
            request_body = {
                "model": self.model,
                "messages": messages
            }
            
            # Call OpenRouter API
            logger.info(
                f"Calling OpenRouter to generate questions",
                extra={
                    "provider": "openrouter",
                    "model": self.model,
                    "video_id": video_id,
                    "question_count": question_count,
                    "prompt_length": len(transcription_text)
                }
            )
            
            start_time = time.time()
            
            response = self.client.post(
                self.OPENROUTER_API_URL,
                headers=headers,
                json=request_body
            )
            
            # Raise exception for HTTP errors
            response.raise_for_status()
            
            response_time = time.time() - start_time
            
            # Parse response JSON
            response_data = response.json()
            
            # Extract response text from OpenRouter format
            if 'choices' not in response_data or len(response_data['choices']) == 0:
                logger.error("OpenRouter response missing 'choices' field")
                return []
            
            response_text = response_data['choices'][0]['message']['content']
            
            # Log response metadata
            logger.debug(
                f"OpenRouter response received",
                extra={
                    "provider": "openrouter",
                    "response_time_seconds": round(response_time, 2),
                    "response_length": len(response_text),
                    "model": response_data.get('model', 'unknown')
                }
            )
            
            # Log raw response (truncated if very long)
            if len(response_text) > 500:
                logger.debug(f"OpenRouter response (truncated): {response_text[:500]}...")
            else:
                logger.debug(f"OpenRouter response: {response_text}")
            
            # Parse response
            questions = self._parse_response(response_text, video_id, requested_count=question_count)
            
            if not questions:
                logger.warning(f"OpenRouter generated no valid questions for video {video_id}")
                return []  # Graceful degradation
            
            logger.info(
                f"Successfully generated questions",
                extra={
                    "provider": "openrouter",
                    "video_id": video_id,
                    "question_count": len(questions),
                    "response_time_seconds": round(response_time, 2)
                }
            )
            
            return questions
            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = e.response.text
            
            logger.error(
                f"OpenRouter API error: {status_code}",
                extra={
                    "provider": "openrouter",
                    "status_code": status_code,
                    "error_detail": error_detail[:500]
                }
            )
            
            # Handle specific error codes
            if status_code == 401:
                raise OllamaConnectionException(
                    "OpenRouter authentication failed. Please check your API key.",
                    details={"status_code": status_code, "error": error_detail}
                )
            elif status_code == 429:
                raise OllamaConnectionException(
                    "OpenRouter rate limit exceeded. Please try again later.",
                    details={"status_code": status_code, "error": error_detail}
                )
            elif status_code >= 500:
                raise OllamaConnectionException(
                    "OpenRouter service error. Please try again later.",
                    details={"status_code": status_code, "error": error_detail}
                )
            else:
                raise OllamaConnectionException(
                    f"OpenRouter API error: {status_code}",
                    details={"status_code": status_code, "error": error_detail}
                )
                
        except (httpx.ConnectError, httpx.RequestError) as e:
            logger.error(
                "OpenRouter connection error",
                extra={"provider": "openrouter", "error": str(e)}
            )
            raise OllamaConnectionException(
                "Failed to connect to OpenRouter. Please check your internet connection.",
                details={"error": str(e)}
            )
        except httpx.ReadTimeout as e:
            logger.error(
                "OpenRouter request timed out",
                extra={"provider": "openrouter", "error": str(e)}
            )
            raise OllamaConnectionException(
                "OpenRouter request timed out. Please try again.",
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error(
                f"Unexpected error generating questions with OpenRouter: {e}",
                extra={"provider": "openrouter", "error_type": type(e).__name__},
                exc_info=True
            )
            # Graceful degradation for unexpected errors
            return []
    
    def check_health(self) -> bool:
        """
        Check if OpenRouter is healthy and accessible.
        
        Returns:
            True if OpenRouter is healthy and API key is valid, False otherwise.
        """
        if not self.api_key:
            logger.warning("OpenRouter API key not configured")
            return False
        
        try:
            # Make a minimal test request to verify API key and connectivity
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Use a simple test message
            test_body = {
                "model": self.model,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            response = self.client.post(
                self.OPENROUTER_API_URL,
                headers=headers,
                json=test_body,
                timeout=10.0
            )
            
            # Check if request was successful
            if response.status_code == 200:
                logger.info("OpenRouter health check passed", extra={"provider": "openrouter"})
                return True
            else:
                logger.warning(
                    f"OpenRouter health check failed with status {response.status_code}",
                    extra={"provider": "openrouter", "status_code": response.status_code}
                )
                return False
                
        except Exception as e:
            logger.error(
                f"OpenRouter health check failed: {e}",
                extra={"provider": "openrouter"}
            )
            return False
