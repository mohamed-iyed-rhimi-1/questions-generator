import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { ErrorBoundary } from 'react-error-boundary'
import { AlertCircle } from 'lucide-react'
import { Dashboard } from '@/pages/Dashboard'
import { Generations } from '@/pages/Generations'
import { GenerationDetail } from '@/pages/GenerationDetail'
import { Layout } from '@/components/Layout'

// Error fallback component
function ErrorFallback({ error, resetErrorBoundary }: { error: Error; resetErrorBoundary: () => void }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        <div className="flex items-center gap-3 mb-4">
          <AlertCircle className="w-8 h-8 text-red-600" />
          <h1 className="text-2xl font-bold text-gray-900">Something went wrong</h1>
        </div>
        <p className="text-gray-700 mb-6">
          {error.message || 'An unexpected error occurred. Please try again.'}
        </p>
        <div className="flex gap-3">
          <button
            onClick={resetErrorBoundary}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
          <button
            onClick={() => window.location.href = '/'}
            className="flex-1 px-4 py-2 bg-gray-200 text-gray-900 rounded-md hover:bg-gray-300 transition-colors"
          >
            Go to Home
          </button>
        </div>
        {/* Development-only error details */}
        <details className="mt-6">
          <summary className="text-sm text-gray-600 cursor-pointer">Error details</summary>
          <pre className="mt-2 text-xs bg-gray-100 p-3 rounded overflow-auto">
            {error.stack}
          </pre>
        </details>
      </div>
    </div>
  );
}

// Create QueryClient instance with enhanced retry logic
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)
      retry: (failureCount, error: unknown) => {
        // Don't retry on 4xx errors (client errors)
        const axiosError = error as { response?: { status?: number } };
        if (axiosError?.response?.status && axiosError.response.status >= 400 && axiosError.response.status < 500) {
          return false;
        }
        // Retry up to 3 times for 5xx errors and network errors
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
    },
    mutations: {
      onError: (error: unknown) => {
        console.error('Mutation error:', error);
      },
    },
  },
})

function App() {
  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onReset={() => window.location.href = '/'}
      onError={(error, errorInfo) => {
        console.error('Error boundary caught:', error, errorInfo);
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/generations" element={<Generations />} />
              <Route path="/generations/:id" element={<GenerationDetail />} />
            </Routes>
          </Layout>
        </BrowserRouter>
        
        {/* Global toast notifications */}
        <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            duration: 3000,
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            duration: 5000,
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
        />
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
