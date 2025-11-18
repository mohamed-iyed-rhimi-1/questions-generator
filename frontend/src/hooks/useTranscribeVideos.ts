import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/axios'
import { toast } from 'react-hot-toast'
import { TranscribeVideosResponse } from '@/types'
import { TRANSCRIPTIONS_QUERY_KEY } from '@/hooks/useTranscriptions'

/**
 * Return type for useTranscribeVideos hook
 */
export interface UseTranscribeVideosReturn {
  transcribeVideos: (videoIds: string[]) => void
  isTranscribing: boolean
  transcriptionResults: TranscribeVideosResponse | undefined
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for transcribing videos
 * Automatically invalidates transcription cache after successful transcription
 * Note: Backend automatically saves embeddings to pgvector during transcription
 */
export function useTranscribeVideos(): UseTranscribeVideosReturn {
  const queryClient = useQueryClient()

  const { mutate, isPending, data, error, reset } = useMutation({
    mutationFn: async (video_ids: string[]) => {
      const response = await api.post<TranscribeVideosResponse>('/transcriptions/transcribe', { video_ids })
      return response.data
    },
    onSuccess: (data: TranscribeVideosResponse) => {
      // Invalidate transcriptions query to refetch updated list
      queryClient.invalidateQueries({ queryKey: TRANSCRIPTIONS_QUERY_KEY })
      
      // Show success toast with summary statistics
      toast.success(
        `Transcribed ${data.successful} video(s). ${data.failed} failed, ${data.not_found || 0} not found, ${data.no_audio || 0} no audio.`
      )
    },
    onError: (error: any) => {
      // The axios interceptor already shows error toast, so just log
      console.error('Transcription error:', error)
    },
  })

  return {
    transcribeVideos: mutate,
    isTranscribing: isPending,
    transcriptionResults: data,
    error: error as Error | null,
    reset,
  }
}
