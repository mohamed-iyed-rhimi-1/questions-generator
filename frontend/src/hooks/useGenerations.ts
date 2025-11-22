import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/axios'
import { GenerationListResponse } from '@/types'

/**
 * Query key for generations cache
 */
export const GENERATIONS_QUERY_KEY = ['generations']

/**
 * Options for useGenerations hook
 */
export interface UseGenerationsOptions {
  skip?: number
  limit?: number
}

/**
 * Return type for useGenerations hook
 */
export interface UseGenerationsReturn {
  generations: GenerationListResponse['generations']
  total: number
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: ReturnType<typeof useQuery>['refetch']
}

/**
 * Custom React Query hook for fetching generations list
 * Provides automatic caching, refetching, and error handling
 */
export function useGenerations(options?: UseGenerationsOptions): UseGenerationsReturn {
  const { skip = 0, limit = 100 } = options || {}

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: [GENERATIONS_QUERY_KEY[0], skip, limit],
    queryFn: async () => {
      const response = await api.get<GenerationListResponse>('/generations', {
        params: { skip, limit },
      })
      return response.data
    },
    staleTime: 1000 * 30, // 30 seconds - generations change less frequently
    refetchOnMount: false, // Rely on cache unless stale
  })

  return {
    generations: data?.generations ?? [],
    total: data?.total ?? 0,
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
  }
}
