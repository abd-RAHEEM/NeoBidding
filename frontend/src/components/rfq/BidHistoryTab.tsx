import React, { useState } from 'react';
import type { Bid, Currency as CurrencyType } from '../../api/types';
import { Currency } from '../common/Currency';

interface BidHistoryTabProps {
  bids: Bid[];
  currency: CurrencyType;
}

export const BidHistoryTab: React.FC<BidHistoryTabProps> = ({
  bids = [],
  currency,
}) => {
  const [sortBy, setSortBy] = useState<'PRICE' | 'TIME'>('TIME');

  const safeBids = Array.isArray(bids) ? bids : [];
  const sortedBids = [...safeBids].sort((a, b) => {
    if (sortBy === 'PRICE') {
      return parseFloat(a.total_price) - parseFloat(b.total_price);
    } else {
      return new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime();
    }
  });

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center justify-between text-xs">
        <span className="font-mono text-muted">
          Showing <strong className="text-ink font-semibold">{bids.length}</strong> submitted quotes
        </span>
        <div className="flex items-center space-x-1 bg-surface border border-hairline p-0.5 rounded">
          <button
            type="button"
            onClick={() => setSortBy('TIME')}
            className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
              sortBy === 'TIME'
                ? 'bg-ink text-surface font-semibold shadow-sm'
                : 'text-muted hover:text-ink'
            }`}
          >
            Sort by Time (Newest)
          </button>
          <button
            type="button"
            onClick={() => setSortBy('PRICE')}
            className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
              sortBy === 'PRICE'
                ? 'bg-ink text-surface font-semibold shadow-sm'
                : 'text-muted hover:text-ink'
            }`}
          >
            Sort by Price (Lowest)
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-hairline rounded bg-surface shadow-subtle">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-hairline bg-bg/60 font-mono text-muted uppercase tracking-wider">
              <th className="py-2.5 px-3 w-12">#</th>
              <th className="py-2.5 px-4">Carrier Name</th>
              <th className="py-2.5 px-4 text-right">Total Price</th>
              <th className="py-2.5 px-3 text-right">Freight</th>
              <th className="py-2.5 px-3 text-right">Origin</th>
              <th className="py-2.5 px-3 text-right">Destination</th>
              <th className="py-2.5 px-3 text-center">Transit</th>
              <th className="py-2.5 px-3 text-center">Validity</th>
              <th className="py-2.5 px-4 text-right">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {sortedBids.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-8 text-center font-mono text-muted">
                  No bids have been submitted yet.
                </td>
              </tr>
            ) : (
              sortedBids.map((bid, index) => (
                <tr key={bid.id} className="hover:bg-bg/40 transition-colors">
                  <td className="py-2.5 px-3 font-mono text-muted">{index + 1}</td>
                  <td className="py-2.5 px-4 font-semibold text-ink">{bid.carrier_name}</td>
                  <td className="py-2.5 px-4 text-right font-mono font-bold text-ink">
                    <Currency amount={bid.total_price} currency={currency} />
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <Currency amount={bid.freight_charges} currency={currency} />
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <Currency amount={bid.origin_charges} currency={currency} />
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <Currency amount={bid.destination_charges} currency={currency} />
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono">{bid.transit_time_days}d</td>
                  <td className="py-2.5 px-3 text-center font-mono">{bid.quote_validity_days}d</td>
                  <td className="py-2.5 px-4 text-right font-mono text-muted">
                    {new Date(bid.submitted_at).toISOString().replace('T', ' ').substring(0, 19)} UTC
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

