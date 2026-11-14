import React from 'react';
import { useCountdown } from '../../hooks/useCountdown';
import type { AuctionStatus } from '../../api/types';

interface CountdownProps {
  targetTime: string;
  startTime?: string;
  status?: AuctionStatus;
  isInTriggerWindow?: boolean;
  className?: string;
  compact?: boolean;
}

export const Countdown: React.FC<CountdownProps> = ({
  targetTime,
  startTime,
  status = 'ACTIVE',
  isInTriggerWindow = false,
  className = '',
  compact = false,
}) => {
  const isScheduled = status === 'SCHEDULED';
  const isFinished = status === 'CLOSED' || status === 'FORCE_CLOSED';

  // If scheduled, countdown to start time; otherwise countdown to close time
  const effectiveTarget = isScheduled ? (startTime || targetTime) : targetTime;
  const { formatted, isUrgent, isExpired } = useCountdown(effectiveTarget);

  if (isFinished) {
    return (
      <span className={`font-mono text-muted text-xs uppercase tracking-wider ${className}`}>
        {status === 'FORCE_CLOSED' ? 'Forced Closed' : 'Auction Concluded'}
      </span>
    );
  }

  if (isScheduled) {
    return (
      <span className={`inline-flex items-center gap-1.5 font-mono text-xs text-muted ${className}`}>
        <span>Opens in:</span>
        <span className="font-semibold text-ink tabular-nums">{formatted}</span>
      </span>
    );
  }

  if (compact) {
    return (
      <span
        className={`font-mono tabular-nums font-semibold ${
          isInTriggerWindow || isUrgent
            ? 'text-accent-orange animate-pulse'
            : 'text-ink'
        } ${className}`}
      >
        {isExpired ? 'Closing...' : formatted}
      </span>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      {isInTriggerWindow && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-accent-orange/15 text-accent-orange border border-accent-orange/30 animate-pulse">
          Trigger Window
        </span>
      )}
      <div
        className={`font-mono tabular-nums font-bold tracking-tight px-2.5 py-1 rounded border ${
          isInTriggerWindow || isUrgent
            ? 'bg-accent-orange/10 border-accent-orange/30 text-accent-orange shadow-sm'
            : 'bg-surface border-hairline text-ink'
        }`}
      >
        {isExpired ? 'Closing...' : formatted}
      </div>
    </div>
  );
};

