import React, { useState, useEffect, useRef } from 'react';
import type { Supplier, SupplierRanking, Currency as CurrencyType, AuctionStatus } from '../../api/types';
import { submitBid } from '../../api/rfqs';
import { Currency } from '../common/Currency';
import { ApiError } from '../../api/client';

interface BidFormProps {
  rfqId: string;
  currency: CurrencyType;
  status: AuctionStatus;
  invitedSuppliers: Supplier[];
  supplierRankings: SupplierRanking[];
  onBidSubmitted: () => void;
  className?: string;
}

export const BidForm: React.FC<BidFormProps> = ({
  rfqId,
  currency,
  status,
  invitedSuppliers,
  supplierRankings,
  onBidSubmitted,
  className = '',
}) => {
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>('');
  const [freightCharges, setFreightCharges] = useState<string>('');
  const [originCharges, setOriginCharges] = useState<string>('0');
  const [destinationCharges, setDestinationCharges] = useState<string>('0');
  const [transitDays, setTransitDays] = useState<string>('3');
  const [validityDays, setValidityDays] = useState<string>('14');

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Idempotency key per submission attempt; retained on error retry, reset on success
  const idempotencyKeyRef = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    if (invitedSuppliers.length > 0 && !selectedSupplierId) {
      setSelectedSupplierId(invitedSuppliers[0].id);
    }
  }, [invitedSuppliers, selectedSupplierId]);

  // Find selected supplier's ranking & best bid
  const selectedSupplierRanking = supplierRankings.find(
    (r) => r.supplier_id === selectedSupplierId
  );
  const currentBestBid = selectedSupplierRanking?.best_bid;

  // Calculate live total
  const freightNum = parseFloat(freightCharges) || 0;
  const originNum = parseFloat(originCharges) || 0;
  const destNum = parseFloat(destinationCharges) || 0;
  const liveTotal = freightNum + originNum + destNum;

  const currentBestTotal = currentBestBid ? parseFloat(currentBestBid.total_price) : null;
  const isLowerThanBest = currentBestTotal === null || liveTotal < currentBestTotal;

  const isActive = status === 'ACTIVE';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isActive || isSubmitting) return;

    setErrorMsg(null);
    setSuccessMsg(null);

    if (liveTotal <= 0) {
      setErrorMsg('Total quote amount must be greater than zero.');
      return;
    }

    if (currentBestTotal !== null && liveTotal >= currentBestTotal) {
      setErrorMsg(
        `Bid must be strictly lower than your current best quote of ${currency} ${currentBestTotal.toFixed(2)}.`
      );
      return;
    }

    setIsSubmitting(true);

    try {
      await submitBid(
        rfqId,
        {
          supplier_id: selectedSupplierId,
          freight_charges: (freightNum || 0).toFixed(2),
          origin_charges: (originNum || 0).toFixed(2),
          destination_charges: (destNum || 0).toFixed(2),
          transit_time_days: parseInt(transitDays, 10) || 1,
          quote_validity_days: parseInt(validityDays, 10) || 1,
        },
        idempotencyKeyRef.current
      );

      // On success: refresh fresh idempotency key, clear message, notify parent
      idempotencyKeyRef.current = crypto.randomUUID();
      setSuccessMsg(`Quote submitted successfully! Total: ${currency} ${liveTotal.toFixed(2)}`);
      setFreightCharges('');
      onBidSubmitted();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMsg(`[${err.errorCode}] ${err.message}`);
      } else {
        setErrorMsg(err.message || 'An unexpected error occurred while placing quote.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`bg-surface border border-hairline rounded p-5 shadow-subtle ${className}`}>
      <div className="flex items-center justify-between border-b border-hairline pb-3 mb-4">
        <div>
          <h3 className="text-sm font-serif font-bold text-ink tracking-wide uppercase">
            Submit Carrier Quote
          </h3>
          <p className="text-[11px] text-muted">
            Open competitive reverse bidding • Next quote must beat carrier best
          </p>
        </div>
        {!isActive && (
          <span className="text-xs font-mono font-semibold text-accent-brick uppercase px-2 py-0.5 rounded bg-accent-brick/10 border border-accent-brick/20">
            Bidding Inactive
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Supplier Selector */}
        <div>
          <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
            Bidding Carrier
          </label>
          <select
            value={selectedSupplierId}
            onChange={(e) => {
              setSelectedSupplierId(e.target.value);
              setErrorMsg(null);
            }}
            disabled={!isActive || isSubmitting}
            aria-label="Bidding Carrier"
            className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink transition-colors disabled:opacity-50"
          >
            {invitedSuppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.code})
              </option>
            ))}
          </select>

          {/* Supplier's Current Status */}
          <div className="mt-1.5 flex items-center justify-between text-xs font-mono px-2 py-1 bg-bg/50 rounded border border-hairline/60">
            <span className="text-muted">Carrier Current Best:</span>
            {currentBestBid ? (
              <span className="font-semibold text-ink">
                <Currency amount={currentBestBid.total_price} currency={currency} />
                <span className="text-muted ml-1.5 font-normal">
                  (Rank #{selectedSupplierRanking?.rank})
                </span>
              </span>
            ) : (
              <span className="text-muted italic">No quote placed yet</span>
            )}
          </div>
        </div>

        {/* Pricing Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-[11px] font-mono text-muted uppercase mb-1">
              Freight Charges *
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              placeholder="e.g. 5000"
              value={freightCharges}
              onChange={(e) => setFreightCharges(e.target.value)}
              disabled={!isActive || isSubmitting}
              className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink transition-colors disabled:opacity-50 tabular-nums"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-muted uppercase mb-1">
              Origin Charges
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={originCharges}
              onChange={(e) => setOriginCharges(e.target.value)}
              disabled={!isActive || isSubmitting}
              className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink transition-colors disabled:opacity-50 tabular-nums"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-muted uppercase mb-1">
              Destination Charges
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={destinationCharges}
              onChange={(e) => setDestinationCharges(e.target.value)}
              disabled={!isActive || isSubmitting}
              className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink transition-colors disabled:opacity-50 tabular-nums"
            />
          </div>
        </div>

        {/* Transit & Validity */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-mono text-muted uppercase mb-1">
              Transit Time (Days) *
            </label>
            <input
              type="number"
              min="1"
              required
              value={transitDays}
              onChange={(e) => setTransitDays(e.target.value)}
              disabled={!isActive || isSubmitting}
              className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink transition-colors disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-muted uppercase mb-1">
              Quote Validity (Days) *
            </label>
            <input
              type="number"
              min="1"
              required
              value={validityDays}
              onChange={(e) => setValidityDays(e.target.value)}
              disabled={!isActive || isSubmitting}
              className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink transition-colors disabled:opacity-50"
            />
          </div>
        </div>

        {/* Total Price Box */}
        <div className="p-3 bg-bg rounded border border-hairline flex items-center justify-between">
          <div>
            <span className="text-[11px] font-mono text-muted uppercase block">
              Calculated Total Quote Price
            </span>
            <div className="text-lg font-serif font-bold text-ink">
              <Currency amount={liveTotal} currency={currency} />
            </div>
          </div>
          {currentBestTotal !== null && (
            <div className="text-right">
              {isLowerThanBest ? (
                <span className="text-xs font-mono font-semibold text-accent-green">
                  ✓ Valid lower quote
                </span>
              ) : (
                <span className="text-xs font-mono font-semibold text-accent-brick">
                  ✕ Must beat {currency} {currentBestTotal.toFixed(2)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Alerts */}
        {errorMsg && (
          <div className="p-2.5 rounded bg-accent-brick/10 border border-accent-brick/30 text-accent-brick text-xs font-mono">
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="p-2.5 rounded bg-accent-green/10 border border-accent-green/30 text-accent-green text-xs font-mono">
            {successMsg}
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!isActive || isSubmitting || !isLowerThanBest || liveTotal <= 0}
          className="w-full py-2.5 px-4 rounded text-xs font-mono font-bold uppercase tracking-wider text-white bg-accent-green hover:bg-accent-green/90 transition-all disabled:bg-muted/40 disabled:cursor-not-allowed shadow-sm flex items-center justify-center space-x-2"
        >
          {isSubmitting ? (
            <span>Submitting Quote...</span>
          ) : (
            <span>Submit Binding Quote</span>
          )}
        </button>

        <div className="text-[10px] font-mono text-muted text-center">
          Idempotency protection active • Server clock verified
        </div>
      </form>
    </div>
  );
};
