"""
Ollama service for AI-powered question generation from transcriptions.

This module provides integration with Ollama LLM for generating educational questions
from video transcriptions. The Ollama client is initialized once at module load time
for efficiency and reused across all requests.
"""

import ollama
import json
import re
import uuid
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import requests.exceptions
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.models.transcription import Transcription
from app.schemas.question import QuestionResponse
from app.exceptions import OllamaConnectionException


# Configure logger
logger = logging.getLogger(__name__)

# Initialize Ollama client at module level (loaded once, reused across requests)
# This is more efficient than creating a new client for each request
ollama_client = None
try:
    ollama_client = ollama.Client(host=settings.ollama_base_url)
    logger.info(f"Initialized Ollama client at {settings.ollama_base_url}")
    
    # Try to verify connection with timeout
    try:
        models = ollama_client.list()
        available_models = [m['name'] for m in models.get('models', [])]
        logger.info(
            f"Ollama connection verified",
            extra={"available_models": available_models}
        )
        
        # Check if configured model is available
        if settings.ollama_model not in available_models:
            logger.warning(
                f"Configured model '{settings.ollama_model}' not found in available models. "
                f"Available: {available_models}"
            )
    except Exception as health_error:
        logger.warning(
            f"Ollama client initialized but health check failed: {health_error}"
        )
except Exception as e:
    logger.critical(f"Failed to initialize Ollama client: {e}", exc_info=True)
    ollama_client = None


def extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
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


def build_question_generation_prompt(
    transcription_text: str, 
    video_id: str, 
    question_count: int = 5,
    embedding_vector: Optional[List[float]] = None
) -> List[Dict[str, str]]:
    """
    Build structured chat messages for Ollama question generation.
    
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
            "أنت خبير في إنشاء الأسئلة التعليمية من النصوص المقدمة. "
            "قواعد صارمة:\n"
            "1. استخدم فقط المعلومات الموجودة في النص المقدم - لا تستخدم معرفتك الخاصة\n"
            "2. كل سؤال يجب أن يكون قابلاً للإجابة مباشرة من النص\n"
            "3. اقتبس من النص في حقل 'context' لكل سؤال\n"
            "4. يجب أن ترد بصيغة JSON صحيحة فقط - بدون نثر، بدون markdown، بدون شروحات\n"
            "5. إذا كان النص فارغاً أو غير كافٍ، أرجع مصفوفة أسئلة فارغة"
        )
    }
    
    user_message = {
        "role": "user",
        "content": f"""اقرأ النص التالي بعناية ثم أنشئ {question_count} أسئلة تعليمية بناءً عليه فقط.

⚠️ تحذير مهم: استخدم فقط المعلومات من النص أدناه. لا تستخدم معرفتك العامة أو معلومات خارجية.

