import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/axios'
import { Transcription, TranscriptionListResponse } from '@/types'

/**
 * Query key for transcriptions cache
 */
export const TRANSCRIPTIONS_QUERY_KEY = ['transcriptions']

/**
 * Options for useTranscriptions hook
 */
export interface UseTranscriptionsOptions {
  video_id?: string
  skip?: number
  limit?: number
}

/**
 * Return type for useTranscriptions hook
 */
export interface UseTranscriptionsReturn {
  transcriptions: Transcription[]
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: () => void
}

/**
 * Custom React Query hook for fetching transcriptions
 * Provides automatic caching, refetching, and error handling
 */
export function useTranscriptions(options?: UseTranscriptionsOptions): UseTranscriptionsReturn {
  const { video_id, skip = 0, limit = 500 } = options || {}

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [TRANSCRIPTIONS_QUERY_KEY[0], video_id, skip, limit],
    queryFn: async () => {
      const response = await api.get<TranscriptionListResponse>('/transcriptions', {
        params: { video_id, skip, limit },
      })
      return response.data.transcriptions
    },
    staleTime: 1000 * 60, // 1 minute
    refetchOnMount: false,
  })

  return {
    transcriptions: data ?? [],
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
  }
}
