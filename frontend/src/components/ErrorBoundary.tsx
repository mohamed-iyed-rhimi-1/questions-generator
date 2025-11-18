import { ErrorBoundary as ReactErrorBoundary } from 'react-error-boundary';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { ReactNode } from 'react';

interface SectionErrorBoundaryProps {
  children: ReactNode;
  sectionName: string;
  onReset?: () => void;
}

interface ErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
  sectionName: string;
}

function SectionErrorFallback({ error, resetErrorBoundary, sectionName }: ErrorFallbackProps) {
  return (
    <div className="border border-red-200 bg-red-50 rounded-lg p-6">
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-red-900 mb-1">
            Error in {sectionName}
          </h3>
          <p className="text-sm text-red-700 mb-3">
            {error.message || 'An unexpected error occurred in this section.'}
          </p>
          <button
            onClick={resetErrorBoundary}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-red-700 bg-white border border-red-300 rounded-md hover:bg-red-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}

export function SectionErrorBoundary({ children, sectionName, onReset }: SectionErrorBoundaryProps) {
  const handleReset = () => {
    if (onReset) {
      onReset();
    }
  };

  return (
    <ReactErrorBoundary
      FallbackComponent={(props) => (
        <SectionErrorFallback {...props} sectionName={sectionName} />
      )}
      onReset={handleReset}
      onError={(error, errorInfo) => {
        console.error(`Error in ${sectionName}:`, error, errorInfo);
      }}
    >
      {children}
    </ReactErrorBoundary>
  );
}
