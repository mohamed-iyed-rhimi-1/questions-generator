/**
 * QuestionGenerationSection component for selecting transcribed videos and generating questions.
 * Follows the TranscriptionSection pattern.
 */

import { useState, useMemo, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import { Sparkles, Loader2, CheckCircle2, AlertCircle, FileQuestion, X } from 'lucide-react';
import { useGenerateQuestions } from '@/hooks/useGenerateQuestions';
import { useTranscriptions } from '@/hooks/useTranscriptions';
import { QuestionCard } from '@/components/QuestionCard';
import { Video, Question, QuestionGenerationResult } from '@/types';

interface QuestionGenerationSectionProps {
  videos: Video[];
}

/**
 * Section for generating AI-powered questions from transcribed videos
 */
export const QuestionGenerationSection = ({ videos }: QuestionGenerationSectionProps) => {
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());
  const [showResults, setShowResults] = useState(false);
  const [allGeneratedQuestions, setAllGeneratedQuestions] = useState<Question[]>([]);

  // Fetch existing transcriptions
  const { transcriptions } = useTranscriptions();

  // Create lookup map for transcriptions
  const videoIdToTranscription = useMemo(() => {
    const map = new Map();
    transcriptions?.forEach((transcription) => {
      map.set(transcription.video_id, transcription);
    });
    return map;
  }, [transcriptions]);

  // Destructure generation hook
  const { generateQuestions, isGenerating, questionResults, reset } = useGenerateQuestions();

  // Get videos that have transcriptions
  const getTranscribedVideos = useMemo(() => {
    return videos.filter((video) => videoIdToTranscription.has(video.video_id));
  }, [videos, videoIdToTranscription]);

  // Update allGeneratedQuestions when questionResults changes
  useEffect(() => {
    if (questionResults) {
      const questions: Question[] = [];
      questionResults.results.forEach((result) => {
        if (result.status === 'success' && result.questions) {
          questions.push(...result.questions);
        }
      });
      setAllGeneratedQuestions(questions);
    }
  }, [questionResults]);

  // Selection handlers
  const handleVideoSelect = (videoId: string) => {
    const newSelected = new Set(selectedVideoIds);
    if (newSelected.has(videoId)) {
      newSelected.delete(videoId);
    } else {
      newSelected.add(videoId);
    }
    setSelectedVideoIds(newSelected);
  };

  const handleSelectAll = () => {
    const allTranscribedIds = new Set(
      getTranscribedVideos.map((video) => video.video_id)
    );
    setSelectedVideoIds(allTranscribedIds);
  };

  const handleDeselectAll = () => {
    setSelectedVideoIds(new Set());
  };

  // Form submission
  const handleSubmit = () => {
    if (selectedVideoIds.size === 0) {
      toast.error('Please select at least one video');
      return;
    }

    // Validate that selected videos have transcriptions
    const selectedArray = Array.from(selectedVideoIds);
    const missingTranscriptions = selectedArray.filter(
      (videoId) => !videoIdToTranscription.has(videoId)
    );

    if (missingTranscriptions.length > 0) {
      toast.error('Some selected videos do not have transcriptions');
      return;
    }

    // Generate questions
    generateQuestions(selectedArray);
    setShowResults(true);
  };

  // Clear/reset handler
  const handleClear = () => {
    setSelectedVideoIds(new Set());
    reset();
    setShowResults(false);
    setAllGeneratedQuestions([]);
  };

  // Get status badge class
  const getStatusBadgeClass = (status: QuestionGenerationResult['status']) => {
    switch (status) {
      case 'success':
        return 'badge badge-success';
      case 'no_transcription':
        return 'badge badge-warning';
      case 'failed':
        return 'badge badge-danger';
      default:
        return 'badge badge-gray';
    }
  };

  // Get status icon
  const getStatusIcon = (status: QuestionGenerationResult['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'no_transcription':
      case 'failed':
        return <AlertCircle className="w-4 h-4" />;
      default:
        return <FileQuestion className="w-4 h-4" />;
    }
  };

  return (
    <div className="card">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Generate Questions</h2>
        <p className="text-gray-600">
          Select transcribed videos to generate AI-powered questions using Ollama
        </p>
      </div>

      {/* Video selection area */}
      <div className="mb-6">
        {/* Selection controls */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <span className="badge badge-primary">
            {selectedVideoIds.size} selected
          </span>
          <button
            onClick={handleSelectAll}
            disabled={isGenerating || getTranscribedVideos.length === 0}
            className="btn btn-outline text-sm"
          >
            Select All Transcribed
          </button>
          <button
            onClick={handleDeselectAll}
            disabled={isGenerating || selectedVideoIds.size === 0}
            className="btn btn-outline text-sm"
          >
            Deselect All
          </button>
        </div>

        {/* Video list */}
        <div className="max-h-96 overflow-y-auto border border-gray-200 rounded-lg">
          {getTranscribedVideos.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <FileQuestion className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>No transcribed videos available. Transcribe videos first.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
              {getTranscribedVideos.map((video) => (
                <div
                  key={video.video_id}
                  onClick={() => {
                    if (isGenerating) return;
                    handleVideoSelect(video.video_id);
                  }}
                  className={`
                    p-4 border-2 rounded-lg transition-all
                    ${
                      selectedVideoIds.has(video.video_id)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }
                    ${isGenerating ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}
                  `}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={selectedVideoIds.has(video.video_id)}
                      onChange={() => handleVideoSelect(video.video_id)}
                      onClick={(e) => e.stopPropagation()}
                      className="mt-1"
                      disabled={isGenerating}
                    />
                    <div className="flex-1 min-w-0">
                      {video.thumbnail_url && (
                        <img
                          src={video.thumbnail_url}
                          alt={video.title}
                          className="w-full h-24 object-cover rounded mb-2"
                        />
                      )}
                      <h3 className="font-medium text-gray-900 text-sm mb-1 truncate">
                        {video.title}
                      </h3>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="badge badge-gray text-xs font-mono">
                          {video.video_id}
                        </span>
                        <span className="badge badge-success text-xs">
                          Transcribed
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleSubmit}
          disabled={isGenerating || selectedVideoIds.size === 0}
          className="btn btn-primary"
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="w-5 h-5 mr-2" />
              Generate Questions
            </>
          )}
        </button>
        <button
          onClick={handleClear}
          disabled={isGenerating}
          className="btn btn-outline"
        >
          <X className="w-5 h-5 mr-2" />
          Clear Selection
        </button>
      </div>

      {/* Results panel */}
      {showResults && questionResults && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Generation Results</h3>
          
          {/* Summary stats */}
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <span className="badge badge-gray">
              Total: {questionResults.total}
            </span>
            <span className="badge badge-success">
              Successful: {questionResults.successful}
            </span>
            <span className="badge badge-danger">
              Failed: {questionResults.failed}
            </span>
            <span className="badge badge-warning">
              No Transcription: {questionResults.no_transcription}
            </span>
            <span className="badge badge-primary text-base font-semibold">
              Total Questions: {questionResults.total_questions}
            </span>
          </div>

          {/* Per-video results list */}
          <div className="space-y-2">
            {questionResults.results.map((result) => (
              <div
                key={result.video_id}
                className="p-3 bg-white rounded border border-gray-200"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-1">
                    {getStatusIcon(result.status)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="badge badge-gray text-xs font-mono">
                        {result.video_id}
                      </span>
                      <span className={getStatusBadgeClass(result.status)}>
                        {result.status}
                      </span>
                      {result.status === 'success' && (
                        <span className="text-xs text-gray-600">
                          ({result.question_count} questions)
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700">{result.message}</p>
                    {result.error && (
                      <p className="text-sm text-red-600 mt-1">{result.error}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Generated Questions Display */}
      {allGeneratedQuestions.length > 0 && (
        <div>
          <h3 className="text-xl font-semibold text-gray-900 mb-4">
            Generated Questions ({allGeneratedQuestions.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[600px] overflow-y-auto">
            {allGeneratedQuestions.map((question, index) => (
              <QuestionCard key={question.id} question={question} index={index} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
