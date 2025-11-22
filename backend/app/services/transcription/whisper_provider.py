"""Whisper transcription provider implementation."""

import whisper
import numpy as np
import torch
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.config import settings
from app.exceptions import TranscriptionException
from .base import TranscriptionProvider


logger = logging.getLogger(__name__)


class WhisperTranscriptionProvider(TranscriptionProvider):
    """Local Whisper transcription provider."""
    
    def __init__(self):
        """Initialize Whisper provider with conditional model loading."""
        self.whisper_model = None
        self.whisper_device = None
        self.use_fp16 = False
        
        # Only load model if this provider is selected
        if settings.transcription_provider == 'whisper':
            self._load_model()
    
    def _load_model(self):
        """Load Whisper model with GPU detection and fallback strategies."""
        try:
            # Check for GPU availability (CUDA for NVIDIA, MPS for Apple Silicon)
            # Note: Whisper has issues with MPS sparse tensors, so we force CPU on Apple Silicon
            if torch.cuda.is_available():
                self.whisper_device = 'cuda'
                self.use_fp16 = True
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f"NVIDIA GPU detected: {gpu_name} ({gpu_memory:.1f} GB)")
            elif torch.backends.mps.is_available():
                self.whisper_device = 'cpu'  # Force CPU for Whisper on Apple Silicon
                self.use_fp16 = False
                logger.info("Apple Silicon GPU (MPS) detected - using CPU for Whisper due to PyTorch MPS limitations")
            else:
                self.whisper_device = 'cpu'
                self.use_fp16 = False
                logger.warning("No GPU detected, falling back to CPU (this will be slow)")
            
            logger.info(f"Loading Whisper model on device: {self.whisper_device}")
            
            import time
            start_time = time.time()
            self.whisper_model = whisper.load_model(settings.whisper_model, device=self.whisper_device)
            load_time = time.time() - start_time
            
            logger.info(
                f"Loaded Whisper model: {settings.whisper_model}",
                extra={"device": self.whisper_device, "load_time_seconds": round(load_time, 2)}
            )
        except Exception as e:
            logger.critical(
                f"Failed to load Whisper model '{settings.whisper_model}': {e}",
                exc_info=True
            )
            self.whisper_model = None
    
    def _clear_gpu_cache(self):
        """Clear GPU cache for both CUDA and MPS devices."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif torch.backends.mps.is_available():
            torch.mps.empty_cache()
    
    def validate_audio_file(self, audio_path: str) -> bool:
        """
        Validate that audio file contains valid audio data that Whisper can process.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            True if audio is valid, False otherwise
        """
        try:
            # Use Whisper's own audio loading to match its expectations
            audio = whisper.load_audio(audio_path)
            
            # Check if we got any audio samples
            if len(audio) == 0:
                logger.error(f"Audio file contains no audio data: {audio_path}")
                return False
            
            # Check minimum duration (Whisper needs at least 0.1 seconds of audio)
            # Audio is sampled at 16kHz, so 0.1 seconds = 1600 samples
            min_samples = 1600
            if len(audio) < min_samples:
                logger.error(
                    f"Audio file too short: {audio_path} "
                    f"(has {len(audio)} samples, needs at least {min_samples})"
                )
                return False
                
            # Check if audio is not just silence (all zeros or near-zeros)
            if np.abs(audio).max() < 1e-6:
                logger.error(f"Audio file appears to contain only silence: {audio_path}")
                return False
            
            # Try to compute the mel spectrogram (this is what Whisper does internally)
            try:
                # Pad audio to 30 seconds like Whisper does
                audio = whisper.pad_or_trim(audio)
                mel = whisper.log_mel_spectrogram(audio)
                
                # Check mel dimensions - should be [80, frames] where frames > 0
                if mel.shape[0] == 0 or mel.shape[1] == 0:
                    logger.error(
                        f"Audio file produces empty mel spectrogram: {audio_path} "
                        f"(shape: {mel.shape})"
                    )
                    return False
                    
                # Mel should have at least a few frames
                if mel.shape[1] < 10:
                    logger.error(
                        f"Audio file produces too few mel frames: {audio_path} "
                        f"(frames: {mel.shape[1]})"
                    )
                    return False
                    
            except Exception as mel_error:
                logger.error(f"Failed to compute mel spectrogram for {audio_path}: {mel_error}")
                return False
                
            logger.debug(
                f"Audio validation passed: {audio_path} "
                f"(samples: {len(audio)}, duration: {len(audio)/16000:.2f}s, mel_shape: {mel.shape})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Audio validation failed for {audio_path}: {e}")
            return False

    def _preprocess_audio(self, audio_path: str) -> Optional[str]:
        """
        Preprocess audio file by re-encoding it to ensure compatibility with Whisper.
        This fixes issues with corrupted files, unusual encodings, or problematic formats.
        
        Args:
            audio_path: Path to the original audio file
            
        Returns:
            Path to preprocessed audio file, or None if preprocessing failed
        """
        try:
            # Create temporary file for preprocessed audio
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.wav',
                delete=False,
                dir=Path(audio_path).parent
            )
            temp_path = temp_file.name
            temp_file.close()
            
            logger.info(f"Preprocessing audio file: {audio_path}")
            
            # Re-encode audio with ffmpeg to ensure compatibility
            # - Convert to 16kHz mono (Whisper's expected format)
            # - Use WAV format (lossless, most reliable for Whisper)
            # - Fix any corruption or format issues
            cmd = [
                'ffmpeg',
                '-i', audio_path,
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',  # Mono
                '-c:a', 'pcm_s16le',  # WAV codec (16-bit PCM)
                '-y',  # Overwrite output file
                temp_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg preprocessing failed: {result.stderr}")
                Path(temp_path).unlink(missing_ok=True)
                return None
            
            # Verify the preprocessed file exists and has content
            if not Path(temp_path).exists() or Path(temp_path).stat().st_size < 1024:
                logger.error(f"Preprocessed file is invalid or too small")
                Path(temp_path).unlink(missing_ok=True)
                return None
            
            logger.info(f"Audio preprocessing successful: {temp_path}")
            return temp_path
            
        except subprocess.TimeoutExpired:
            logger.error(f"Audio preprocessing timed out for: {audio_path}")
            Path(temp_path).unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            if 'temp_path' in locals():
                Path(temp_path).unlink(missing_ok=True)
            return None

    def transcribe_audio(self, audio_path: str, language: str = "ar") -> Optional[str]:
        """
        Transcribe audio file using Whisper with fallback strategies for robustness.
        
        Args:
            audio_path: Path to the audio file (MP3)
            language: Language code (default: "ar" for Arabic)
            
        Returns:
            Transcription text or None if failed
        """
        if self.whisper_model is None:
            logger.error("Whisper model not loaded")
            raise TranscriptionException("Whisper model not loaded. Please restart the application.")
        
        # Verify audio file exists
        audio_file = Path(audio_path)
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return None
        
        # Validate file size
        file_size = audio_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size < 1024:  # Less than 1KB
            logger.error(f"Audio file too small ({file_size} bytes): {audio_path}")
            return None
        elif file_size_mb > 500:  # Larger than 500MB
            logger.warning(f"Audio file very large ({file_size_mb:.2f}MB): {audio_path}")
        
        # Validate audio content before attempting transcription
        if not self.validate_audio_file(audio_path):
            logger.error(f"Audio file validation failed, skipping transcription: {audio_path}")
            return None
        
        # Determine device and precision
        if torch.cuda.is_available():
            device = 'cuda'
            use_fp16 = True  # NVIDIA GPUs support FP16
        elif torch.backends.mps.is_available():
            device = 'mps'
            use_fp16 = False  # MPS doesn't support FP16 in Whisper yet
        else:
            device = 'cpu'
            use_fp16 = False

        # Strategy 1: Try with optimized settings (beam_size=5)
        try:
            logger.info(
                f"Starting Whisper transcription for {audio_file.name} ({file_size_mb:.2f}MB)",
                extra={"language": language, "strategy": "optimized", "provider": "whisper"}
            )
            
            if use_fp16:
                logger.info(f"Using GPU with FP16 precision for faster transcription")
            
            result = self.whisper_model.transcribe(
                audio_path,
                language=language,
                task="transcribe",
                fp16=use_fp16,
                verbose=False,
                beam_size=5,
                best_of=5,
                temperature=0.0,
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=True,
                word_timestamps=False,
            )
            text = result['text'].strip()
            
            # Get detected language info
            detected_language = result.get('language', 'unknown')
            language_probability = result.get('language_probability', 0.0)
            
            # Log language detection results
            logger.info(
                f"Language detection results",
                extra={
                    "requested_language": language,
                    "detected_language": detected_language,
                    "language_probability": round(language_probability, 3)
                }
            )
            
            # Validate text is not empty and has minimum length
            if not text:
                logger.warning(f"Transcription resulted in empty text for: {audio_path}")
                return None
            elif len(text) < 10:
                logger.warning(
                    f"Transcription seems too short ({len(text)} chars): {audio_path}"
                )

            # Check if text contains Arabic characters
            arabic_char_count = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
            total_chars = len(text)
            arabic_percentage = (arabic_char_count / total_chars * 100) if total_chars > 0 else 0
            
            logger.info(
                f"Successfully transcribed {audio_file.name}",
                extra={
                    "text_length": len(text),
                    "file_size_mb": round(file_size_mb, 2),
                    "device": device,
                    "language": language,
                    "arabic_percentage": round(arabic_percentage, 1),
                    "strategy": "optimized",
                    "provider": "whisper"
                }
            )
            
            # Preview first 100 characters (for debugging)
            logger.debug(f"Transcription preview: {text[:100]}...")
            
            return text
            
        except RuntimeError as e:
            error_msg = str(e)
            
            # Handle OOM for both CUDA and MPS (MPS raises RuntimeError for OOM)
            if "out of memory" in error_msg.lower():
                logger.error(f"GPU out of memory for {audio_path}: {e}")
                self._clear_gpu_cache()
                return None
            
            # Handle tensor errors (empty segments, size mismatches, corrupted audio) - fallback to simpler settings
            if any(keyword in error_msg for keyword in [
                "cannot reshape tensor", 
                "0 elements", 
                "is ambiguous",
                "Sizes of tensors must match",
                "Expected size"
            ]):
                logger.warning(
                    f"Whisper encountered tensor error, trying fallback strategy: {e}",
                    extra={"error_type": "TensorError", "strategy": "fallback"}
                )
                
                # Clear GPU cache
                self._clear_gpu_cache()

                # Strategy 2: Fallback with simpler settings (beam_size=1, no best_of)
                try:
                    logger.info(f"Retrying with simplified settings (beam_size=1)")
                    
                    result = self.whisper_model.transcribe(
                        audio_path,
                        language=language,
                        task="transcribe",
                        fp16=use_fp16,
                        verbose=False,
                        beam_size=1,  # Simpler decoding
                        temperature=0.0,
                        compression_ratio_threshold=2.4,
                        logprob_threshold=-1.0,
                        no_speech_threshold=0.6,
                        condition_on_previous_text=False,  # Disable context to avoid state issues
                        word_timestamps=False,
                    )
                    
                    text = result['text'].strip()
                    
                    if not text:
                        logger.error(f"Fallback strategy produced empty text for: {audio_path}")
                        return None
                    
                    logger.info(
                        f"Successfully transcribed with fallback strategy",
                        extra={
                            "text_length": len(text),
                            "strategy": "fallback",
                            "provider": "whisper"
                        }
                    )
                    
                    return text
                    
                except Exception as fallback_error:
                    logger.error(
                        f"Fallback strategy also failed for {audio_path}: {fallback_error}",
                        extra={"error_type": type(fallback_error).__name__},
                        exc_info=True
                    )
                    
                    self._clear_gpu_cache()
                    
                    # Strategy 3: Try preprocessing the audio file and retry
                    logger.warning("Attempting audio preprocessing as final fallback")
                    preprocessed_path = self._preprocess_audio(audio_path)
                    
                    if preprocessed_path:
                        try:
                            logger.info(f"Retrying transcription with preprocessed audio")
                            
                            result = self.whisper_model.transcribe(
                                preprocessed_path,
                                language=language,
                                task="transcribe",
                                fp16=use_fp16,
                                verbose=False,
                                beam_size=1,
                                temperature=0.0,
                                compression_ratio_threshold=2.4,
                                logprob_threshold=-1.0,
                                no_speech_threshold=0.6,
                                condition_on_previous_text=False,
                                word_timestamps=False,
                            )
                            
                            text = result['text'].strip()
                            
                            # Clean up preprocessed file
                            Path(preprocessed_path).unlink(missing_ok=True)
                            
                            if not text:
                                logger.error(f"Preprocessing strategy produced empty text for: {audio_path}")
                                return None
                            
                            logger.info(
                                f"Successfully transcribed with preprocessing strategy",
                                extra={
                                    "text_length": len(text),
                                    "strategy": "preprocessing",
                                    "provider": "whisper"
                                }
                            )
                            
                            return text
                            
                        except Exception as preprocess_error:
                            logger.error(
                                f"Preprocessing strategy also failed for {audio_path}: {preprocess_error}",
                                extra={"error_type": type(preprocess_error).__name__}
                            )
                            # Clean up preprocessed file
                            if preprocessed_path:
                                Path(preprocessed_path).unlink(missing_ok=True)
                            return None
                    
                    return None
            
            # Other runtime errors
            logger.error(
                f"Whisper runtime error for {audio_path}: {e}",
                extra={"error_type": "RuntimeError"},
                exc_info=True
            )
            
            self._clear_gpu_cache()
            
            return None

        except Exception as e:
            logger.error(
                f"Whisper transcription error for {audio_path}: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True
            )
            
            self._clear_gpu_cache()
            
            return None
