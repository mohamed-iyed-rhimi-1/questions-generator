/**
 * Custom React Query mutation hook for generating questions from transcribed videos.
 * Follows the useTranscribeVideos pattern.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { api } from '@/lib/axios';
import { GenerateQuestionsResponse } from '@/types';

interface UseGenerateQuestionsReturn {
  generateQuestions: (videoIds: string[]) => void;
  isGenerating: boolean;
  questionResults: GenerateQuestionsResponse | undefined;
  error: Error | null;
  reset: () => void;
}

/**
 * Hook for generating questions from transcribed videos
 * 
 * @returns Mutation functions and state for question generation
 */
export const useGenerateQuestions = (): UseGenerateQuestionsReturn => {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (video_ids: string[]) => {
      const response = await api.post<GenerateQuestionsResponse>(
        '/questions/generate',
        { video_ids }
      );
      return response.data;
    },
    onSuccess: (data: GenerateQuestionsResponse) => {
      // Show success toast with summary statistics
      toast.success(
        `Generated ${data.total_questions} question(s) from ${data.successful} video(s). ` +
        `${data.failed} failed, ${data.no_transcription} no transcription.`
      );
      
      // Note: No cache invalidation needed since questions are transient (not cached)
    },
    onError: (error: any) => {
      console.error('Question generation error:', error);
      // Axios interceptor already shows error toast
    },
  });

  return {
    generateQuestions: mutation.mutate,
    isGenerating: mutation.isPending,
    questionResults: mutation.data,
    error: mutation.error,
    reset: mutation.reset,
  };
};
