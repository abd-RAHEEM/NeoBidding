import React from 'react';
import { Link } from 'react-router-dom';
import type { RfqSummary } from '../../api/types';
import { Badge } from '../common/Badge';
import { Countdown } from '../common/Countdown';
import { Currency } from '../common/Currency';

interface RfqCardProps {
  rfq: RfqSummary;
}

export const RfqCard: React.FC<RfqCardProps> = ({ rfq }) => {
  const auctionType = rfq.auction_type || rfq.mode;
  const isBritish = auctionType === 'BRITISH';
  const formatUtc = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toTimeString().substring(0, 5) + ' UTC';
    } catch {
      return iso;
    }
  };

  return (
    <Link
      to={`/rfqs/${rfq.id}`}
      className="block bg-surface border border-hairline rounded p-4 shadow-subtle hover:border-ink/40 transition-all hover:shadow-card group"
    >
      {/* Top Header */}
      <div className="flex items-start justify-between gap-3 mb-2.5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs font-semibold text-muted">
              {rfq.reference_id}
            </span>
            <Badge status={rfq.status} />
            <Badge mode={auctionType} />
          </div>
          <h3 className="font-serif text-lg font-bold text-ink group-hover:text-accent-orange transition-colors">
            {rfq.name}
          </h3>
        </div>

        {/* Live Countdown */}
        <div className="text-right">
          <Countdown
            targetTime={rfq.current_close_time}
            startTime={rfq.bid_start_time}
            status={rfq.status}
          />
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-3 border-y border-hairline my-3 bg-bg/30 px-3 rounded text-xs font-mono">
        <div>
          <span className="text-[10px] text-muted uppercase block">Current Lowest Bid</span>
          <div className="font-bold text-sm text-ink mt-0.5">
            {rfq.current_lowest_bid ? (
              <span className="text-accent-green">
                <Currency amount={rfq.current_lowest_bid} currency={rfq.currency} />
              </span>
            ) : (
              <span className="text-muted italic text-xs">No quotes placed</span>
            )}
          </div>
        </div>

        <div>
          <span className="text-[10px] text-muted uppercase block">Current Close</span>
          <div className="font-semibold text-ink mt-0.5">
            {formatUtc(rfq.current_close_time)}
          </div>
        </div>

        <div>
          <span className="text-[10px] text-muted uppercase block">Forced Close Cap</span>
          <div className="font-semibold text-accent-brick mt-0.5">
            {formatUtc(rfq.forced_close_time)}
          </div>
        </div>

        <div>
          <span className="text-[10px] text-muted uppercase block">Bids / Extensions</span>
          <div className="font-semibold text-ink mt-0.5">
            <span>{rfq.bids_count} bids</span>
            {isBritish && (
              <span className="text-accent-orange ml-1">
                ({rfq.extension_count} ext)
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Footer Details */}
      <div className="flex items-center justify-between text-[11px] font-mono text-muted pt-1">
        <span>
          Start: {formatUtc(rfq.bid_start_time)}
        </span>
        <span className="group-hover:text-ink font-semibold flex items-center gap-1 transition-colors">
          View Ledger & Quotes →
        </span>
      </div>
    </Link>
  );
};
