import { useState, useMemo, useEffect } from 'react'
import { FileText, Loader2, CheckCircle2, AlertCircle, Eye, X, Database, Clock } from 'lucide-react'
import { useTranscribeVideos } from '@/hooks/useTranscribeVideos'
import { useTranscriptions } from '@/hooks/useTranscriptions'
import { TranscriptionModal } from '@/components/TranscriptionModal'
import { Video, Transcription, TranscriptionResult } from '@/types'
import { toast } from 'react-hot-toast'

/**
 * Props for TranscriptionSection component
 */
interface TranscriptionSectionProps {
  videos: Video[]
}

/**
 * TranscriptionSection Component
 * Allows users to select videos and trigger batch transcription
 * Note: Backend automatically saves embeddings to pgvector during transcription
 */
export function TranscriptionSection({ videos }: TranscriptionSectionProps) {
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set())
  const [showResults, setShowResults] = useState(false)
  const [modalTranscription, setModalTranscription] = useState<Transcription | null>(null)
  const [modalVideoTitle, setModalVideoTitle] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [processingVideoIds, setProcessingVideoIds] = useState<Set<string>>(new Set())
  const [pendingVideoIds, setPendingVideoIds] = useState<Set<string>>(new Set())

  // Fetch existing transcriptions
  const { transcriptions, isLoading: isLoadingTranscriptions, refetch } = useTranscriptions()

  // Destructure transcription mutation hook
  const { transcribeVideos, isTranscribing, transcriptionResults, reset } = useTranscribeVideos()

  // Create lookup map for O(1) transcription lookup
  const videoIdToTranscription = useMemo(() => {
    const map = new Map<string, Transcription>()
    transcriptions.forEach((t) => {
      map.set(t.video_id, t)
    })
    return map
  }, [transcriptions])

  // Selection handlers
  const handleVideoSelect = (videoId: string) => {
    setSelectedVideoIds((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(videoId)) {
        newSet.delete(videoId)
      } else {
        newSet.add(videoId)
      }
      return newSet
    })
  }

  const handleSelectAll = () => {
    setSelectedVideoIds(new Set(videos.map((v) => v.video_id)))
  }

  const handleDeselectAll = () => {
    setSelectedVideoIds(new Set())
  }

  // Form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (selectedVideoIds.size === 0) {
      toast.error('Please select at least one video to transcribe')
      return
    }

    const videoIds = Array.from(selectedVideoIds)
    // Mark selected videos as pending
    setPendingVideoIds(new Set(videoIds))
    transcribeVideos(videoIds)
    setShowResults(true)
  }

  // Poll for transcription status updates while processing
  useEffect(() => {
    if (isTranscribing) {
      // Mark pending videos as processing
      setProcessingVideoIds(new Set(pendingVideoIds))
      setPendingVideoIds(new Set())
    } else if (processingVideoIds.size > 0) {
      // When transcription completes, refetch to get updated statuses
      refetch()
      // Clear processing state after a delay to allow cache to update
      const timer = setTimeout(() => {
        setProcessingVideoIds(new Set())
      }, 1000)
      return () => clearTimeout(timer)
    }
  }, [isTranscribing, pendingVideoIds, processingVideoIds, refetch])

  // View transcription handler
  const handleViewTranscription = (videoId: string, providedTranscription?: Transcription) => {
    const transcription = providedTranscription || videoIdToTranscription.get(videoId)
    const video = videos.find((v) => v.video_id === videoId)

    if (transcription) {
      setModalTranscription(transcription)
      setModalVideoTitle(video?.title || videoId)
      setIsModalOpen(true)
    }
  }

  // Clear/reset handler
  const handleClear = () => {
    setSelectedVideoIds(new Set())
    setPendingVideoIds(new Set())
    setProcessingVideoIds(new Set())
    reset()
    setShowResults(false)
  }

  // Helper function to get per-video status
  const getVideoStatus = (videoId: string): 'pending' | 'processing' | 'completed' | null => {
    if (pendingVideoIds.has(videoId)) return 'pending'
    if (processingVideoIds.has(videoId)) return 'processing'
    if (videoIdToTranscription.has(videoId)) return 'completed'
    return null
  }

  // Helper functions
  const getStatusBadgeClass = (status: TranscriptionResult['status']) => {
    switch (status) {
      case 'success':
        return 'badge badge-success'
      case 'not_found':
        return 'badge badge-warning'
      case 'no_audio':
        return 'badge badge-warning'
      case 'failed':
        return 'badge badge-danger'
      default:
        return 'badge badge-gray'
    }
  }

  const getStatusIcon = (status: TranscriptionResult['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-3 h-3 mr-1" />
      case 'not_found':
        return <AlertCircle className="w-3 h-3 mr-1" />
      case 'no_audio':
        return <AlertCircle className="w-3 h-3 mr-1" />
      case 'failed':
        return <AlertCircle className="w-3 h-3 mr-1" />
      default:
        return null
    }
  }

  return (
    <div className="card">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Transcribe Videos</h2>
        <p className="text-gray-600 mb-1">
          Select videos to transcribe audio and generate embeddings for semantic search
        </p>
        <p className="text-sm text-gray-500">
          Note: Embeddings are automatically saved to vector database
        </p>
      </div>

      {/* Video selection area */}
      <div className="mb-6">
        {/* Selection controls */}
        <div className="flex items-center gap-3 mb-4">
          <span className="badge badge-primary">
            {selectedVideoIds.size} selected
          </span>
          <button
            onClick={handleSelectAll}
            disabled={isTranscribing || videos.length === 0}
            className="btn btn-sm btn-outline"
          >
            Select All
          </button>
          <button
            onClick={handleDeselectAll}
            disabled={isTranscribing || selectedVideoIds.size === 0}
            className="btn btn-sm btn-outline"
          >
            Deselect All
          </button>
        </div>

        {/* Video list */}
        {videos.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No videos available. Download videos first.
          </div>
        ) : (
          <div className="max-h-[400px] overflow-y-auto scrollbar-thin">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {videos.map((video) => {
                const isSelected = selectedVideoIds.has(video.video_id)

                return (
                  <div
                    key={video.video_id}
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      isSelected
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                    onClick={() => handleVideoSelect(video.video_id)}
                  >
                    <div className="flex items-start gap-3">
                      {/* Checkbox */}
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleVideoSelect(video.video_id)}
                        onClick={(e) => e.stopPropagation()}
                        className="mt-1 w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                        disabled={isTranscribing}
                      />

                      {/* Video info */}
                      <div className="flex-1 min-w-0">
                        {/* Thumbnail */}
                        {video.thumbnail_url && (
                          <img
                            src={video.thumbnail_url}
                            alt={video.title}
                            className="w-full h-20 object-cover rounded mb-2"
                          />
                        )}

                        {/* Title */}
                        <p className="text-sm font-medium text-gray-900 truncate mb-1">
                          {video.title}
                        </p>

                        {/* Video ID badge */}
                        <p className="text-xs text-gray-500 font-mono truncate mb-2">
                          {video.video_id}
                        </p>

                        {/* Transcription status */}
                        <div className="flex items-center gap-2">
                          {(() => {
                            const status = getVideoStatus(video.video_id)
                            if (status === 'pending') {
                              return (
                                <span className="badge badge-warning text-xs flex items-center">
                                  <Clock className="w-3 h-3 mr-1" />
                                  Pending
                                </span>
                              )
                            }
                            if (status === 'processing') {
                              return (
                                <span className="badge badge-primary text-xs flex items-center">
                                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  Processing
                                </span>
                              )
                            }
                            if (status === 'completed') {
                              return (
                                <>
                                  <span className="badge badge-success text-xs">
                                    Completed
                                  </span>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      handleViewTranscription(video.video_id)
                                    }}
                                    className="text-xs text-primary-600 hover:text-primary-700 flex items-center"
                                  >
                                    <Eye className="w-3 h-3 mr-1" />
                                    View
                                  </button>
                                </>
                              )
                            }
                            return (
                              <span className="badge badge-gray text-xs">
                                Not transcribed
                              </span>
                            )
                          })()}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <form onSubmit={handleSubmit} className="flex gap-3 mb-6">
        <button
          type="submit"
          disabled={isTranscribing || selectedVideoIds.size === 0}
          className="btn btn-primary flex items-center"
        >
          {isTranscribing ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Transcribing...
            </>
          ) : (
            <>
              <FileText className="w-4 h-4 mr-2" />
              Transcribe Selected
            </>
          )}
        </button>

        <button
          type="button"
          disabled={true}
          className="btn btn-outline flex items-center opacity-60 cursor-not-allowed"
          title="Embeddings are automatically saved to vector database during transcription"
        >
          <Database className="w-4 h-4 mr-2" />
          Save to Vector DB
        </button>

        <button
          type="button"
          onClick={handleClear}
          disabled={isTranscribing}
          className="btn btn-outline flex items-center"
        >
          <X className="w-4 h-4 mr-2" />
          Clear Selection
        </button>
      </form>

      {/* Results panel */}
      {showResults && transcriptionResults && (
        <div className="pt-6 border-t border-gray-200">
          {/* Summary stats */}
          <div className="mb-4 flex flex-wrap gap-2">
            <span className="badge badge-gray">
              Total: {transcriptionResults.total}
            </span>
            <span className="badge badge-success">
              Successful: {transcriptionResults.successful}
            </span>
            <span className="badge badge-danger">
              Failed: {transcriptionResults.failed}
            </span>
            {transcriptionResults.not_found !== undefined && transcriptionResults.not_found > 0 && (
              <span className="badge badge-warning">
                Not Found: {transcriptionResults.not_found}
              </span>
            )}
            {transcriptionResults.no_audio !== undefined && transcriptionResults.no_audio > 0 && (
              <span className="badge badge-warning">
                No Audio: {transcriptionResults.no_audio}
              </span>
            )}
          </div>

          {/* Per-video results list */}
          {transcriptionResults.results.length > 0 && (
            <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
              {transcriptionResults.results.map((result, index) => (
                <div
                  key={index}
                  className="p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-mono text-gray-600 truncate">
                        {result.video_id}
                      </p>
                      <p className="text-sm text-gray-700 mt-1">{result.message}</p>
                      {result.error && (
                        <p className="text-sm text-red-600 mt-1">{result.error}</p>
                      )}
                      {result.steps_completed !== undefined && result.total_steps !== undefined && (
                        <p className="text-xs text-gray-500 mt-1">
                          Steps: {result.steps_completed}/{result.total_steps}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <span className={`${getStatusBadgeClass(result.status)} flex items-center whitespace-nowrap`}>
                        {getStatusIcon(result.status)}
                        {result.status}
                      </span>
                      {result.status === 'success' && result.transcription && (
                        <button
                          onClick={() => handleViewTranscription(result.video_id, result.transcription)}
                          className="text-xs text-primary-600 hover:text-primary-700 flex items-center"
                        >
                          <Eye className="w-3 h-3 mr-1" />
                          View
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TranscriptionModal */}
      <TranscriptionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        transcription={modalTranscription}
        videoTitle={modalVideoTitle}
      />
    </div>
  )
}
