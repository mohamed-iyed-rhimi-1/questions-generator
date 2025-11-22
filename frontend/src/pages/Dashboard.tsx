import { RefreshCw } from 'lucide-react'
import { useVideos } from '@/hooks/useVideos'
import { DownloadSection } from '@/components/DownloadSection'
import { VideoGrid } from '@/components/VideoGrid'
import { TranscriptionSection } from '@/components/TranscriptionSection'
import { QuestionGenerationSection } from '@/components/QuestionGenerationSection'

export function Dashboard() {
  const { videos, isLoading, refetch } = useVideos()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header section */}
      <header className="bg-gradient-to-r from-primary-600 to-secondary-600 text-white responsive-section-spacing responsive-container-padding">
        <div className="max-w-7xl mx-auto">
          <h1 className="responsive-heading-1 font-bold mb-2">
            YouTube Question Generator
          </h1>
          <p className="text-base sm:text-lg text-primary-100">
            Download videos, transcribe audio, and generate questions with AI
          </p>
        </div>
      </header>

      {/* Main content area */}
      <main className="max-w-7xl mx-auto responsive-container-padding responsive-section-spacing">
        {/* Section 1: Download Section */}
        <div className="mb-8 sm:mb-10 md:mb-12">
          <DownloadSection />
        </div>

        {/* Section 2: Downloaded Videos */}
        <section>
          {/* Section header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4 mb-4 sm:mb-6">
            <div className="flex items-center flex-wrap gap-2">
              <h2 className="responsive-heading-2 font-bold text-gray-900">
                Downloaded Videos
              </h2>
              <span className="badge badge-primary">
                {videos.length} video{videos.length !== 1 ? 's' : ''}
              </span>
            </div>
            <button
              onClick={() => refetch()}
              disabled={isLoading}
              className="btn btn-sm btn-touch btn-outline flex items-center justify-center"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {/* Error state - removed inline alert to avoid duplicate with axios interceptor toast */}

          {/* Video grid */}
          <VideoGrid videos={videos} isLoading={isLoading} />
        </section>

        {/* Section 3: Transcription Section */}
        <div className="mt-8 sm:mt-10 md:mt-12">
          <TranscriptionSection videos={videos} />
        </div>

        {/* Section 4: Question Generation Section */}
        <div className="mt-8 sm:mt-10 md:mt-12">
          <QuestionGenerationSection videos={videos} />
        </div>
      </main>
    </div>
  )
}
