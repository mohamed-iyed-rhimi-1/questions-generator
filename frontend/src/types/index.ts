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
 */
export interface Question {
  id: number;
  generation_id: number;
  video_id: string;
  question_text: string;
  answer?: string | null;
  context?: string;
  difficulty?: string;
  question_type?: string;
  order_index: number;
  created_at: string;
  updated_at: string;
}

/**
 * Request for updating a question
 * Matches backend UpdateQuestionRequest schema
 */
export interface UpdateQuestionRequest {
  question_text?: string;
  answer?: string | null;
  context?: string;
  difficulty?: string;
  question_type?: string;
  order_index?: number;
}

/**
 * Request for reordering questions
 * Matches backend UpdateQuestionsOrderRequest schema
 */
export interface UpdateQuestionsOrderRequest {
  question_ids: number[];
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
  generation_id?: number;
}

/**
 * Generation entity
 * Matches backend GenerationResponse schema
 */
export interface Generation {
  id: number;
  video_ids: string[];
  question_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * Generation detail with questions
 * Matches backend GenerationDetailResponse schema
 */
export interface GenerationDetailResponse extends Generation {
  questions: Question[];
}

/**
 * Response from GET /api/generations endpoint
 * Matches backend GenerationListResponse schema
 */
export interface GenerationListResponse {
  generations: Generation[];
  total: number;
}

/**
 * Response type alias for QuestionResponse
 * Matches backend QuestionResponse schema
 */
export type QuestionResponse = Question;

/**
 * Dependency error response
 * Returned when deletion fails due to dependent resources
 */
export interface DependencyError {
  error: 'dependency_violation';
  message: string;
  details: Record<string, any>;
  dependent_resources: Array<{
    type: string;
    id: number | string;
  }>;
}
