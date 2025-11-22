import { useState } from 'react'
import { Video as VideoIcon, Calendar, Trash2, Loader2 } from 'lucide-react'
import { Video } from '@/types'
import { ConfirmDialog } from './ConfirmDialog'
import { useDeleteVideo } from '@/hooks/useDeleteVideo'

export interface VideoCardProps {
  video: Video
  onSelect?: (videoId: string) => void
  isSelected?: boolean
}

export function VideoCard({ video, onSelect, isSelected }: VideoCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const { deleteVideo, isDeleting } = useDeleteVideo()

  const handleClick = () => {
    if (onSelect && !isDeleting) {
      onSelect(video.video_id)
    }
  }

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowDeleteDialog(true)
  }

  const handleConfirmDelete = () => {
    deleteVideo(video.video_id)
    setShowDeleteDialog(false)
  }

  const formattedDate = new Date(video.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })

  return (
    <>
      <article
        className={`relative card responsive-card-padding transition-all duration-200 ${
          isDeleting 
            ? 'opacity-50 cursor-not-allowed' 
            : 'card-hover cursor-pointer hover:-translate-y-1'
        } ${isSelected ? 'ring-2 ring-primary-500 shadow-lg' : ''}`}
        onClick={handleClick}
        role="button"
        tabIndex={isDeleting ? -1 : 0}
        aria-label={`Video: ${video.title}. Status: ${video.download_status}. ${isSelected ? 'Selected' : 'Not selected'}`}
        aria-pressed={isSelected}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !isDeleting) {
            e.preventDefault()
            handleClick()
          }
        }}
      >
        {/* Semi-transparent overlay during deletion */}
        {isDeleting && (
          <div className="absolute inset-0 bg-white/60 backdrop-blur-sm rounded-xl z-10 flex items-center justify-center">
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-8 h-8 text-primary-600 animate-spin" />
              <span className="text-sm font-medium text-gray-700">Deleting...</span>
            </div>
          </div>
        )}

        {/* Thumbnail section */}
        <div className="relative aspect-video rounded-lg overflow-hidden bg-gradient-to-br from-gray-100 to-gray-200 mb-4 shadow-inner" role="img" aria-label={`Thumbnail for ${video.title}`}>
          {video.thumbnail_url ? (
            <img
              src={video.thumbnail_url}
              alt={`Thumbnail for ${video.title}`}
              className="w-full h-full object-cover transition-transform duration-300 hover:scale-105"
              onError={(e) => {
                e.currentTarget.style.display = 'none'
                e.currentTarget.nextElementSibling?.classList.remove('hidden')
              }}
            />
          ) : null}
          <div className={`w-full h-full flex items-center justify-center ${video.thumbnail_url ? 'hidden' : ''}`}>
            <VideoIcon className="w-12 h-12 text-gray-400" aria-hidden="true" />
          </div>
        </div>

        {/* Content section */}
        <div className="space-y-3">
          {/* Title */}
          <h3
            className="font-semibold text-gray-900 truncate-2 leading-snug"
            title={video.title}
          >
            {video.title}
          </h3>

          {/* Metadata row */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="badge badge-gray text-xs font-mono">
              {video.video_id}
            </span>
            <span className={`badge ${
              video.download_status === 'completed' ? 'badge-success' :
              video.download_status === 'failed' ? 'badge-danger' :
              'badge-warning'
            }`}>
              {video.download_status}
            </span>
          </div>

          {/* Date */}
          <p className="text-xs text-gray-500 flex items-center">
            <Calendar className="w-3 h-3 mr-1 inline" />
            Downloaded on {formattedDate}
          </p>
        </div>

        {/* Action buttons */}
        <div className="absolute top-2 right-2 sm:top-3 sm:right-3 flex gap-2">
          <button
            onClick={handleDeleteClick}
            disabled={isDeleting}
            className="touch-target p-2 sm:p-2 bg-white/90 backdrop-blur-sm hover:bg-red-50 text-gray-600 hover:text-red-600 rounded-lg shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-110 active:scale-95 focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
            title="Delete video"
            aria-label={`Delete video ${video.title}`}
            aria-busy={isDeleting}
            type="button"
          >
            {isDeleting ? (
              <Loader2 className="w-5 h-5 sm:w-4 sm:h-4 animate-spin" aria-hidden="true" />
            ) : (
              <Trash2 className="w-5 h-5 sm:w-4 sm:h-4" aria-hidden="true" />
            )}
            <span className="sr-only">{isDeleting ? 'Deleting video' : 'Delete video'}</span>
          </button>
        </div>

        {/* Optional selection indicator */}
        {isSelected && (
          <div className="absolute top-2 left-2 sm:top-3 sm:left-3 w-7 h-7 sm:w-6 sm:h-6 bg-primary-600 rounded-full flex items-center justify-center shadow-lg" aria-hidden="true">
            <svg
              className="w-5 h-5 sm:w-4 sm:h-4 text-white"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
              role="img"
              aria-label="Selected"
            >
              <path d="M5 13l4 4L19 7"></path>
            </svg>
          </div>
        )}
      </article>

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showDeleteDialog}
        title="Delete Video"
        message={`Are you sure you want to delete "${video.title}"? This will permanently remove the video and its audio file from storage.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleConfirmDelete}
        onCancel={() => setShowDeleteDialog(false)}
        isLoading={isDeleting}
      />
    </>
  )
}
