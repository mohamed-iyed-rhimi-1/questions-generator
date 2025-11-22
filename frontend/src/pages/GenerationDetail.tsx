import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { Calendar, Video, FileText, Edit, Eye, ArrowLeft, AlertCircle, Save, X, Trash2 } from 'lucide-react'
import { useGeneration } from '@/hooks/useGeneration'
import { useReorderQuestions } from '@/hooks/useReorderQuestions'
import { useUpdateQuestion } from '@/hooks/useUpdateQuestion'
import { useDeleteQuestion } from '@/hooks/useDeleteQuestion'
import { useDeleteGeneration } from '@/hooks/useDeleteGeneration'
import { QuestionCard } from '@/components/QuestionCard'
import { QuestionEditCard } from '@/components/QuestionEditCard'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { EmptyState } from '@/components/EmptyState'
import { Question, UpdateQuestionRequest } from '@/types'

export function GenerationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [editMode, setEditMode] = useState(searchParams.get('edit') === 'true')
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [showExitConfirm, setShowExitConfirm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const { generation, isLoading, isError, error } = useGeneration(id)
  
  // Hooks for mutations
  const generationId = id ? parseInt(id) : 0
  const { reorderQuestions } = useReorderQuestions(generationId)
  const { updateQuestion: updateQuestionMutation, isUpdating } = useUpdateQuestion(generationId)
  const { deleteQuestion, isDeleting: isDeletingQuestion } = useDeleteQuestion(generationId)
  const { deleteGeneration, isDeleting: isDeletingGeneration } = useDeleteGeneration()
  
  // Wrapper function to match QuestionEditCard's expected signature
  const handleUpdateQuestion = (questionId: number, updates: UpdateQuestionRequest) => {
    updateQuestionMutation({ questionId, updates })
    setHasUnsavedChanges(true)
  }
  
  // Handle edit mode toggle with confirmation if there are unsaved changes
  const handleEditModeToggle = () => {
    if (editMode && hasUnsavedChanges) {
      setShowExitConfirm(true)
    } else {
      setEditMode(!editMode)
      setHasUnsavedChanges(false)
    }
  }
  
  // Confirm exit edit mode
  const handleConfirmExit = () => {
    setEditMode(false)
    setHasUnsavedChanges(false)
    setShowExitConfirm(false)
  }
  
  // Cancel exit (stay in edit mode)
  const handleCancelExit = () => {
    setShowExitConfirm(false)
  }
  
  // Save all changes (in this implementation, changes are auto-saved)
  const handleSaveAll = () => {
    // Since changes are auto-saved via individual mutations,
    // we just need to clear the unsaved changes flag and exit edit mode
    setHasUnsavedChanges(false)
    setEditMode(false)
  }
  
  // Handle generation deletion
  const handleDeleteGeneration = () => {
    if (generationId) {
      deleteGeneration(generationId)
    }
  }
  
  // Local state for drag and drop
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [localQuestions, setLocalQuestions] = useState<Question[]>([])
  
  // Update local questions when generation data changes
  useEffect(() => {
    if (generation?.questions) {
      setLocalQuestions([...generation.questions])
    }
  }, [generation?.questions])

  // Drag and drop handlers
  const handleDragStart = (index: number) => {
    setDraggedIndex(index)
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    setDragOverIndex(index)
  }

  const handleDragLeave = () => {
    setDragOverIndex(null)
  }

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault()
    
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null)
      setDragOverIndex(null)
      return
    }

    // Create new array with reordered questions
    const newQuestions = [...localQuestions]
    const [draggedQuestion] = newQuestions.splice(draggedIndex, 1)
    newQuestions.splice(dropIndex, 0, draggedQuestion)
    
    // Update local state optimistically
    setLocalQuestions(newQuestions)
    setHasUnsavedChanges(true)
    
    // Call API to persist the new order
    const questionIds = newQuestions.map(q => q.id)
    reorderQuestions(questionIds)
    
    // Reset drag state
    setDraggedIndex(null)
    setDragOverIndex(null)
  }

  const handleDragEnd = () => {
    setDraggedIndex(null)
    setDragOverIndex(null)
  }

  // Move up/down handlers (alternative to drag-and-drop)
  const handleMoveUp = (index: number) => {
    if (index === 0) return
    
    const newQuestions = [...localQuestions]
    const temp = newQuestions[index - 1]
    newQuestions[index - 1] = newQuestions[index]
    newQuestions[index] = temp
    
    setLocalQuestions(newQuestions)
    setHasUnsavedChanges(true)
    
    const questionIds = newQuestions.map(q => q.id)
    reorderQuestions(questionIds)
  }

  const handleMoveDown = (index: number) => {
    if (index === localQuestions.length - 1) return
    
    const newQuestions = [...localQuestions]
    const temp = newQuestions[index + 1]
    newQuestions[index + 1] = newQuestions[index]
    newQuestions[index] = temp
    
    setLocalQuestions(newQuestions)
    setHasUnsavedChanges(true)
    
    const questionIds = newQuestions.map(q => q.id)
    reorderQuestions(questionIds)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8">
          <div className="max-w-7xl mx-auto">
            <button
              onClick={() => navigate('/generations')}
              className="flex items-center text-white hover:text-primary-100 mb-4 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 mr-2" />
              Back to Generations
            </button>
            <h1 className="text-3xl sm:text-4xl font-bold">
              Generation Details
            </h1>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-center py-12">
            <div className="spinner w-12 h-12"></div>
          </div>
        </main>
      </div>
    )
  }

  // Error state - invalid generation ID or other errors
  if (isError || !generation) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8">
          <div className="max-w-7xl mx-auto">
            <button
              onClick={() => navigate('/generations')}
              className="flex items-center text-white hover:text-primary-100 mb-4 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 mr-2" />
              Back to Generations
            </button>
            <h1 className="text-3xl sm:text-4xl font-bold">
              Generation Not Found
            </h1>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="card bg-red-50 border-red-200">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <AlertCircle className="h-6 w-6 text-red-600" />
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">
                  Error loading generation
                </h3>
                <p className="mt-2 text-sm text-red-700">
                  {error?.message || 'The generation you are looking for does not exist or could not be loaded.'}
                </p>
                <button
                  onClick={() => navigate('/generations')}
                  className="mt-4 btn btn-sm btn-outline"
                >
                  Return to Generations List
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    )
  }

  // Main content
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <button
            onClick={() => navigate('/generations')}
            className="flex items-center text-white hover:text-primary-100 mb-4 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Generations
          </button>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <h1 className="responsive-heading-1 font-bold mb-2">
                Generation #{generation.id}
              </h1>
              <p className="text-base sm:text-lg text-primary-100">
                View and manage generated questions
              </p>
            </div>
            <div className="mobile-button-group">
              <button
                onClick={handleEditModeToggle}
                className={`btn btn-touch ${editMode ? 'btn-secondary' : 'btn-outline'} flex items-center justify-center`}
                disabled={isDeletingGeneration}
              >
                {editMode ? (
                  <>
                    <Eye className="w-4 h-4 mr-2" />
                    <span className="hide-mobile">View Mode</span>
                    <span className="show-mobile">View</span>
                  </>
                ) : (
                  <>
                    <Edit className="w-4 h-4 mr-2" />
                    <span className="hide-mobile">Edit Mode</span>
                    <span className="show-mobile">Edit</span>
                  </>
                )}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="btn btn-danger btn-touch flex items-center justify-center"
                disabled={isDeletingGeneration}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                <span className="hide-mobile">Delete Generation</span>
                <span className="show-mobile">Delete</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Generation metadata card */}
        <div className="card mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            Generation Information
          </h2>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-6">
            {/* Creation date */}
            <div className="flex items-start">
              <Calendar className="w-5 h-5 text-primary-600 mr-3 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-gray-500 mb-1">Created</p>
                <p className="text-sm sm:text-base font-medium text-gray-900">
                  {formatDate(generation.created_at)}
                </p>
              </div>
            </div>

            {/* Question count */}
            <div className="flex items-start">
              <FileText className="w-5 h-5 text-secondary-600 mr-3 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-gray-500 mb-1">Questions</p>
                <p className="text-sm sm:text-base font-medium text-gray-900">
                  {generation.question_count} question{generation.question_count !== 1 ? 's' : ''}
                </p>
              </div>
            </div>

            {/* Video count */}
            <div className="flex items-start">
              <Video className="w-5 h-5 text-accent-600 mr-3 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm text-gray-500 mb-1">Source Videos</p>
                <p className="text-sm sm:text-base font-medium text-gray-900">
                  {generation.video_ids.length} video{generation.video_ids.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          </div>

          {/* Video IDs list */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-sm font-medium text-gray-700 mb-3">Source Video IDs:</p>
            <div className="flex flex-wrap gap-2">
              {generation.video_ids.map((videoId) => (
                <span
                  key={videoId}
                  className="badge badge-gray font-mono text-xs"
                  title={videoId}
                >
                  {videoId}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Questions section */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900">
              Questions
            </h2>
            <span className="badge badge-primary">
              {localQuestions.length} total
            </span>
          </div>

          {localQuestions.length === 0 ? (
            <div className="card">
              <EmptyState
                icon={FileText}
                title="No questions found"
                description="This generation does not contain any questions. This might happen if all questions were deleted or if the generation failed."
                actionLabel="Back to Generations"
                onAction={() => navigate('/generations')}
              />
            </div>
          ) : (
            <div className="space-y-4">
              {localQuestions.map((question, index) => (
                <div
                  key={question.id}
                  draggable={editMode}
                  onDragStart={() => handleDragStart(index)}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, index)}
                  onDragEnd={handleDragEnd}
                  className={`
                    ${editMode ? 'cursor-move' : ''}
                    ${draggedIndex === index ? 'opacity-50' : ''}
                    ${dragOverIndex === index && draggedIndex !== index ? 'border-t-4 border-blue-500' : ''}
                    transition-opacity duration-200
                  `}
                >
                  {editMode ? (
                    <QuestionEditCard
                      question={question}
                      index={index}
                      onUpdate={handleUpdateQuestion}
                      onDelete={deleteQuestion}
                      onMoveUp={index > 0 ? () => handleMoveUp(index) : undefined}
                      onMoveDown={index < localQuestions.length - 1 ? () => handleMoveDown(index) : undefined}
                      isUpdating={isUpdating}
                      isDeleting={isDeletingQuestion}
                    />
                  ) : (
                    <QuestionCard
                      question={question}
                      index={index}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Edit mode notice */}
        {editMode && (
          <div className="card bg-blue-50 border-blue-200 mt-6">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <Edit className="h-5 w-5 text-blue-600" />
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-blue-800">
                  Edit Mode Active
                </h3>
                <p className="mt-1 text-sm text-blue-700">
                  You can now edit questions, reorder them by dragging, or use the up/down buttons. 
                  Changes are saved automatically.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Sticky action bar for edit mode */}
      {editMode && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-40">
          <div className="max-w-7xl mx-auto responsive-container-padding py-3 sm:py-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex items-center gap-2">
                <Edit className="w-5 h-5 text-blue-600 flex-shrink-0" />
                <span className="text-sm font-medium text-gray-700">
                  Edit Mode Active
                </span>
                {hasUnsavedChanges && (
                  <span className="badge badge-warning text-xs">
                    Unsaved changes
                  </span>
                )}
              </div>
              <div className="mobile-button-group">
                <button
                  onClick={handleEditModeToggle}
                  className="btn btn-outline btn-touch flex items-center justify-center"
                >
                  <X className="w-4 h-4 mr-2" />
                  Cancel
                </button>
                <button
                  onClick={handleSaveAll}
                  className="btn btn-primary btn-touch flex items-center justify-center"
                  disabled={!hasUnsavedChanges}
                >
                  <Save className="w-4 h-4 mr-2" />
                  <span className="hide-mobile">Save All & Exit</span>
                  <span className="show-mobile">Save & Exit</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Exit confirmation dialog */}
      {showExitConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-start mb-4">
              <div className="flex-shrink-0">
                <AlertCircle className="h-6 w-6 text-yellow-600" />
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  Unsaved Changes
                </h3>
                <p className="text-gray-600">
                  You have unsaved changes. Are you sure you want to exit edit mode? 
                  Your changes have been automatically saved, but you may want to review them first.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={handleCancelExit}
                className="btn btn-outline"
              >
                Stay in Edit Mode
              </button>
              <button
                onClick={handleConfirmExit}
                className="btn btn-primary"
              >
                Exit Anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete generation confirmation dialog */}
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="Delete Generation?"
        message={`Are you sure you want to delete Generation #${generation?.id}? This will permanently delete all ${generation?.question_count || 0} questions in this generation. This action cannot be undone.`}
        confirmLabel="Delete Generation"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleDeleteGeneration}
        onCancel={() => setShowDeleteConfirm(false)}
        isLoading={isDeletingGeneration}
      />
    </div>
  )
}
