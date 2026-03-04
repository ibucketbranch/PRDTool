"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * Error severity levels
 */
export type ErrorSeverity = "error" | "warning" | "info";

/**
 * Props for the ErrorDisplay component
 */
export interface ErrorDisplayProps {
  /** The error message to display */
  message: string;
  /** Optional title for the error */
  title?: string;
  /** Severity level affects styling */
  severity?: ErrorSeverity;
  /** Callback for retry action */
  onRetry?: () => void;
  /** Custom retry button text */
  retryText?: string;
  /** Whether retry is currently in progress */
  isRetrying?: boolean;
  /** Link to navigate to (alternative to retry) */
  linkTo?: string;
  /** Link text */
  linkText?: string;
  /** Additional className */
  className?: string;
  /** Whether to show full page styling */
  fullPage?: boolean;
}

const severityStyles: Record<ErrorSeverity, { bg: string; border: string; text: string; link: string }> = {
  error: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    link: "text-red-600 hover:text-red-800",
  },
  warning: {
    bg: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-700",
    link: "text-amber-600 hover:text-amber-800",
  },
  info: {
    bg: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-700",
    link: "text-blue-600 hover:text-blue-800",
  },
};

/**
 * Consistent error display component with retry functionality
 */
export function ErrorDisplay({
  message,
  title,
  severity = "error",
  onRetry,
  retryText = "Try again",
  isRetrying = false,
  linkTo,
  linkText = "Return to dashboard",
  className,
  fullPage = false,
}: ErrorDisplayProps) {
  const styles = severityStyles[severity];

  const content = (
    <div
      className={cn(
        "p-4 rounded-lg border",
        styles.bg,
        styles.border,
        className
      )}
    >
      {title && (
        <h3 className={cn("font-semibold mb-1", styles.text)}>{title}</h3>
      )}
      <p className={styles.text}>
        {severity === "error" ? "Error: " : ""}
        {message}
      </p>
      <div className="mt-3 flex items-center gap-4">
        {onRetry && (
          <button
            onClick={onRetry}
            disabled={isRetrying}
            className={cn(
              "text-sm underline hover:no-underline transition-colors",
              styles.link,
              isRetrying && "opacity-50 cursor-not-allowed"
            )}
          >
            {isRetrying ? "Retrying..." : retryText}
          </button>
        )}
        {linkTo && (
          <Link
            href={linkTo}
            className={cn("text-sm underline hover:no-underline", styles.link)}
          >
            {linkText}
          </Link>
        )}
      </div>
    </div>
  );

  if (fullPage) {
    return (
      <main className="container mx-auto px-4 py-8">
        {content}
      </main>
    );
  }

  return content;
}

/**
 * Inline error message for form fields or small areas
 */
interface InlineErrorProps {
  message: string;
  className?: string;
}

export function InlineError({ message, className }: InlineErrorProps) {
  return (
    <p className={cn("text-sm text-red-600", className)}>
      {message}
    </p>
  );
}

/**
 * Network error with automatic retry suggestion
 */
interface NetworkErrorProps {
  onRetry?: () => void;
  isRetrying?: boolean;
  className?: string;
}

export function NetworkError({ onRetry, isRetrying = false, className }: NetworkErrorProps) {
  return (
    <ErrorDisplay
      title="Connection Error"
      message="Unable to connect to the server. Please check your internet connection and try again."
      severity="error"
      onRetry={onRetry}
      isRetrying={isRetrying}
      className={className}
    />
  );
}

/**
 * Not found error display
 */
interface NotFoundErrorProps {
  resource?: string;
  linkTo?: string;
  className?: string;
}

export function NotFoundError({
  resource = "Resource",
  linkTo = "/",
  className,
}: NotFoundErrorProps) {
  return (
    <ErrorDisplay
      title="Not Found"
      message={`${resource} could not be found.`}
      severity="warning"
      linkTo={linkTo}
      linkText="Return to dashboard"
      className={className}
    />
  );
}

/**
 * Empty state component (not an error, but related UX)
 */
interface EmptyStateProps {
  title?: string;
  message: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  message,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 text-center",
        className
      )}
    >
      {icon && <div className="mb-4 text-neutral-400">{icon}</div>}
      {title && (
        <h3 className="text-lg font-medium text-neutral-700 mb-2">{title}</h3>
      )}
      <p className="text-neutral-500 max-w-md">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/**
 * Alert banner for important messages
 */
interface AlertBannerProps {
  message: string;
  severity?: ErrorSeverity;
  onDismiss?: () => void;
  className?: string;
}

export function AlertBanner({
  message,
  severity = "info",
  onDismiss,
  className,
}: AlertBannerProps) {
  const styles = severityStyles[severity];

  return (
    <div
      className={cn(
        "p-3 rounded-lg border flex items-center justify-between",
        styles.bg,
        styles.border,
        className
      )}
    >
      <p className={cn("text-sm", styles.text)}>{message}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className={cn("text-sm ml-4 hover:opacity-70", styles.text)}
          aria-label="Dismiss"
        >
          &times;
        </button>
      )}
    </div>
  );
}
