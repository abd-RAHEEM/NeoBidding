import React from 'react';
import type { AuctionEvent } from '../../api/types';

interface ActivityLogProps {
  events: AuctionEvent[];
  className?: string;
}

export const ActivityLog: React.FC<ActivityLogProps> = ({
  events,
  className = '',
}) => {
  const formatUtc = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toISOString().replace('T', ' ').substring(11, 19) + ' UTC';
    } catch {
      return iso;
    }
  };

  const getEventBadge = (type: string) => {
    switch (type) {
      case 'TIME_EXTENDED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-accent-orange/15 text-accent-orange border border-accent-orange/30">
            ⏱ Time Extended
          </span>
        );
      case 'BID_SUBMITTED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-accent-green/10 text-accent-green border border-accent-green/20">
            Bid Placed
          </span>
        );
      case 'AUCTION_STARTED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-accent-green/10 text-accent-green border border-accent-green/20">
            Auction Started
          </span>
        );
      case 'AUCTION_FORCE_CLOSED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-accent-brick/15 text-accent-brick border border-accent-brick/30">
            Forced Closed
          </span>
        );
      case 'AUCTION_CLOSED':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-ink/5 text-muted border border-hairline">
            Auction Closed
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase bg-bg text-muted border border-hairline">
            {type}
          </span>
        );
    }
  };

  return (
    <div className={`bg-surface border border-hairline rounded p-4 shadow-subtle ${className}`}>
      <div className="flex items-center justify-between mb-3 border-b border-hairline pb-2">
        <h4 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
          Audit Trail & Activity Log
        </h4>
        <span className="text-[11px] font-mono text-muted">
          {events.length} {events.length === 1 ? 'event' : 'events'} recorded
        </span>
      </div>

      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <p className="text-xs font-mono text-muted text-center py-4">No events logged yet.</p>
        ) : (
          events.map((evt) => {
            const isExtension = evt.event_type === 'TIME_EXTENDED';
            const reason = evt.payload?.reason || evt.payload?.trigger_type;
            const newClose = evt.payload?.new_close_time;

            return (
              <div
                key={evt.id}
                className={`p-2.5 rounded border text-xs font-mono transition-colors ${
                  isExtension
                    ? 'bg-accent-orange/[0.04] border-accent-orange/30'
                    : 'bg-bg/40 border-hairline/60'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    {getEventBadge(evt.event_type)}
                    <span className="text-muted text-[11px]">{formatUtc(evt.occurred_at)}</span>
                  </div>
                  {isExtension && newClose && (
                    <span className="text-[10px] text-accent-orange font-bold">
                      → Extended to {new Date(newClose).toTimeString().substring(0, 5)} UTC
                    </span>
                  )}
                </div>

                {/* Event Description */}
                {isExtension ? (
                  <div className="mt-1 text-[11px] text-ink font-sans bg-accent-orange/10 p-2 rounded border border-accent-orange/20">
                    <strong className="font-semibold text-accent-orange font-mono">Trigger Fired: </strong>
                    <span>{reason || 'Bidding activity inside the trigger window.'}</span>
                  </div>
                ) : evt.event_type === 'BID_SUBMITTED' ? (
                  <div className="text-muted text-[11px]">
                    Quote from <strong className="text-ink">{evt.payload?.carrier_name || 'Carrier'}</strong>:{' '}
                    Total <strong className="text-ink">{evt.payload?.currency} {evt.payload?.total_price}</strong>
                  </div>
                ) : (
                  <div className="text-muted text-[11px]">
                    {evt.event_type === 'RFQ_CREATED' && `RFQ configured and issued with ${evt.payload?.mode || 'STANDARD'} rules.`}
                    {evt.event_type === 'AUCTION_STARTED' && 'Start time reached. Bidding is now open.'}
                    {evt.event_type === 'AUCTION_CLOSED' && 'Auction closed at scheduled close time.'}
                    {evt.event_type === 'AUCTION_FORCE_CLOSED' && 'Hard forced close time reached. Auction ended.'}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