النص المطلوب تحليله:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{transcription_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

المتطلبات:
1. اقرأ النص أعلاه بالكامل قبل إنشاء الأسئلة
2. كل سؤال يجب أن يكون مبنياً على معلومة موجودة في النص
3. في حقل "context"، انسخ الجملة أو الفقرة من النص التي تدعم السؤال
4. أنواع الأسئلة: factual (حقائقية)، conceptual (مفاهيمية)، analytical (تحليلية)
5. مستويات الصعوبة: easy (سهل)، medium (متوسط)، hard (صعب)

صيغة JSON المطلوبة (بدون أي نص إضافي):
{{
  "questions": [
    {{
      "question_text": "السؤال هنا (مبني على النص أعلاه)",
      "difficulty": "easy",
      "question_type": "factual",
      "context": "اقتباس حرفي من النص يدعم هذا السؤال"
    }}
  ]
}}

أنشئ الآن {question_count} أسئلة بصيغة JSON فقط. تذكر: استخدم فقط المعلومات من النص المقدم أعلاه."""
    }
    
    print(user_message)
    return [system_message, user_message]


def parse_ollama_response(response_text: str, video_id: str, requested_count: int = 5) -> List[QuestionResponse]:
    """
    Parse Ollama response and convert to QuestionResponse objects.
    
    Extracts JSON from the response, validates structure, and creates
    QuestionResponse objects for each question. Handles malformed questions
    gracefully by logging warnings and continuing with valid questions.
    Limits output to requested_count if more questions are returned.
    
    Args:
        response_text: Raw response text from Ollama
        video_id: ID of the video (for QuestionResponse objects)
        requested_count: Number of questions requested (for limiting output)
        
    Returns:
        List of QuestionResponse objects (empty list if parsing fails)
    """
    # Extract JSON from response
    parsed_json = extract_json_from_response(response_text)
    if not parsed_json:
        logger.error(
            "Failed to extract JSON from Ollama response",
            extra={"response_preview": response_text[:500] if response_text else ""}
        )
        return []
    
    # Log the parsed JSON structure for debugging
    logger.info(
        "Parsed JSON from Ollama",
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
    if not all(isinstance(q, dict) for q in questions_list):
        logger.error("Response 'questions' array contains non-object elements")
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
            
            question_response = QuestionResponse(
                id=str(uuid.uuid4()),
                video_id=video_id,
                question_text=question_text,
                context=question_dict.get('context'),
                difficulty=question_dict.get('difficulty'),
                question_type=question_dict.get('question_type'),
                created_at=datetime.utcnow()
            )
            question_responses.append(question_response)
        except (KeyError, TypeError) as e:
            logger.warning(f"Failed to parse question {idx}: {e}")
            continue
    
    logger.info(f"Successfully parsed {len(question_responses)} questions from Ollama response")
    return question_responses


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((
        ConnectionError,
        TimeoutError,
        requests.exceptions.RequestException,
        httpx.RequestError,
        httpx.ConnectError,
        httpx.ReadTimeout
    ))
)
def generate_questions_with_ollama(
    video_id: str, 
    transcription_text: str, 
    question_count: int = 5,
    embedding_vector: Optional[List[float]] = None
) -> List[QuestionResponse]:
    """
    Main function to generate questions using Ollama.
    
    This is the main entry point for Ollama question generation. It builds the prompt,
    calls the Ollama chat API, and parses the response into QuestionResponse objects.
    
    Implements graceful degradation: returns empty list on any error rather than
    raising exceptions. All errors are logged for debugging.
    
    Args:
        video_id: ID of the video
        transcription_text: The transcription text to generate questions from
        question_count: Number of questions to generate (default: 5)
        embedding_vector: Optional 384-dim embedding vector from pgvector
        
    Returns:
        List of QuestionResponse objects (empty list on error)
    """
    # Check if Ollama client is loaded
    if ollama_client is None:
        logger.error("Ollama client not initialized - cannot generate questions")
        raise OllamaConnectionException(
            "Ollama is not available. Please ensure Ollama is running and the model is loaded.",
            details={"ollama_base_url": settings.ollama_base_url}
        )
    
    # Validate inputs
    if not transcription_text or not transcription_text.strip():
        logger.warning("Empty transcription text provided")
        return []
    
    if question_count <= 0:
        logger.warning(f"Invalid question_count: {question_count}, defaulting to 5")
        question_count = 5
    
    # Truncate very long transcriptions to avoid exceeding model context
    # Typical LLM context: ~4000 tokens (~16000 chars), leave room for prompt/response
    MAX_TRANSCRIPTION_CHARS = 12000
    if len(transcription_text) > MAX_TRANSCRIPTION_CHARS:
        logger.warning(f"Transcription text ({len(transcription_text)} chars) exceeds limit, truncating to {MAX_TRANSCRIPTION_CHARS} chars")
        transcription_text = transcription_text[:MAX_TRANSCRIPTION_CHARS] + "\n\n[Transcript truncated for brevity]"
    
    try:
        # Build prompt messages
        messages = build_question_generation_prompt(
            transcription_text=transcription_text,
            video_id=video_id,
            question_count=question_count,
            embedding_vector=embedding_vector
        )
        
        # Call Ollama chat API with timeout
        logger.info(
            f"Calling Ollama to generate questions",
            extra={
                "model": settings.ollama_model,
                "video_id": video_id,
                "question_count": question_count,
                "prompt_length": len(transcription_text)
            }
        )
        
        import time
        start_time = time.time()
        
        # Note: Timeout should be configured at client level or transport level
        # The ollama library may not support timeout parameter directly in chat()
        response = ollama_client.chat(
            model=settings.ollama_model,
            messages=messages
        )
        
        response_time = time.time() - start_time
        
        # Extract response text
        response_text = response['message']['content']
        
        # Log response metadata
        logger.debug(
            f"Ollama response received",
            extra={
                "response_time_seconds": round(response_time, 2),
                "response_length": len(response_text)
            }
        )
        
        # Log raw response (truncated if very long)
        if len(response_text) > 500:
            logger.debug(f"Ollama response (truncated): {response_text[:500]}...")
        else:
            logger.debug(f"Ollama response: {response_text}")
        
        # Parse response
        questions = parse_ollama_response(response_text, video_id, requested_count=question_count)
        
        if not questions:
            logger.warning(f"Ollama generated no valid questions for video {video_id}")
            return []  # Graceful degradation
        
        logger.info(
            f"Successfully generated questions",
            extra={
                "video_id": video_id,
                "question_count": len(questions),
                "response_time_seconds": round(response_time, 2)
            }
        )
        
        return questions
        
    except (ConnectionError, httpx.ConnectError) as e:
        logger.error(
            "Ollama connection error",
            extra={"error": str(e), "ollama_url": settings.ollama_base_url}
        )
        raise OllamaConnectionException(
            "Ollama is not running. Please start Ollama with 'ollama serve'.",
            details={"error": str(e)}
        )
    except (TimeoutError, httpx.ReadTimeout) as e:
        logger.error(
            "Ollama request timed out",
            extra={"error": str(e), "model": settings.ollama_model}
        )
        raise OllamaConnectionException(
            "Ollama request timed out. The model may be too slow or overloaded.",
            details={"error": str(e)}
        )
    except (requests.exceptions.RequestException, httpx.RequestError) as e:
        logger.error(
            "Ollama request error",
            extra={"error": str(e), "model": settings.ollama_model}
        )
        raise OllamaConnectionException(
            "Failed to communicate with Ollama. Please check the service.",
            details={"error": str(e)}
        )
    except KeyError as e:
        logger.error(
            "Ollama returned invalid response format",
            extra={"error": str(e), "model": settings.ollama_model}
        )
        if 'model' in str(e).lower():
            raise OllamaConnectionException(
                f"Model '{settings.ollama_model}' not found. Please pull it with 'ollama pull {settings.ollama_model}'.",
                details={"error": str(e)}
            )
        raise OllamaConnectionException(
            "Ollama returned invalid response. Please check Ollama logs.",
            details={"error": str(e)}
        )
    except Exception as e:
        logger.error(
            f"Unexpected error generating questions with Ollama: {e}",
            extra={"error_type": type(e).__name__},
            exc_info=True
        )
        # Graceful degradation for unexpected errors
        return []


def retrieve_transcriptions_for_videos(
    video_ids: List[str], 
    session: Session
) -> Dict[str, Transcription]:
    """
    Batch retrieve transcriptions for multiple videos.
    
    This is more efficient than querying each video individually.
    Returns a lookup dict for O(1) access by video_id.
    
    Args:
        video_ids: List of video IDs to retrieve transcriptions for
        session: Database session
        
    Returns:
        Dict mapping video_id to Transcription object
    """
    transcriptions = session.query(Transcription).filter(
        Transcription.video_id.in_(video_ids)
    ).all()
    
    return {t.video_id: t for t in transcriptions}


def check_ollama_health() -> bool:
    """
    Check if Ollama is healthy and the configured model is available.
    
    Returns:
        True if Ollama is healthy and model is available, False otherwise.
    """
    if ollama_client is None:
        logger.warning("Ollama client not initialized")
        return False
    
    try:
        # Try to list models
        models = ollama_client.list()
        available_models = [m['name'] for m in models.get('models', [])]
        
        # Check if configured model is available
        if settings.ollama_model not in available_models:
            logger.warning(
                f"Configured model '{settings.ollama_model}' not available. "
                f"Available models: {available_models}"
            )
            return False
        
        logger.info("Ollama health check passed")
        return True
        
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        return False
