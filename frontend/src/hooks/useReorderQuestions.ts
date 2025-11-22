import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { api } from '@/lib/axios'
import { GenerationDetailResponse, UpdateQuestionsOrderRequest } from '@/types'
import { generationDetailQueryKey } from './useGeneration'

/**
 * Return type for useReorderQuestions hook
 */
export interface UseReorderQuestionsReturn {
  reorderQuestions: (questionIds: number[]) => void
  isReordering: boolean
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for reordering questions
 * Invalidates generation detail cache on success and shows toast notifications
 * 
 * @param generationId - The generation ID that owns the questions
 */
export function useReorderQuestions(generationId: number): UseReorderQuestionsReturn {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async (questionIds: number[]) => {
      const requestBody: UpdateQuestionsOrderRequest = { question_ids: questionIds }
      const response = await api.put<GenerationDetailResponse>(
        `/generations/${generationId}/questions/reorder`,
        requestBody
      )
      return response.data
    },
    onSuccess: () => {
      // Invalidate generation detail query to refetch updated data
      queryClient.invalidateQueries({ queryKey: generationDetailQueryKey(generationId) })
      
      // Show success notification
      toast.success('Questions reordered successfully')
    },
    onError: (error: Error) => {
      console.error('Question reordering error:', error)
      // Show error notification
      const axiosError = error as { response?: { data?: { detail?: string } } }
      toast.error(axiosError.response?.data?.detail || 'Failed to reorder questions')
    },
  })

  return {
    reorderQuestions: mutation.mutate,
    isReordering: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  }
}
