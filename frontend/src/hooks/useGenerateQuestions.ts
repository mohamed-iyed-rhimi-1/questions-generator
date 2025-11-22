/**
 * Custom React Query mutation hook for generating questions from transcribed videos.
 * Follows the useTranscribeVideos pattern.
 */

import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { api } from '@/lib/axios';
import { GenerateQuestionsResponse } from '@/types';

interface UseGenerateQuestionsReturn {
  generateQuestions: (videoIds: string[], questionCount?: number) => void;
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
  const navigate = useNavigate();

  const mutation = useMutation({
    mutationFn: async ({ video_ids, question_count }: { video_ids: string[]; question_count?: number }) => {
      const response = await api.post<GenerateQuestionsResponse>(
        '/questions/generate',
        { video_ids, question_count: question_count || 10 }
      );
      return response.data;
    },
    onSuccess: (data: GenerateQuestionsResponse) => {
      // Show success toast with summary statistics and navigation info
      toast.success(
        `Generated ${data.total_questions} question(s) from ${data.successful} video(s). ` +
        `Redirecting to generation details...`
      );
      
      // Navigate to generation detail page if generation_id is present
      if (data.generation_id) {
        navigate(`/generations/${data.generation_id}`);
      }
      
      // Note: No cache invalidation needed since questions are transient (not cached)
    },
    onError: (error: any) => {
      console.error('Question generation error:', error);
      // Axios interceptor already shows error toast
    },
  });

  return {
    generateQuestions: (videoIds: string[], questionCount?: number) => 
      mutation.mutate({ video_ids: videoIds, question_count: questionCount }),
    isGenerating: mutation.isPending,
    questionResults: mutation.data,
    error: mutation.error,
    reset: mutation.reset,
  };
};
