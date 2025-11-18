/**
 * Component for displaying individual generated questions in a card format.
 * Follows established card design patterns from VideoCard.
 */

import { HelpCircle, BookOpen, Lightbulb } from 'lucide-react';
import { Question } from '@/types';

interface QuestionCardProps {
  question: Question;
  index?: number;
}

/**
 * Displays a single generated question in a visually appealing card format
 */
export const QuestionCard = ({ question, index }: QuestionCardProps) => {
  // Get icon based on question type
  const getTypeIcon = () => {
    switch (question.question_type) {
      case 'factual':
        return <BookOpen className="w-3 h-3 mr-1" />;
      case 'conceptual':
        return <Lightbulb className="w-3 h-3 mr-1" />;
      case 'analytical':
        return <HelpCircle className="w-3 h-3 mr-1" />;
      default:
        return null;
    }
  };

  // Get difficulty badge class
  const getDifficultyClass = () => {
    switch (question.difficulty) {
      case 'easy':
        return 'badge badge-success';
      case 'medium':
        return 'badge badge-warning';
      case 'hard':
        return 'badge badge-danger';
      default:
        return 'badge badge-gray';
    }
  };

  return (
    <article className="card p-6">
      {/* Header section */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="flex items-center gap-2">
          {index !== undefined && (
            <span className="badge badge-primary">
              Question {index + 1}
            </span>
          )}
          {question.difficulty && (
            <span className={getDifficultyClass()}>
              {question.difficulty}
            </span>
          )}
          {question.question_type && (
            <span className="badge badge-gray flex items-center">
              {getTypeIcon()}
              {question.question_type}
            </span>
          )}
        </div>
      </div>

      {/* Question text section */}
      <div className="text-lg font-medium text-gray-900 mt-3 mb-2">
        {question.question_text}
      </div>

      {/* Context section */}
      {question.context && (
        <div className="mt-2">
          <span className="text-sm font-medium text-gray-700">Context:</span>
          <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200 mt-1 italic">
            {question.context}
          </div>
        </div>
      )}

      {/* Footer section */}
      <div className="text-xs text-gray-500 mt-3 flex items-center gap-2 flex-wrap">
        <span className="badge badge-gray text-xs font-mono">
          {question.video_id}
        </span>
        <span>•</span>
        <span>
          {new Date(question.created_at).toLocaleString()}
        </span>
      </div>
    </article>
  );
};
