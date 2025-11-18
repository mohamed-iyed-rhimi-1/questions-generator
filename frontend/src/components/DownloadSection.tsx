import { useState } from 'react'
import { toast } from 'react-hot-toast'
import { Download, Loader2, X, CheckCircle2, AlertCircle, Clock } from 'lucide-react'
import { useDownloadVideos } from '@/hooks/useDownloadVideos'
import { DownloadResult } from '@/types'

/**
 * DownloadSection Component
 * 
 * Note: Progress updates are shown as a single request-level loading state.
 * The backend processes downloads synchronously without streaming progress.
 * Per-URL results are displayed after the entire batch completes.
 * 
 * For true real-time per-URL incremental progress, the backend would need:
 * - SSE (Server-Sent Events) or WebSocket endpoint for streaming progress
 * - Periodic polling endpoint to check in-progress download statuses
 * - Database tracking of individual URL download states
 */
export function DownloadSection() {
  const [urlInput, setUrlInput] = useState('')
  const [showResults, setShowResults] = useState(false)
  const { downloadVideos, isDownloading, downloadResults, reset } = useDownloadVideos()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Parse URLs from textarea
    const urls = urlInput
      .split('\n')
      .map((url) => url.trim())
      .filter((url) => url.length > 0)

    // Validate at least one URL exists
    if (urls.length === 0) {
      toast.error('Please enter at least one YouTube URL')
      return
    }

    // Call download mutation
    downloadVideos(urls)
    setShowResults(true)
  }

  const handleClear = () => {
    setUrlInput('')
    reset()
    setShowResults(false)
  }

  const getStatusBadgeClass = (status: DownloadResult['status']) => {
    switch (status) {
      case 'success':
        return 'badge badge-success'
      case 'duplicate':
        return 'badge badge-warning'
      case 'failed':
        return 'badge badge-danger'
      default:
        return 'badge badge-gray'
    }
  }

  const getStatusIcon = (status: DownloadResult['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-3 h-3 mr-1" />
      case 'duplicate':
        return <Clock className="w-3 h-3 mr-1" />
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
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Download Videos</h2>
        <p className="text-gray-600">
          Enter YouTube URLs (one per line) to download and process videos
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Textarea */}
        <div>
          <label htmlFor="url-input" className="label">
            YouTube URLs
          </label>
          <textarea
            id="url-input"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="Enter YouTube URLs (one per line)&#10;https://youtube.com/watch?v=...&#10;https://youtu.be/..."
            rows={6}
            className="input font-mono text-sm resize-none"
            disabled={isDownloading}
          />
        </div>

        {/* Button row */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={isDownloading || urlInput.trim().length === 0}
            className="btn btn-primary flex items-center"
          >
            {isDownloading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                Download Videos
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleClear}
            disabled={isDownloading}
            className="btn btn-outline flex items-center"
          >
            <X className="w-4 h-4 mr-2" />
            Clear
          </button>
        </div>
      </form>

      {/* Results panel */}
      {showResults && downloadResults && (
        <div className="mt-6 pt-6 border-t border-gray-200">
          {/* Summary stats */}
          <div className="mb-4 flex flex-wrap gap-2">
            <span className="badge badge-gray">
              Total: {downloadResults.total}
            </span>
            <span className="badge badge-success">
              Successful: {downloadResults.successful}
            </span>
            <span className="badge badge-warning">
              Duplicates: {downloadResults.duplicates}
            </span>
            <span className="badge badge-danger">
              Failed: {downloadResults.failed}
            </span>
          </div>

          {/* Per-URL results list */}
          {downloadResults.results.length > 0 && (
            <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
              {downloadResults.results.map((result, index) => (
                <div
                  key={index}
                  className="p-3 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-mono text-gray-600 truncate">
                        {result.url}
                      </p>
                      <p className="text-sm text-gray-700 mt-1">{result.message}</p>
                      {result.error && (
                        <p className="text-sm text-red-600 mt-1">{result.error}</p>
                      )}
                    </div>
                    <span className={`${getStatusBadgeClass(result.status)} flex items-center whitespace-nowrap`}>
                      {getStatusIcon(result.status)}
                      {result.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
