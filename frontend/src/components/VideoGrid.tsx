import { Video as VideoIcon, Loader2 } from 'lucide-react'
import { VideoCard } from '@/components/VideoCard'
import { Video } from '@/types'

export interface VideoGridProps {
  videos: Video[]
  isLoading?: boolean
  emptyMessage?: string
}

export function VideoGrid({
  videos,
  isLoading = false,
  emptyMessage = 'No videos downloaded yet',
}: VideoGridProps) {
  // Loading state
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <div
            key={index}
            className="card animate-pulse"
          >
            <div className="aspect-video bg-gray-200 rounded-lg mb-4"></div>
            <div className="space-y-3">
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              <div className="flex gap-2">
                <div className="h-5 bg-gray-200 rounded w-16"></div>
                <div className="h-5 bg-gray-200 rounded w-20"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  // Empty state
  if (videos.length === 0) {
    return (
      <div className="text-center py-12">
        <VideoIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">
          {emptyMessage}
        </h3>
        <p className="text-gray-600">
          Download some YouTube videos to get started
        </p>
      </div>
    )
  }

  // Grid layout
  return (
    <section
      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
      aria-label="Video grid"
    >
      {videos.map((video) => (
        <VideoCard key={video.id} video={video} />
      ))}
    </section>
  )
}
