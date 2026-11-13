import React from 'react';
import type { RfqStats, Currency as CurrencyType } from '../../api/types';
import { Currency } from './Currency';

interface StatsStripProps {
  stats: RfqStats;
  currency: CurrencyType;
  className?: string;
}

export const StatsStrip: React.FC<StatsStripProps> = ({
  stats,
  currency,
  className = '',
}) => {
  return (
    <div className={`grid grid-cols-2 md:grid-cols-4 gap-3 ${className}`}>
      {/* Metric 1: Total Bids */}
      <div className="bg-surface p-3.5 rounded border border-hairline shadow-subtle">
        <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
          Total Bids
        </span>
        <div className="mt-1 flex items-baseline space-x-1.5">
          <span className="text-2xl font-serif font-bold text-ink tabular-nums">
            {stats.total_bids}
          </span>
          <span className="text-xs text-muted font-mono">quotes</span>
        </div>
      </div>

      {/* Metric 2: Participating Suppliers */}
      <div className="bg-surface p-3.5 rounded border border-hairline shadow-subtle">
        <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
          Carriers Active
        </span>
        <div className="mt-1 flex items-baseline space-x-1.5">
          <span className="text-2xl font-serif font-bold text-ink tabular-nums">
            {stats.participating_suppliers}
          </span>
          <span className="text-xs text-muted font-mono">
            / {stats.total_invited_suppliers} invited
          </span>
        </div>
      </div>

      {/* Metric 3: Extensions Triggered */}
      <div className="bg-surface p-3.5 rounded border border-hairline shadow-subtle">
        <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
          Extensions
        </span>
        <div className="mt-1 flex items-baseline space-x-1.5">
          <span className="text-2xl font-serif font-bold text-ink tabular-nums">
            {stats.extension_count}
          </span>
          <span className="text-xs text-muted font-mono">
            {stats.extension_count === 1 ? 'time added' : 'times added'}
          </span>
        </div>
      </div>

      {/* Metric 4: Price Improvement */}
      <div className="bg-surface p-3.5 rounded border border-hairline shadow-subtle">
        <span className="text-[11px] font-mono text-muted uppercase tracking-wider block">
          Price Improvement
        </span>
        <div className="mt-1">
          {stats.price_improvement_pct && parseFloat(stats.price_improvement_pct) > 0 ? (
            <div className="flex items-baseline space-x-1.5">
              <span className="text-2xl font-serif font-bold text-accent-green tabular-nums">
                -{stats.price_improvement_pct}%
              </span>
              <span className="text-xs text-accent-green font-mono">
                (<Currency amount={stats.price_improvement} currency={currency} /> saved)
              </span>
            </div>
          ) : (
            <div className="flex items-baseline space-x-1">
              <span className="text-lg font-mono text-muted">—</span>
              <span className="text-xs text-muted font-mono">no drop yet</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
