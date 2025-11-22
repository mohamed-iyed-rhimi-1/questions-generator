import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/axios'
import { GenerationDetailResponse } from '@/types'

/**
 * Query key factory for generation detail cache
 */
export const generationDetailQueryKey = (id: string | number | undefined) => ['generations', id]

/**
 * Return type for useGeneration hook
 */
export interface UseGenerationReturn {
  generation: GenerationDetailResponse | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null
  refetch: ReturnType<typeof useQuery>['refetch']
}

/**
 * Custom React Query hook for fetching a single generation with questions
 * Provides automatic caching, refetching, and error handling
 * 
 * @param id - Generation ID (query is disabled if undefined)
 */
export function useGeneration(id: string | number | undefined): UseGenerationReturn {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: generationDetailQueryKey(id),
    queryFn: async () => {
      const response = await api.get<GenerationDetailResponse>(`/generations/${id}`)
      return response.data
    },
    enabled: !!id, // Only run query when id is provided
    staleTime: 1000 * 30, // 30 seconds
    refetchOnMount: false,
  })

  return {
    generation: data,
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
  }
}
