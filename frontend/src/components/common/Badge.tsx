import React from 'react';
import type { AuctionStatus, AuctionMode } from '../../api/types';

interface BadgeProps {
  children?: React.ReactNode;
  variant?: 'status' | 'mode' | 'l1' | 'tag' | 'warning';
  status?: AuctionStatus;
  mode?: AuctionMode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'tag',
  status,
  mode,
  className = '',
}) => {
  if (status) {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold uppercase tracking-wider bg-accent-green/10 text-accent-green border border-accent-green/20 ${className}`}>
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green mr-1.5 animate-pulse" />
            Active
          </span>
        );
      case 'SCHEDULED':
        return (
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium uppercase tracking-wider bg-accent-slate/10 text-accent-slate border border-accent-slate/20 ${className}`}>
            Scheduled
          </span>
        );
      case 'CLOSED':
        return (
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium uppercase tracking-wider bg-ink/5 text-muted border border-hairline ${className}`}>
            Closed
          </span>
        );
      case 'FORCE_CLOSED':
        return (
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold uppercase tracking-wider bg-accent-brick/10 text-accent-brick border border-accent-brick/20 ${className}`}>
            Forced Close
          </span>
        );
    }
  }

  if (mode) {
    return mode === 'BRITISH' ? (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-accent-orange/10 text-accent-orange border border-accent-orange/20 ${className}`}>
        British
      </span>
    ) : (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-muted/10 text-muted border border-hairline ${className}`}>
        Standard
      </span>
    );
  }

  if (variant === 'l1') {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-bold bg-accent-green text-white shadow-sm ${className}`}>
        L1 LEADER
      </span>
    );
  }

  if (variant === 'warning') {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold bg-accent-amber/15 text-accent-amber border border-accent-amber/30 ${className}`}>
        {children}
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono text-muted bg-surface border border-hairline ${className}`}>
      {children}
    </span>
  );
};

