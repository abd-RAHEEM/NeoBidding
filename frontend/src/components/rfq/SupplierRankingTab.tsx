import React from 'react';
import type { SupplierRanking, Currency as CurrencyType } from '../../api/types';
import { Currency } from '../common/Currency';
import { Badge } from '../common/Badge';

interface SupplierRankingTabProps {
  rankings: SupplierRanking[];
  currency: CurrencyType;
}

export const SupplierRankingTab: React.FC<SupplierRankingTabProps> = ({
  rankings,
  currency,
}) => {
  return (
    <div className="overflow-x-auto border border-hairline rounded bg-surface shadow-subtle">
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-hairline bg-bg/60 font-mono text-muted uppercase tracking-wider">
            <th className="py-2.5 px-3 w-16">Rank</th>
            <th className="py-2.5 px-4">Carrier / Supplier</th>
            <th className="py-2.5 px-4 text-right">Total Price</th>
            <th className="py-2.5 px-3 text-right">Freight</th>
            <th className="py-2.5 px-3 text-right">Origin</th>
            <th className="py-2.5 px-3 text-right">Destination</th>
            <th className="py-2.5 px-3 text-center">Transit</th>
            <th className="py-2.5 px-3 text-center">Validity</th>
            <th className="py-2.5 px-4 text-right">Best Quote Time</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline">
          {(rankings || []).map((row: any) => {
            const hasBid = !row.no_bid && (row.total_price !== null && row.total_price !== undefined || row.best_bid);
            if (!hasBid) {
              return (
                <tr key={row.supplier_id} className="opacity-50 hover:opacity-75 transition-opacity bg-bg/20">
                  <td className="py-3 px-3 font-mono text-muted text-center">—</td>
                  <td className="py-3 px-4">
                    <div className="font-medium text-muted">{row.supplier_name || row.carrier_name}</div>
                    <div className="text-[10px] font-mono text-muted/80">{row.supplier_code || ''}</div>
                  </td>
                  <td className="py-3 px-4 text-right font-mono italic text-muted" colSpan={7}>
                    No bid submitted yet (Invited)
                  </td>
                </tr>
              );
            }

            const bid = row.best_bid || row;
            const isL1 = row.rank === 1 || row.is_l1;

            return (
              <tr
                key={row.supplier_id}
                className={`hover:bg-bg/40 transition-colors ${
                  isL1 ? 'bg-accent-green/[0.04]' : ''
                }`}
              >
                <td className="py-3 px-3 font-mono font-bold">
                  {isL1 ? (
                    <Badge variant="l1" className="text-[10px]">
                      L1
                    </Badge>
                  ) : (
                    <span className="text-muted pl-1.5">#{row.rank}</span>
                  )}
                </td>
                <td className="py-3 px-4">
                  <div className="font-semibold text-ink flex items-center gap-1.5">
                    {row.supplier_name}
                    {isL1 && (
                      <span className="text-accent-green text-[10px] font-mono font-bold">
                        ★ LOWEST
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] font-mono text-muted">{row.supplier_code}</div>
                </td>
                <td className="py-3 px-4 text-right font-mono font-bold text-sm">
                  <span className={isL1 ? 'text-accent-green' : 'text-ink'}>
                    <Currency amount={bid.total_price} currency={currency} />
                  </span>
                </td>
                <td className="py-3 px-3 text-right">
                  <Currency amount={bid.freight_charges} currency={currency} />
                </td>
                <td className="py-3 px-3 text-right">
                  <Currency amount={bid.origin_charges} currency={currency} />
                </td>
                <td className="py-3 px-3 text-right">
                  <Currency amount={bid.destination_charges} currency={currency} />
                </td>
                <td className="py-3 px-3 text-center font-mono">
                  {bid.transit_time_days}d
                </td>
                <td className="py-3 px-3 text-center font-mono">
                  {bid.quote_validity_days}d
                </td>
                <td className="py-3 px-4 text-right font-mono text-[11px] text-muted">
                  {new Date(bid.submitted_at).toTimeString().substring(0, 8)} UTC
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

