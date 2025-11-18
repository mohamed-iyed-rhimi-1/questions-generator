import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/axios'
import { Video } from '@/types'

/**
 * Query key for videos cache
 */
export const VIDEOS_QUERY_KEY = ['videos']

/**
 * Options for useVideos hook
 */
export interface UseVideosOptions {
  skip?: number
  limit?: number
}

/**
 * Return type for useVideos hook
 */
export interface UseVideosReturn {
  videos: Video[]
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: ReturnType<typeof useQuery>['refetch']
}

/**
 * Custom React Query hook for fetching videos
 * Provides automatic caching, refetching, and error handling
 */
export function useVideos(options?: UseVideosOptions): UseVideosReturn {
  const { skip = 0, limit = 100 } = options || {}

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [VIDEOS_QUERY_KEY[0], skip, limit],
    queryFn: async () => {
      const response = await api.get<Video[]>('/videos', {
        params: { skip, limit },
      })
      return response.data
    },
    staleTime: 1000 * 60, // 1 minute - videos don't change frequently
    refetchOnMount: false, // Rely on cache unless stale
  })

  return {
    videos: data ?? [],
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
  }
}
