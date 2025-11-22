import { useEffect, useRef } from 'react'
import { X, AlertTriangle, Info, AlertCircle, Loader2 } from 'lucide-react'

export interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'warning' | 'info'
  onConfirm: () => void
  onCancel: () => void
  isLoading?: boolean
}

/**
 * Confirmation dialog component with modal overlay
 * Features:
 * - Modal overlay with backdrop
 * - Customizable title, message, and buttons
 * - Variant styles (danger, warning, info)
 * - Loading state with spinner on confirm button
 * - Disabled buttons during loading
 * - Keyboard support (Escape, Enter)
 * - Focus trap for accessibility
 */
export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
  isLoading = false,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const cancelButtonRef = useRef<HTMLButtonElement>(null)

  // Handle keyboard events
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading) {
        onCancel()
      } else if (e.key === 'Enter' && !isLoading) {
        onConfirm()
      } else if (e.key === 'Tab') {
        // Focus trap implementation
        e.preventDefault()
        const focusableElements = dialogRef.current?.querySelectorAll(
          'button:not(:disabled)'
        )
        if (!focusableElements || focusableElements.length === 0) return

        const firstElement = focusableElements[0] as HTMLElement
        const lastElement = focusableElements[
          focusableElements.length - 1
        ] as HTMLElement

        if (e.shiftKey) {
          // Shift + Tab
          if (document.activeElement === firstElement) {
            lastElement.focus()
          } else {
            const currentIndex = Array.from(focusableElements).indexOf(
              document.activeElement as HTMLElement
            )
            if (currentIndex > 0) {
              (focusableElements[currentIndex - 1] as HTMLElement).focus()
            }
          }
        } else {
          // Tab
          if (document.activeElement === lastElement) {
            firstElement.focus()
          } else {
            const currentIndex = Array.from(focusableElements).indexOf(
              document.activeElement as HTMLElement
            )
            if (currentIndex < focusableElements.length - 1) {
              (focusableElements[currentIndex + 1] as HTMLElement).focus()
            }
          }
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isLoading, onCancel, onConfirm])

  // Focus management - focus confirm button when dialog opens
  useEffect(() => {
    if (isOpen && confirmButtonRef.current) {
      confirmButtonRef.current.focus()
    }
  }, [isOpen])

  // Prevent body scroll when dialog is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  if (!isOpen) return null

  // Get variant-specific styles
  const getVariantIcon = () => {
    switch (variant) {
      case 'danger':
        return <AlertCircle className="w-6 h-6 text-red-600" />
      case 'warning':
        return <AlertTriangle className="w-6 h-6 text-yellow-600" />
      case 'info':
        return <Info className="w-6 h-6 text-blue-600" />
    }
  }

  const getVariantStyles = () => {
    switch (variant) {
      case 'danger':
        return {
          iconBg: 'bg-red-100',
          confirmBtn: 'btn-danger',
        }
      case 'warning':
        return {
          iconBg: 'bg-yellow-100',
          confirmBtn: 'bg-yellow-600 text-white hover:bg-yellow-700 active:bg-yellow-800 focus-visible:ring-yellow-500',
        }
      case 'info':
        return {
          iconBg: 'bg-blue-100',
          confirmBtn: 'btn-primary',
        }
    }
  }

  const variantStyles = getVariantStyles()

  return (
    <div
      className="confirm-dialog-backdrop"
      onClick={!isLoading ? onCancel : undefined}
      role="presentation"
      aria-hidden="true"
    >
      <div
        ref={dialogRef}
        className="confirm-dialog responsive-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        aria-describedby="dialog-description"
        aria-live="polite"
      >
        {/* Close button */}
        <button
          type="button"
          className="confirm-dialog-close"
          onClick={onCancel}
          disabled={isLoading}
          aria-label={`Close ${title} dialog`}
          title="Close dialog (Escape)"
        >
          <X className="w-5 h-5" aria-hidden="true" />
        </button>

        {/* Icon */}
        <div className={`confirm-dialog-icon ${variantStyles.iconBg}`}>
          {getVariantIcon()}
        </div>

        {/* Content */}
        <div className="confirm-dialog-content">
          <h3 id="dialog-title" className="confirm-dialog-title">
            {title}
          </h3>
          <p id="dialog-description" className="confirm-dialog-message">
            {message}
          </p>
        </div>

        {/* Actions */}
        <div className="confirm-dialog-actions mobile-button-group">
          <button
            ref={cancelButtonRef}
            type="button"
            className="btn btn-outline btn-touch flex-1"
            onClick={onCancel}
            disabled={isLoading}
            aria-label={`${cancelLabel} (Escape)`}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmButtonRef}
            type="button"
            className={`btn btn-touch ${variantStyles.confirmBtn} flex-1 inline-flex items-center justify-center gap-2`}
            onClick={onConfirm}
            disabled={isLoading}
            aria-label={`${confirmLabel} (Enter)`}
            aria-busy={isLoading}
          >
            {isLoading && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
            <span>{confirmLabel}</span>
          </button>
        </div>
      </div>
    </div>
  )
}
