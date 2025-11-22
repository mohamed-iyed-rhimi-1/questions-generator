import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { api } from '@/lib/axios'
import { DependencyError, Transcription } from '@/types'
import { TRANSCRIPTIONS_QUERY_KEY } from './useTranscriptions'

/**
 * Return type for useDeleteTranscription hook
 */
export interface UseDeleteTranscriptionReturn {
  deleteTranscription: (transcriptionId: number) => void
  isDeleting: boolean
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for deleting a transcription
 * Uses optimistic updates to immediately remove transcription from UI
 * Rolls back on error and shows toast notifications
 * Handles dependency violations (409 Conflict) when transcription is used in generations
 */
export function useDeleteTranscription(): UseDeleteTranscriptionReturn {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async (transcriptionId: number) => {
      await api.delete(`/transcriptions/${transcriptionId}`)
    },
    // Optimistic update: remove transcription from cache before API call
    onMutate: async (transcriptionId: number) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: TRANSCRIPTIONS_QUERY_KEY })

      // Snapshot all previous transcription queries for rollback
      const previousData = new Map<string, Transcription[]>()
      
      // Get all transcription queries from cache
      queryClient.getQueriesData<Transcription[]>({ queryKey: TRANSCRIPTIONS_QUERY_KEY }).forEach(([queryKey, data]) => {
        if (data) {
          previousData.set(JSON.stringify(queryKey), data)
          
          // Optimistically update each query by removing the transcription
          queryClient.setQueryData<Transcription[]>(queryKey, (old) => {
            if (!old) return []
            return old.filter((transcription) => transcription.id !== transcriptionId)
          })
        }
      })

      // Return context with previous data for rollback
      return { previousData }
    },
    onSuccess: () => {
      // Show success notification
      toast.success('Transcription deleted successfully')
    },
    onError: (error: Error, _transcriptionId, context) => {
      console.error('Transcription deletion error:', error)
      
      // Rollback optimistic update on error
      if (context?.previousData) {
        context.previousData.forEach((data, queryKeyStr) => {
          const queryKey = JSON.parse(queryKeyStr)
          queryClient.setQueryData(queryKey, data)
        })
      }
      
      // Type guard for axios error
      const axiosError = error as { response?: { status?: number; data?: DependencyError | { detail?: string } } }
      
      // Handle dependency violation (409 Conflict)
      if (axiosError.response?.status === 409) {
        const data = axiosError.response.data as DependencyError
        toast.error(data.message || 'Cannot delete transcription due to dependencies')
      } else {
        // Generic error message
        const errorData = axiosError.response?.data as { detail?: string } | undefined
        const errorMessage = errorData?.detail || 'Failed to delete transcription'
        toast.error(errorMessage)
      }
    },
    // Always refetch after mutation settles to ensure cache is in sync
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: TRANSCRIPTIONS_QUERY_KEY })
    },
  })

  return {
    deleteTranscription: mutation.mutate,
    isDeleting: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  }
}
