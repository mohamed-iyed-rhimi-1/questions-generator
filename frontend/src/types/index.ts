/**
 * Shared TypeScript interfaces and types for the application
 * Aligned with backend schemas from backend/app/schemas/video.py
 */

/**
 * Download status enum
 * Note: Backend only returns 'completed' by default.
 * 'pending' and 'downloading' are UI-only states for optimistic updates.
 */
export type DownloadStatus = 
  | 'pending'
  | 'downloading'
  | 'completed'
  | 'failed';

/**
 * Video entity
 * Matches backend VideoResponse schema
 */
export interface Video {
  id: number;
  video_id: string;
  title: string;
  thumbnail_url?: string;
  download_status: DownloadStatus;
  file_path?: string;
  created_at: string;
}

/**
 * Download result for a single URL
 * Matches backend DownloadResult schema
 */
export interface DownloadResult {
  url: string;
  status: 'success' | 'duplicate' | 'failed';
  message: string;
  video_id?: string;
  video?: Video;
  error?: string;
}

/**
 * Response from batch download operation
 * Matches backend DownloadVideosResponse schema
 */
export interface DownloadVideosResponse {
  results: DownloadResult[];
  total: number;
  successful: number;
  duplicates: number;
  failed: number;
}

/**
 * Transcription entity
 * Aligned with backend TranscriptionResponse schema from backend/app/schemas/transcription.py
 * Note: Embeddings are automatically saved to pgvector during transcription process
 */
export interface Transcription {
  id: number; // Backend returns integer
  video_id: string;
  transcription_text: string; // Renamed from 'text' to match backend field name
  vector_embedding?: number[]; // Optional array of floats, 384 dimensions (all-MiniLM-L6-v2)
  status: string; // Backend returns string, default "completed"
  created_at: string; // Backend returns datetime as ISO string in JSON
}

/**
 * Result for a single video transcription operation
 * Matches backend TranscriptionResult schema
 */
export interface TranscriptionResult {
  video_id: string;
  status: 'success' | 'not_found' | 'no_audio' | 'failed';
  message: string;
  transcription?: Transcription;
  error?: string;
  steps_completed?: number;
  total_steps?: number;
}

/**
 * Response from batch transcription operation
 * Matches backend TranscribeVideosResponse schema
 */
export interface TranscribeVideosResponse {
  results: TranscriptionResult[];
  total: number;
  successful: number;
  failed: number;
  not_found?: number;
  no_audio?: number;
}

/**
 * Response from GET /api/transcriptions endpoint
 * Matches backend TranscriptionListResponse schema
 */
export interface TranscriptionListResponse {
  transcriptions: Transcription[];
  total: number;
}

/**
 * Question entity
 * Matches backend QuestionResponse schema
 * Note: Questions are currently placeholder/mock data.
 * Ollama integration will replace placeholder generation in next phase.
 * Questions are transient (not persisted to database yet).
 */
export interface Question {
  id: string;
  video_id: string;
  question_text: string;
  context?: string;
  difficulty?: string;
  question_type?: string;
  created_at: string;
}

/**
 * Result for a single video question generation operation
 * Matches backend QuestionGenerationResult schema
 */
export interface QuestionGenerationResult {
  video_id: string;
  status: 'success' | 'no_transcription' | 'failed';
  message: string;
  questions?: Question[];
  error?: string;
  question_count: number;
}

/**
 * Response from batch question generation operation
 * Matches backend GenerateQuestionsResponse schema
 */
export interface GenerateQuestionsResponse {
  results: QuestionGenerationResult[];
  total: number;
  successful: number;
  failed: number;
  no_transcription: number;
  total_questions: number;
}
