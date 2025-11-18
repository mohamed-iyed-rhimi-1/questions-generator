import { Video as VideoIcon, Calendar } from 'lucide-react'
import { Video } from '@/types'

export interface VideoCardProps {
  video: Video
  onSelect?: (videoId: string) => void
  isSelected?: boolean
}

export function VideoCard({ video, onSelect, isSelected }: VideoCardProps) {
  const handleClick = () => {
    if (onSelect) {
      onSelect(video.video_id)
    }
  }

  const formattedDate = new Date(video.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })

  return (
    <article
      className={`relative card card-hover cursor-pointer ${
        isSelected ? 'ring-2 ring-primary-500' : ''
      }`}
      onClick={handleClick}
    >
      {/* Thumbnail section */}
      <div className="relative aspect-video rounded-lg overflow-hidden bg-gray-200 mb-4">
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt={video.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <VideoIcon className="w-12 h-12 text-gray-400" />
          </div>
        )}
      </div>

      {/* Content section */}
      <div className="space-y-3">
        {/* Title */}
        <h3
          className="font-semibold text-gray-900 truncate-2"
          title={video.title}
        >
          {video.title}
        </h3>

        {/* Metadata row */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="badge badge-gray text-xs font-mono">
            {video.video_id}
          </span>
          <span className="badge badge-success">
            {video.download_status}
          </span>
        </div>

        {/* Date */}
        <p className="text-xs text-gray-500 flex items-center">
          <Calendar className="w-3 h-3 mr-1 inline" />
          Downloaded on {formattedDate}
        </p>
      </div>

      {/* Optional selection indicator */}
      {isSelected && (
        <div className="absolute top-2 right-2 w-6 h-6 bg-primary-600 rounded-full flex items-center justify-center">
          <svg
            className="w-4 h-4 text-white"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path d="M5 13l4 4L19 7"></path>
          </svg>
        </div>
      )}
    </article>
  )
}
