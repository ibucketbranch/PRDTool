"use client";

import { cn } from "@/lib/utils";
import { HelpTooltip } from "./Tooltip";

interface StatCardProps {
  title: string;
  value: number | string;
  description?: string;
  className?: string;
  /** Optional help text shown in a tooltip next to the title */
  helpText?: string;
}

export function StatCard({ title, value, description, className, helpText }: StatCardProps) {
  return (
    <div
      className={cn(
        "p-6 bg-neutral-50 rounded-lg border border-neutral-200",
        className
      )}
    >
      <div className="flex items-center gap-1">
        <h3 className="text-sm font-medium text-neutral-600 uppercase tracking-wide">
          {title}
        </h3>
        {helpText && <HelpTooltip text={helpText} size={14} />}
      </div>
      <p className="mt-2 text-3xl font-bold text-neutral-800">{value}</p>
      {description && (
        <p className="mt-1 text-sm text-neutral-500">{description}</p>
      )}
    </div>
  );
}
