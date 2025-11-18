import { useEffect } from 'react'
import { X } from 'lucide-react'
import { Transcription } from '@/types'

/**
 * Props for TranscriptionModal component
 */
interface TranscriptionModalProps {
  isOpen: boolean
  onClose: () => void
  transcription: Transcription | null
  videoTitle?: string
}

/**
 * TranscriptionModal Component
 * Displays full transcription text in a modal dialog
 */
export function TranscriptionModal({
  isOpen,
  onClose,
  transcription,
  videoTitle,
}: TranscriptionModalProps) {
  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleCopyToClipboard = () => {
    if (transcription?.transcription_text) {
      navigator.clipboard.writeText(transcription.transcription_text)
      // Note: Could add toast notification here if desired
    }
  }

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 bg-black/50 z-50 transition-opacity duration-200"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal container */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="relative w-full max-w-4xl max-h-[80vh] bg-white rounded-lg shadow-xl flex flex-col animate-slide-up"
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          {/* Modal header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <h2 id="modal-title" className="text-xl font-bold text-gray-900">
              {videoTitle ? `Transcription - ${videoTitle}` : 'Transcription'}
            </h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              aria-label="Close modal"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Modal body */}
          <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
            {!transcription ? (
              <p className="text-gray-500 text-center py-8">No transcription available</p>
            ) : (
              <div className="prose max-w-none">
                <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                  {transcription.transcription_text}
                </p>
              </div>
            )}
          </div>

          {/* Modal footer */}
          {transcription && (
            <div className="p-6 border-t border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-4 text-sm text-gray-600">
                  <span>
                    Created: {new Date(transcription.created_at).toLocaleDateString()}
                  </span>
                  <span className="badge badge-gray">
                    {transcription.status}
                  </span>
                  <span>
                    {transcription.transcription_text.length} characters
                  </span>
                </div>
                <button
                  onClick={handleCopyToClipboard}
                  className="btn btn-sm btn-outline"
                >
                  Copy to Clipboard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
