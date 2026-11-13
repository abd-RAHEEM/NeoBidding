import React from 'react';
import type { AuctionStatus } from '../../api/types';

interface TimelineBarProps {
  startTime: string;
  originalCloseTime: string;
  currentCloseTime: string;
  forcedCloseTime: string;
  triggerWindowMinutes?: number | null;
  status?: AuctionStatus;
  inTriggerWindow: boolean;
  className?: string;
}

export const TimelineBar: React.FC<TimelineBarProps> = ({
  startTime,
  currentCloseTime,
  forcedCloseTime,
  triggerWindowMinutes,
  status,
  inTriggerWindow,
  className = '',
}) => {
  const formatUtcTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toTimeString().substring(0, 5) + ' UTC';
    } catch {
      return iso;
    }
  };

  const isExtended = new Date(currentCloseTime).getTime() > new Date(startTime).getTime();

  return (
    <div className={`bg-surface p-4 rounded border border-hairline shadow-subtle ${className}`}>
      <div className="flex items-center justify-between text-xs font-mono mb-2">
        <div className="flex items-center gap-2">
          <span className="text-muted uppercase tracking-wider font-semibold">
            Auction Timeline & Guardrails
          </span>
          {status && (
            <span className="text-[10px] text-muted font-normal">
              [{status}]
            </span>
          )}
        </div>
        {inTriggerWindow && (
          <span className="text-accent-orange font-bold uppercase tracking-wider animate-pulse flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-orange" />
            Inside {triggerWindowMinutes}m Trigger Window
          </span>
        )}
      </div>

      {/* Progress Track */}
      <div className="relative h-2.5 bg-bg rounded-full overflow-hidden border border-hairline/60 flex">
        <div className="bg-ink/20 h-full w-full relative">
          {inTriggerWindow && (
            <div className="absolute right-0 top-0 bottom-0 bg-accent-orange/40 animate-pulse w-1/3" />
          )}
        </div>
      </div>

      {/* Timeline Markers */}
      <div className="grid grid-cols-3 gap-2 mt-2 text-[11px] font-mono">
        <div>
          <span className="text-muted block text-[10px] uppercase">Bid Start</span>
          <span className="font-semibold text-ink">{formatUtcTime(startTime)}</span>
        </div>

        <div className="text-center">
          <span className="text-muted block text-[10px] uppercase">
            Current Close {isExtended && '(Extended)'}
          </span>
          <span className={`font-semibold ${inTriggerWindow ? 'text-accent-orange' : 'text-ink'}`}>
            {formatUtcTime(currentCloseTime)}
          </span>
        </div>

        <div className="text-right">
          <span className="text-muted block text-[10px] uppercase flex items-center justify-end gap-1">
            <span className="text-accent-brick font-bold">⊘</span> Forced Cap
          </span>
          <span className="font-semibold text-accent-brick">
            {formatUtcTime(forcedCloseTime)}
          </span>
        </div>
      </div>
    </div>
  );
};
