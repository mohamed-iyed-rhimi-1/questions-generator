import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/axios'
import { toast } from 'react-hot-toast'
import { DownloadVideosResponse } from '@/types'
import { VIDEOS_QUERY_KEY } from '@/hooks/useVideos'

/**
 * Return type for useDownloadVideos hook
 */
export interface UseDownloadVideosReturn {
  downloadVideos: (urls: string[]) => void
  isDownloading: boolean
  downloadResults: DownloadVideosResponse | undefined
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for downloading videos
 * Automatically invalidates video cache after successful download
 */
export function useDownloadVideos(): UseDownloadVideosReturn {
  const queryClient = useQueryClient()

  const { mutate, isPending, data, error, reset } = useMutation({
    mutationFn: async (urls: string[]) => {
      const response = await api.post<DownloadVideosResponse>('/videos/download', { urls })
      return response.data
    },
    onSuccess: (data: DownloadVideosResponse) => {
      // Invalidate videos query to refetch updated list
      queryClient.invalidateQueries({ queryKey: VIDEOS_QUERY_KEY })
      
      // Show success toast with summary statistics
      toast.success(
        `Downloaded ${data.successful} video(s). ${data.duplicates} duplicate(s), ${data.failed} failed.`
      )
    },
    onError: (error: any) => {
      // The axios interceptor already shows error toast, so just log
      console.error('Download error:', error)
    },
  })

  return {
    downloadVideos: mutate,
    isDownloading: isPending,
    downloadResults: data,
    error: error as Error | null,
    reset,
  }
}
