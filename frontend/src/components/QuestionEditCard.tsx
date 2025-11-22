/**
 * Component for editing individual questions in a generation.
 * Provides inline editing with validation, reordering, and deletion.
 */

import { useState } from 'react';
import { 
  Save, 
  X, 
  Trash2, 
  ChevronUp, 
  ChevronDown,
  AlertCircle,
  GripVertical,
  Loader2
} from 'lucide-react';
import { Question, UpdateQuestionRequest } from '@/types';
import { ConfirmDialog } from './ConfirmDialog';

interface QuestionEditCardProps {
  question: Question;
  index?: number;
  onUpdate: (id: number, updates: UpdateQuestionRequest) => void;
  onDelete: (id: number) => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  isUpdating?: boolean;
  isDeleting?: boolean;
}

/**
 * Editable question card with save/cancel, reordering, and delete functionality
 */
export const QuestionEditCard = ({
  question,
  index,
  onUpdate,
  onDelete,
  onMoveUp,
  onMoveDown,
  isUpdating = false,
  isDeleting = false,
}: QuestionEditCardProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  // Local state for editing
  const [editedQuestion, setEditedQuestion] = useState({
    question_text: question.question_text,
    context: question.context || '',
    difficulty: question.difficulty || '',
    question_type: question.question_type || '',
  });

  // Validation function
  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!editedQuestion.question_text.trim()) {
      newErrors.question_text = 'Question text is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle save
  const handleSave = () => {
    if (!validate()) return;
    
    const updates: UpdateQuestionRequest = {};
    
    if (editedQuestion.question_text !== question.question_text) {
      updates.question_text = editedQuestion.question_text;
    }
    if (editedQuestion.context !== (question.context || '')) {
      updates.context = editedQuestion.context || undefined;
    }
    if (editedQuestion.difficulty !== (question.difficulty || '')) {
      updates.difficulty = editedQuestion.difficulty || undefined;
    }
    if (editedQuestion.question_type !== (question.question_type || '')) {
      updates.question_type = editedQuestion.question_type || undefined;
    }
    
    if (Object.keys(updates).length > 0) {
      onUpdate(question.id, updates);
    }
    
    setIsEditing(false);
    setErrors({});
  };

  // Handle cancel
  const handleCancel = () => {
    setEditedQuestion({
      question_text: question.question_text,
      context: question.context || '',
      difficulty: question.difficulty || '',
      question_type: question.question_type || '',
    });
    setIsEditing(false);
    setErrors({});
  };

  // Handle delete
  const handleDelete = () => {
    onDelete(question.id);
    setShowDeleteConfirm(false);
  };

  return (
    <article 
      className={`card responsive-card-padding relative flex flex-col sm:flex-row gap-3 transition-opacity ${isDeleting ? 'opacity-50 pointer-events-none' : ''}`}
      aria-label={`Question ${index !== undefined ? index + 1 : ''} - ${isEditing ? 'Editing' : 'View'} mode`}
      aria-busy={isDeleting || isUpdating}
    >
      {/* Loading overlay during deletion */}
      {isDeleting && (
        <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center rounded-lg z-10" role="status" aria-live="polite">
          <div className="flex items-center gap-2 text-gray-700">
            <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
            <span className="font-medium">Deleting question...</span>
          </div>
        </div>
      )}

      {/* Drag handle */}
      <div className="flex-shrink-0 flex items-start pt-1 hide-mobile" role="button" aria-label="Drag to reorder" tabIndex={0}>
        <GripVertical className="w-5 h-5 text-gray-400 cursor-move hover:text-gray-600" aria-hidden="true" />
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        {/* Header section with controls */}
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <div className="flex items-center gap-2">
            {index !== undefined && (
              <span className="badge badge-primary">
                Question {index + 1}
              </span>
            )}
            {!isEditing && question.difficulty && (
              <span className={`badge ${
                question.difficulty === 'easy' ? 'badge-success' :
                question.difficulty === 'medium' ? 'badge-warning' :
                question.difficulty === 'hard' ? 'badge-danger' :
                'badge-gray'
              }`}>
                {question.difficulty}
              </span>
            )}
            {!isEditing && question.question_type && (
              <span className="badge badge-gray">
                {question.question_type}
              </span>
            )}
          </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Reorder buttons */}
          {!isEditing && (
            <>
              {onMoveUp && (
                <button
                  onClick={onMoveUp}
                  className="btn btn-sm btn-touch btn-outline focus-visible:ring-2 focus-visible:ring-primary-500"
                  title="Move question up"
                  aria-label={`Move question ${index !== undefined ? index + 1 : ''} up`}
                  disabled={isUpdating || isDeleting}
                  type="button"
                >
                  <ChevronUp className="w-4 h-4" aria-hidden="true" />
                  <span className="sr-only">Move up</span>
                </button>
              )}
              {onMoveDown && (
                <button
                  onClick={onMoveDown}
                  className="btn btn-sm btn-touch btn-outline focus-visible:ring-2 focus-visible:ring-primary-500"
                  title="Move question down"
                  aria-label={`Move question ${index !== undefined ? index + 1 : ''} down`}
                  disabled={isUpdating || isDeleting}
                  type="button"
                >
                  <ChevronDown className="w-4 h-4" aria-hidden="true" />
                  <span className="sr-only">Move down</span>
                </button>
              )}
            </>
          )}

          {/* Edit/Save/Cancel buttons */}
          {isEditing ? (
            <>
              <button
                onClick={handleSave}
                className="btn btn-sm btn-touch btn-primary"
                disabled={isUpdating}
                aria-label="Save changes"
                type="button"
              >
                <Save className="w-4 h-4 mr-1" aria-hidden="true" />
                <span className="hide-mobile">Save</span>
                <span className="show-mobile sr-only">Save</span>
              </button>
              <button
                onClick={handleCancel}
                className="btn btn-sm btn-touch btn-outline"
                disabled={isUpdating}
                aria-label="Cancel editing"
                type="button"
              >
                <X className="w-4 h-4 mr-1" aria-hidden="true" />
                <span className="hide-mobile">Cancel</span>
                <span className="show-mobile sr-only">Cancel</span>
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setIsEditing(true)}
                className="btn btn-sm btn-touch btn-outline"
                disabled={isUpdating || isDeleting}
                aria-label="Edit question"
                type="button"
              >
                Edit
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="btn btn-sm btn-touch btn-outline text-red-600 hover:bg-red-50 border-red-300 inline-flex items-center justify-center focus-visible:ring-2 focus-visible:ring-red-500"
                disabled={isUpdating || isDeleting}
                aria-label="Delete question"
                aria-busy={isDeleting}
                type="button"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Trash2 className="w-4 h-4" aria-hidden="true" />
                )}
                <span className="sr-only">{isDeleting ? 'Deleting' : 'Delete'}</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Question text section */}
      <div className="mt-3">
        {isEditing ? (
          <div>
            <label htmlFor={`question-text-${question.id}`} className="block text-sm font-medium text-gray-700 mb-1">
              Question Text *
            </label>
            <textarea
              id={`question-text-${question.id}`}
              value={editedQuestion.question_text}
              onChange={(e) => setEditedQuestion({
                ...editedQuestion,
                question_text: e.target.value
              })}
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                errors.question_text ? 'border-red-500' : 'border-gray-300'
              }`}
              rows={3}
              placeholder="Enter question text..."
              aria-required="true"
              aria-invalid={!!errors.question_text}
              aria-describedby={errors.question_text ? `question-text-error-${question.id}` : undefined}
            />
            {errors.question_text && (
              <div id={`question-text-error-${question.id}`} className="flex items-center gap-1 mt-1 text-sm text-red-600" role="alert">
                <AlertCircle className="w-4 h-4" aria-hidden="true" />
                {errors.question_text}
              </div>
            )}
          </div>
        ) : (
          <div className="text-lg font-medium text-gray-900" role="heading" aria-level={3}>
            {question.question_text}
          </div>
        )}
      </div>

      {/* Difficulty and Type selects (edit mode) */}
      {isEditing && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <label htmlFor={`difficulty-${question.id}`} className="block text-sm font-medium text-gray-700 mb-1">
              Difficulty
            </label>
            <select
              id={`difficulty-${question.id}`}
              value={editedQuestion.difficulty}
              onChange={(e) => setEditedQuestion({
                ...editedQuestion,
                difficulty: e.target.value
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              aria-label="Select question difficulty"
            >
              <option value="">Select difficulty</option>
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>

          <div>
            <label htmlFor={`question-type-${question.id}`} className="block text-sm font-medium text-gray-700 mb-1">
              Question Type
            </label>
            <select
              id={`question-type-${question.id}`}
              value={editedQuestion.question_type}
              onChange={(e) => setEditedQuestion({
                ...editedQuestion,
                question_type: e.target.value
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              aria-label="Select question type"
            >
              <option value="">Select type</option>
              <option value="factual">Factual</option>
              <option value="conceptual">Conceptual</option>
              <option value="analytical">Analytical</option>
            </select>
          </div>
        </div>
      )}

      {/* Context section */}
      <div className="mt-4">
        {isEditing ? (
          <div>
            <label htmlFor={`context-${question.id}`} className="block text-sm font-medium text-gray-700 mb-1">
              Context
            </label>
            <textarea
              id={`context-${question.id}`}
              value={editedQuestion.context}
              onChange={(e) => setEditedQuestion({
                ...editedQuestion,
                context: e.target.value
              })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={3}
              placeholder="Enter context from the video..."
              aria-label="Question context from video"
            />
          </div>
        ) : (
          question.context && (
            <div role="region" aria-label="Question context">
              <span className="text-sm font-medium text-gray-700" id={`context-label-${question.id}`}>Context:</span>
              <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200 mt-1 italic" aria-labelledby={`context-label-${question.id}`}>
                {question.context}
              </div>
            </div>
          )
        )}
      </div>

        {/* Footer section */}
        {!isEditing && (
          <div className="text-xs text-gray-500 mt-3 flex items-center gap-2 flex-wrap">
            <span className="badge badge-gray text-xs font-mono">
              {question.video_id}
            </span>
            <span>•</span>
            <span>
              Updated: {new Date(question.updated_at).toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        title="Delete Question?"
        message="Are you sure you want to delete this question? This action cannot be undone."
        confirmLabel="Delete Question"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteConfirm(false)}
        isLoading={isDeleting}
      />
    </article>
  );
};
