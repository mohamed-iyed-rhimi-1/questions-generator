import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { api } from '@/lib/axios'
import { DependencyError, Video } from '@/types'
import { VIDEOS_QUERY_KEY } from './useVideos'

/**
 * Return type for useDeleteVideo hook
 */
export interface UseDeleteVideoReturn {
  deleteVideo: (videoId: string) => void
  isDeleting: boolean
  error: Error | null
  reset: () => void
}

/**
 * Custom React Query mutation hook for deleting a video
 * Uses optimistic updates to immediately remove video from UI
 * Rolls back on error and shows toast notifications
 * Handles dependency violations (409 Conflict) when video has transcriptions
 */
export function useDeleteVideo(): UseDeleteVideoReturn {
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async (videoId: string) => {
      await api.delete(`/videos/${videoId}`)
    },
    // Optimistic update: remove video from cache before API call
    onMutate: async (videoId: string) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: VIDEOS_QUERY_KEY })

      // Snapshot the previous value for rollback
      const previousVideos = queryClient.getQueryData<Video[]>(VIDEOS_QUERY_KEY)

      // Optimistically update cache by removing the video
      queryClient.setQueryData<Video[]>(VIDEOS_QUERY_KEY, (old) => {
        if (!old) return []
        return old.filter((video) => video.video_id !== videoId)
      })

      // Return context with previous data for rollback
      return { previousVideos }
    },
    onSuccess: () => {
      // Show success notification
      toast.success('Video and associated files deleted successfully')
    },
    onError: (error: Error, _videoId, context) => {
      console.error('Video deletion error:', error)
      
      // Rollback optimistic update on error
      if (context?.previousVideos) {
        queryClient.setQueryData(VIDEOS_QUERY_KEY, context.previousVideos)
      }
      
      // Type guard for axios error
      const axiosError = error as { response?: { status?: number; data?: DependencyError | { detail?: string } } }
      
      // Handle dependency violation (409 Conflict)
      if (axiosError.response?.status === 409) {
        const data = axiosError.response.data as DependencyError
        toast.error(data.message || 'Cannot delete video due to dependencies')
      } else {
        // Generic error message
        const errorData = axiosError.response?.data as { detail?: string } | undefined
        const errorMessage = errorData?.detail || 'Failed to delete video'
        toast.error(errorMessage)
      }
    },
    // Always refetch after mutation settles to ensure cache is in sync
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: VIDEOS_QUERY_KEY })
    },
  })

  return {
    deleteVideo: mutation.mutate,
    isDeleting: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  }
}
