import { Video as VideoIcon } from 'lucide-react'
import { VideoCard } from '@/components/VideoCard'
import { EmptyState } from '@/components/EmptyState'
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
      <div className="grid responsive-grid-1-2-4 responsive-grid-gap">
        {Array.from({ length: 6 }).map((_, index) => (
          <div
            key={index}
            className="card animate-pulse responsive-card-padding"
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
    const scrollToTop = () => {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    return (
      <EmptyState
        icon={VideoIcon}
        title={emptyMessage}
        description="Start by entering YouTube video URLs in the download section above. You can download multiple videos at once."
        actionLabel="Scroll to Download"
        onAction={scrollToTop}
      />
    )
  }

  // Grid layout
  return (
    <section
      className="grid responsive-grid-1-2-4 responsive-grid-gap"
      aria-label="Video grid"
    >
      {videos.map((video) => (
        <VideoCard key={video.id} video={video} />
      ))}
    </section>
  )
}
