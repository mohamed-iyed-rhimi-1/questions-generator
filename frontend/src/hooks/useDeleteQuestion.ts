import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { api } from '@/lib/axios'
import { generationDetailQueryKey } from './useGeneration'

/**
 * Return type for useDeleteQuestion hook
 */
export interface UseDeleteQuestionReturn {
  deleteQuestion: (questionId: number) => void
  isDeleting: boolean
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for deleting a question
 * Invalidates generation detail cache on success and shows toast notifications
 * 
 * @param generationId - The generati
on ID that owns the question
 */
export function useDeleteQuestion(generationId: number): UseDeleteQuestionReturn {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async (questionId: number) => {
      await api.delete(`/generations/${generationId}/questions/${questionId}`)
    },
    onSuccess: () => {
      // Invalidate generation detail query to refetch updated data
      queryClient.invalidateQueries({ queryKey: generationDetailQueryKey(generationId) })
      
      // Show success notification
      toast.success('Question deleted successfully')
    },
    onError: (error: Error) => {
      console.error('Question deletion error:', error)
      // Show error notification
      const axiosError = error as { response?: { data?: { detail?: string } } }
      toast.error(axiosError.response?.data?.detail || 'Failed to delete question')
    },
  })

  return {
    deleteQuestion: mutation.mutate,
    isDeleting: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  }
}
