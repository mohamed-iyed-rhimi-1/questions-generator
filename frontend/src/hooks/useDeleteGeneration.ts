import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/axios'
import { GenerationListResponse } from '@/types'
import { GENERATIONS_QUERY_KEY } from './useGenerations'

/**
 * Return type for useDeleteGeneration hook
 */
export interface UseDeleteGenerationReturn {
  deleteGeneration: (generationId: number) => void
  isDeleting: boolean
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for deleting a generation
 * Uses optimistic updates to immediately remove generation from UI
 * Rolls back on error, shows toast notifications,
 * and navigates to generations list page on success
 */
export function useDeleteGeneration(): UseDeleteGenerationReturn {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const mutation = useMutation({
    mutationFn: async (generationId: number) => {
      await api.delete(`/generations/${generationId}`)
    },
    // Optimistic update: remove generation from cache before API call
    onMutate: async (generationId: number) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: GENERATIONS_QUERY_KEY })

      // Snapshot all previous generation queries for rollback
      const previousData = new Map<string, GenerationListResponse>()
      
      // Get all generation queries from cache
      queryClient.getQueriesData<GenerationListResponse>({ queryKey: GENERATIONS_QUERY_KEY }).forEach(([queryKey, data]) => {
        if (data) {
          previousData.set(JSON.stringify(queryKey), data)
          
          // Optimistically update each query by removing the generation
          queryClient.setQueryData<GenerationListResponse>(queryKey, (old) => {
            if (!old || !old.generations) return old || { generations: [], total: 0 }
            return {
              generations: old.generations.filter((generation) => generation.id !== generationId),
              total: Math.max(0, old.total - 1),
            }
          })
        }
      })

      // Return context with previous data for rollback
      return { previousData }
    },
    onSuccess: () => {
      // Show success notification
      toast.success('Generation deleted successfully')
      
      // Navigate to generations list page
      navigate('/generations')
    },
    onError: (error: Error, _generationId, context) => {
      console.error('Generation deletion error:', error)
      
      // Rollback optimistic update on error
      if (context?.previousData) {
        context.previousData.forEach((data, queryKeyStr) => {
          const queryKey = JSON.parse(queryKeyStr)
          queryClient.setQueryData(queryKey, data)
        })
      }
      
      // Type guard for axios error
      const axiosError = error as { response?: { data?: { detail?: string } } }
      
      // Generic error message
      const errorMessage = axiosError.response?.data?.detail || 'Failed to delete generation'
      toast.error(errorMessage)
    },
    // Always refetch after mutation settles to ensure cache is in sync
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: GENERATIONS_QUERY_KEY })
    },
  })

  return {
    deleteGeneration: mutation.mutate,
    isDeleting: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  }
}
