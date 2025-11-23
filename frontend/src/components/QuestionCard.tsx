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

  console.log({
    question
  })

  return (
    <article className="card responsive-card-padding" aria-label={`Question ${index !== undefined ? index + 1 : ''}`}>
      {/* Header section */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="flex items-center gap-2" role="group" aria-label="Question metadata">
          {index !== undefined && (
            <span className="badge badge-primary" aria-label={`Question number ${index + 1}`}>
              Question {index + 1}
            </span>
          )}
          {question.difficulty && (
            <span className={getDifficultyClass()} aria-label={`Difficulty: ${question.difficulty}`}>
              {question.difficulty}
            </span>
          )}
          {question.question_type && (
            <span className="badge badge-gray flex items-center" aria-label={`Type: ${question.question_type}`}>
              {getTypeIcon()}
              {question.question_type}
            </span>
          )}
        </div>
      </div>

      {/* Question text section */}
      <div className="text-base sm:text-lg font-medium text-gray-900 mt-3 mb-2" role="heading" aria-level={3}>
        {question.question_text}
      </div>

      {/* Answer section */}
      {question.answer && (
        <div className="mt-3" role="region" aria-label="Question answer">
          <span className="text-sm font-medium text-gray-700" id={`answer-label-${question.id}`}>الإجابة:</span>
          <div 
            className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg border border-blue-200 mt-1 leading-relaxed" 
            aria-labelledby={`answer-label-${question.id}`}
          >
            {question.answer}
          </div>
        </div>
      )}

      {/* Context section */}
      {question.context && (
        <div className="mt-3" role="region" aria-label="Question context">
          <span className="text-sm font-medium text-gray-700" id={`context-label-${question.id}`}>Context:</span>
          <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-200 mt-1 italic" aria-labelledby={`context-label-${question.id}`}>
            {question.context}
          </div>
        </div>
      )}

      {/* Footer section */}
      <div className="text-xs text-gray-500 mt-3 flex items-center gap-2 flex-wrap" role="contentinfo" aria-label="Question metadata">
        <span className="badge badge-gray text-xs font-mono" aria-label={`Video ID: ${question.video_id}`}>
          {question.video_id}
        </span>
        <span aria-hidden="true">•</span>
        <time dateTime={question.created_at} aria-label={`Created at ${new Date(question.created_at).toLocaleString()}`}>
          {new Date(question.created_at).toLocaleString()}
        </time>
      </div>
    </article>
  );
};
