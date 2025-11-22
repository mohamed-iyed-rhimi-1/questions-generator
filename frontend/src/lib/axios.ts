import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import toast from 'react-hot-toast';

// Retry configuration
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second base delay
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];
const RETRYABLE_ERROR_CODES = ['ECONNABORTED', 'ENOTFOUND', 'ENETUNREACH', 'ETIMEDOUT'];

// Extend AxiosRequestConfig to include retry count
declare module 'axios' {
  export interface InternalAxiosRequestConfig {
    __retryCount?: number;
  }
}

/**
 * Check if an error should be retried
 */
function isRetryableError(error: AxiosError): boolean {
  // Network errors (no response)
  if (!error.response) {
    return true;
  }

  // Check status code
  if (error.response.status && RETRYABLE_STATUS_CODES.includes(error.response.status)) {
    return true;
  }

  // Check error code
  if (error.code && RETRYABLE_ERROR_CODES.includes(error.code)) {
    return true;
  }

  return false;
}

/**
 * Calculate retry delay with exponential backoff and jitter
 */
function getRetryDelay(retryCount: number): number {
  const delay = RETRY_DELAY * Math.pow(2, retryCount);
  const maxDelay = 30000; // 30 seconds max
  const jitter = delay * (0.5 + Math.random() * 0.5);
  return Math.min(jitter, maxDelay);
}

/**
 * Map error codes to user-friendly messages
 */
function getErrorMessage(error: AxiosError): string {
  // Check for structured error response
  const errorData = error.response?.data as any;
  const errorCode = errorData?.error_code;

  // Map specific error codes
  const errorMessages: Record<string, string> = {
    'OLLAMA_CONNECTION_FAILED': 'AI service is unavailable. Please try again later.',
    'VIDEO_DOWNLOAD_FAILED': 'Failed to download video. Please check the URL and try again.',
    'TRANSCRIPTION_FAILED': 'Failed to transcribe video. The audio may be corrupted.',
    'EMBEDDING_FAILED': 'Failed to generate embeddings. Please try again.',
    'DATABASE_ERROR': 'Database error. Please try again later.',
    'DATABASE_CONNECTION_ERROR': 'Database is temporarily unavailable. Please try again later.',
    'VALIDATION_ERROR': errorData?.message || 'Invalid input. Please check your data.',
  };

  if (errorCode && errorMessages[errorCode]) {
    return errorMessages[errorCode];
  }

  // Fallback to generic messages
  return (
    errorData?.message ||
    (errorData?.detail as string) ||
    error.message ||
    'An unexpected error occurred'
  );
}

/**
 * Configured Axios instance for API calls
 * Uses relative path '/api' which will be proxied by Vite to the backend
 */
export const api = axios.create({
  baseURL: '/api',  // Changed: Use relative path that Vite will proxy
  timeout: 120000, // 2 minutes for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor for auth token injection
 * TODO: Implement token injection when authentication is added
 */
api.interceptors.request.use(
  (config) => {
    // Placeholder for future auth token injection
    // const token = localStorage.getItem('auth_token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor for error handling via toast system and retry logic
 */
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig;

    // Initialize retry count
    if (!config) {
      return Promise.reject(error);
    }

    config.__retryCount = config.__retryCount || 0;

    // Check if we should retry
    if (isRetryableError(error) && config.__retryCount < MAX_RETRIES) {
      config.__retryCount++;
      const delay = getRetryDelay(config.__retryCount);

      console.log(
        `Retrying request (${config.__retryCount}/${MAX_RETRIES}) after ${delay}ms`,
        config.url
      );

      // Wait for delay
      await new Promise(resolve => setTimeout(resolve, delay));

      // Retry request
      return api.request(config);
    }

    // Max retries exceeded or non-retryable error
    // Check if toast should be suppressed (via custom config flag)
    const suppressToast = (config as any)?.suppressErrorToast;

    if (!suppressToast) {
      // Extract and map error message
      const message = getErrorMessage(error);

      // Surface error via toast
      toast.error(message);
    }

    return Promise.reject(error);
  }
);