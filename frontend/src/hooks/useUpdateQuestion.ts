import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { api } from '@/lib/axios'
import { QuestionResponse, UpdateQuestionRequest } from '@/types'
import { generationDetailQueryKey } from './useGeneration'

/**
 * Parameters for updating a question
 */
export interface UpdateQuestionParams {
  questionId: number
  updates: UpdateQuestionRequest
}

/**
 * Return type for useUpdateQuestion hook
 */
export interface UseUpdateQuestionReturn {
  updateQuestion: (params: UpdateQuestionParams) => void
  isUpdating: boolean
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for updating a question
 * Invalidates generation detail cache on success and shows toast notifications
 * 
 * @param generationId - The generation ID that owns the question
 */
export function useUpdateQuestion(generationId: number): UseUpdateQuestionReturn {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async ({ questionId, updates }: UpdateQuestionParams) => {
      const response = await api.put<QuestionResponse>(
        `/generations/${generationId}/questions/${questionId}`,
        updates
      )
      return response.data
    },
    onSuccess: () => {
      // Invalidate generation detail query to refetch updated data
      queryClient.invalidateQueries({ queryKey: generationDetailQueryKey(generationId) })
      
      // Show success notification
      toast.success('Question updated successfully')
    },
    onError: (error: Error) => {
      console.error('Question update error:', error)
      // Show error notification
      const axiosError = error as { response?: { data?: { detail?: string } } }
      toast.error(axiosError.response?.data?.detail || 'Failed to update question')
    },
  })

  return {
    updateQuestion: mutation.mutate,
    isUpdating: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  }
}
