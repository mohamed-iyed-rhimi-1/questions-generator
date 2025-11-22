import { Calendar, FileText, Video, Eye, Edit, RefreshCw, Trash2, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useGenerations } from '@/hooks/useGenerations'
import { useDeleteGeneration } from '@/hooks/useDeleteGeneration'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState } from '@/components/EmptyState'
import { Generation } from '@/types'

export function Generations() {
  const navigate = useNavigate()
  const { generations, total, isLoading, isError, error, refetch } = useGenerations()

  const handleView = (generationId: number) => {
    navigate(`/generations/${generationId}`)
  }

  const handleEdit = (generationId: number) => {
    navigate(`/generations/${generationId}?edit=true`)
  }

  // Loading state
  if (isLoading) {
    return (
      <div>
        <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8 mb-8">
          <div className="max-w-7xl mx-auto">
            <h1 className="text-3xl sm:text-4xl font-bold mb-2">
              Question Generations
            </h1>
            <p className="text-lg text-primary-100">
              View and manage your generated question sets
            </p>
          </div>
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-center py-12">
            <div className="spinner w-12 h-12" role="status" aria-label="Loading generations"></div>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (isError) {
    return (
      <div>
        <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8 mb-8">
          <div className="max-w-7xl mx-auto">
            <h1 className="text-3xl sm:text-4xl font-bold mb-2">
              Question Generations
            </h1>
            <p className="text-lg text-primary-100">
              View and manage your generated question sets
            </p>
          </div>
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="card bg-red-50 border-red-200" role="alert">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <svg
                  className="h-6 w-6 text-red-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div className="ml-3 flex-1">
                <h3 className="text-sm font-medium text-red-800">
                  Error loading generations
                </h3>
                <p className="mt-2 text-sm text-red-700">
                  {error?.message || 'An unexpected error occurred'}
                </p>
                <button
                  onClick={() => refetch()}
                  className="mt-4 btn btn-sm btn-outline hover:bg-red-50"
                  type="button"
                >
                  Try Again
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Empty state
  if (generations.length === 0) {
    return (
      <div>
        <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8 mb-8">
          <div className="max-w-7xl mx-auto">
            <h1 className="text-3xl sm:text-4xl font-bold mb-2">
              Question Generations
            </h1>
            <p className="text-lg text-primary-100">
              View and manage your generated question sets
            </p>
          </div>
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="card">
            <EmptyState
              icon={Sparkles}
              title="No question generations yet"
              description="Start by downloading videos, transcribing them, and then generating educational questions. Your question sets will appear here."
              actionLabel="Go to Dashboard"
              onAction={() => navigate('/')}
            />
          </div>
        </div>
      </div>
    )
  }

  // Main content with generations
  return (
    <div>
      <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8 mb-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl sm:text-4xl font-bold mb-2">
            Question Generations
          </h1>
          <p className="text-lg text-primary-100">
            View and manage your generated question sets
          </p>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div className="flex items-center flex-wrap gap-2">
            <h2 className="text-2xl font-bold text-gray-900">
              All Generations
            </h2>
            <span className="badge badge-primary">
              {total} generation{total !== 1 ? 's' : ''}
            </span>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="btn btn-sm btn-outline flex items-center justify-center"
            type="button"
            aria-label="Refresh generations list"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Refresh
          </button>
        </div>

        {/* Generations grid */}
        <div className="grid responsive-grid-1-2-3 responsive-grid-gap">
          {generations.map((generation) => (
            <GenerationCard
              key={generation.id}
              generation={generation}
              onView={handleView}
              onEdit={handleEdit}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

interface GenerationCardProps {
  generation: Generation
  onView: (id: number) => void
  onEdit: (id: number) => void
}

function GenerationCard({ generation, onView, onEdit }: GenerationCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const { deleteGeneration, isDeleting } = useDeleteGeneration()

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffInMs = now.getTime() - date.getTime()
    const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24))

    // Show relative time for recent generations
    if (diffInDays === 0) {
      const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60))
      if (diffInHours === 0) {
        const diffInMinutes = Math.floor(diffInMs / (1000 * 60))
        return diffInMinutes <= 1 ? 'Just now' : `${diffInMinutes} minutes ago`
      }
      return diffInHours === 1 ? '1 hour ago' : `${diffInHours} hours ago`
    } else if (diffInDays === 1) {
      return 'Yesterday'
    } else if (diffInDays < 7) {
      return `${diffInDays} days ago`
    }

    // Show full date for older generations
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const handleDeleteClick = () => {
    setShowDeleteDialog(true)
  }

  const handleConfirmDelete = () => {
    deleteGeneration(generation.id)
    setShowDeleteDialog(false)
  }

  const handleCancelDelete = () => {
    setShowDeleteDialog(false)
  }

  return (
    <>
      <article className={`card responsive-card-padding transition-all duration-300 relative overflow-hidden ${
        isDeleting ? 'pointer-events-none' : 'hover:shadow-lg hover:-translate-y-1'
      }`}>
        {/* Loading overlay */}
        {isDeleting && (
          <div className="absolute inset-0 bg-white bg-opacity-75 rounded-lg flex items-center justify-center z-10">
            <div className="spinner w-8 h-8" role="status" aria-label="Deleting generation"></div>
          </div>
        )}

        {/* Header with date and delete button */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center text-sm text-gray-600 font-medium">
            <Calendar className="w-4 h-4 mr-2 flex-shrink-0 text-gray-400" aria-hidden="true" />
            <time dateTime={generation.created_at} className="tracking-tight">
              {formatDate(generation.created_at)}
            </time>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-primary flex-shrink-0 font-semibold">
              #{generation.id}
            </span>
            <button
              onClick={handleDeleteClick}
              disabled={isDeleting}
              className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-110"
              type="button"
              aria-label={`Delete generation ${generation.id}`}
              title="Delete generation"
            >
              {isDeleting ? (
                <div className="spinner w-4 h-4" role="status" aria-label="Deleting"></div>
              ) : (
                <Trash2 className="w-4 h-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

      {/* Stats with enhanced styling */}
      <div className="space-y-4 mb-6 bg-gradient-to-br from-gray-50 to-white p-4 rounded-lg border border-gray-100">
        <div className="flex items-center justify-between group">
          <div className="flex items-center text-gray-700">
            <div className="p-2 bg-primary-100 rounded-lg mr-3 group-hover:bg-primary-200 transition-colors">
              <FileText className="w-5 h-5 text-primary-600 flex-shrink-0" aria-hidden="true" />
            </div>
            <span className="font-semibold text-base">Questions</span>
          </div>
          <span className="text-3xl font-bold text-gray-900 tracking-tight" aria-label={`${generation.question_count} questions`}>
            {generation.question_count}
          </span>
        </div>

        <div className="h-px bg-gray-200"></div>

        <div className="flex items-center justify-between group">
          <div className="flex items-center text-gray-700">
            <div className="p-2 bg-secondary-100 rounded-lg mr-3 group-hover:bg-secondary-200 transition-colors">
              <Video className="w-5 h-5 text-secondary-600 flex-shrink-0" aria-hidden="true" />
            </div>
            <span className="font-semibold text-base">Videos</span>
          </div>
          <span className="text-3xl font-bold text-gray-900 tracking-tight" aria-label={`${generation.video_ids.length} videos`}>
            {generation.video_ids.length}
          </span>
        </div>
      </div>

      {/* Video IDs preview with enhanced styling */}
      <div className="mb-6">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Source Videos</p>
        <div className="flex flex-wrap gap-2">
          {generation.video_ids.slice(0, 3).map((videoId) => (
            <span
              key={videoId}
              className="badge badge-gray text-xs font-mono px-2.5 py-1 hover:bg-gray-200 transition-colors cursor-default"
              title={videoId}
            >
              {videoId.substring(0, 8)}...
            </span>
          ))}
          {generation.video_ids.length > 3 && (
            <span className="badge badge-primary text-xs font-semibold px-2.5 py-1">
              +{generation.video_ids.length - 3} more
            </span>
          )}
        </div>
      </div>

      {/* Action buttons with enhanced styling */}
      <div className="mobile-button-group pt-2">
        <button
          onClick={() => onView(generation.id)}
          disabled={isDeleting}
          className="btn btn-primary btn-touch flex-1 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-sm hover:shadow-md transition-all"
          type="button"
          aria-label={`View generation ${generation.id}`}
        >
          <Eye className="w-4 h-4 mr-2" aria-hidden="true" />
          View
        </button>
        <button
          onClick={() => onEdit(generation.id)}
          disabled={isDeleting}
          className="btn btn-outline btn-touch flex-1 flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed font-semibold hover:bg-gray-50 transition-all"
          type="button"
          aria-label={`Edit generation ${generation.id}`}
        >
          <Edit className="w-4 h-4 mr-2" aria-hidden="true" />
          Edit
        </button>
      </div>
    </article>

    {/* Confirmation Dialog */}
    <ConfirmDialog
      isOpen={showDeleteDialog}
      title="Delete Generation"
      message={`Are you sure you want to delete generation #${generation.id}? This will permanently delete all ${generation.question_count} questions in this generation.`}
      confirmLabel="Delete"
      cancelLabel="Cancel"
      variant="danger"
      onConfirm={handleConfirmDelete}
      onCancel={handleCancelDelete}
      isLoading={isDeleting}
    />
  </>
  )
}
