import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchSuppliers, createRfq } from '../api/rfqs';
import type { Currency, ExtensionTrigger, AuctionMode } from '../api/types';
import { ApiError } from '../api/client';

export const CreateRfqPage: React.FC = () => {
  const navigate = useNavigate();

  // Helper to get local ISO string for datetime-local inputs
  const toLocalIso = (date: Date) => {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
      date.getHours()
    )}:${pad(date.getMinutes())}`;
  };

  const now = new Date();
  const defaultStart = new Date(now.getTime() + 60 * 1000); // 1 min from now
  const defaultClose = new Date(now.getTime() + 20 * 60 * 1000); // 20 mins from now
  const defaultForcedClose = new Date(now.getTime() + 60 * 60 * 1000); // 60 mins from now
  const defaultPickup = new Date(now.getTime() + 48 * 60 * 60 * 1000).toISOString().substring(0, 10);

  // Form states
  const [name, setName] = useState('Mumbai-Delhi Express Freight');
  const [referenceId, setReferenceId] = useState(
    `RFQ-${new Date().toISOString().substring(0, 10).replace(/-/g, '')}-${Math.floor(1000 + Math.random() * 9000)}`
  );
  const [currency, setCurrency] = useState<Currency>('INR');
  const [pickupDate, setPickupDate] = useState(defaultPickup);
  const [bidStartTime, setBidStartTime] = useState(toLocalIso(defaultStart));
  const [bidCloseTime, setBidCloseTime] = useState(toLocalIso(defaultClose));
  const [forcedCloseTime, setForcedCloseTime] = useState(toLocalIso(defaultForcedClose));

  // British Toggle & Config
  const [isBritish, setIsBritish] = useState(true);
  const [triggerWindowX, setTriggerWindowX] = useState<number>(5);
  const [extensionDurationY, setExtensionDurationY] = useState<number>(5);
  const [extensionTrigger, setExtensionTrigger] = useState<ExtensionTrigger>('L1_CHANGE_IN_LAST_X');

  // Suppliers selection
  const [selectedSupplierIds, setSelectedSupplierIds] = useState<string[]>([]);
  const [supplierSearch, setSupplierSearch] = useState('');

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { data: suppliers = [], isLoading: isLoadingSuppliers } = useQuery({
    queryKey: ['suppliers'],
    queryFn: fetchSuppliers,
  });

  const filteredSuppliers = suppliers.filter(
    (s) =>
      s.name.toLowerCase().includes(supplierSearch.toLowerCase()) ||
      s.code.toLowerCase().includes(supplierSearch.toLowerCase())
  );

  const handleSelectAll = () => {
    setSelectedSupplierIds(suppliers.map((s) => s.id));
  };

  const handleClearAll = () => {
    setSelectedSupplierIds([]);
  };

  const toggleSupplier = (id: string) => {
    setSelectedSupplierIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const generateNewReferenceId = () => {
    setReferenceId(
      `RFQ-${new Date().toISOString().substring(0, 10).replace(/-/g, '')}-${Math.floor(1000 + Math.random() * 9000)}`
    );
  };

  // Plain-English explanation generator
  const getExplanation = () => {
    if (!isBritish) {
      return 'Standard Auction: Fixed close time. Bidding closes exactly at the scheduled bid close time with no extensions.';
    }

    let triggerText = '';
    switch (extensionTrigger) {
      case 'BID_IN_LAST_X':
        triggerText = 'any new valid bid is placed';
        break;
      case 'ANY_RANK_CHANGE_IN_LAST_X':
        triggerText = 'any change in supplier rank occurs';
        break;
      case 'L1_CHANGE_IN_LAST_X':
        triggerText = 'the lowest bidder (L1) changes';
        break;
    }

    return `British Anti-Sniping Rule: If ${triggerText} during the final ${triggerWindowX} minutes before close, the auction close time automatically extends by ${extensionDurationY} minutes, strictly capped at the forced close time.`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    // Validation
    const startMs = new Date(bidStartTime).getTime();
    const closeMs = new Date(bidCloseTime).getTime();
    const forcedMs = new Date(forcedCloseTime).getTime();

    if (closeMs <= startMs) {
      setErrorMsg('Bid Close Time must be strictly later than Bid Start Time.');
      return;
    }
    if (forcedMs <= closeMs) {
      setErrorMsg('Forced Close Time must be strictly later than Bid Close Time.');
      return;
    }
    if (selectedSupplierIds.length === 0) {
      setErrorMsg('At least one supplier must be invited to the auction.');
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = {
        name,
        reference_id: referenceId,
        currency,
        pickup_date: pickupDate,
        bid_start_time: new Date(bidStartTime).toISOString(),
        bid_close_time: new Date(bidCloseTime).toISOString(),
        forced_close_time: new Date(forcedCloseTime).toISOString(),
        auction_type: (isBritish ? 'BRITISH' : 'STANDARD') as AuctionMode,
        mode: (isBritish ? 'BRITISH' : 'STANDARD') as AuctionMode,
        supplier_ids: selectedSupplierIds,
        ...(isBritish && {
          british_config: {
            trigger_window_minutes: triggerWindowX,
            extension_duration_minutes: extensionDurationY,
            extension_trigger: extensionTrigger,
          },
        }),
      };

      const result = await createRfq(payload);
      navigate(`/rfqs/${result.id}`);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMsg(`[${err.errorCode}] ${err.message}`);
      } else {
        setErrorMsg(err.message || 'Failed to create RFQ.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-serif font-bold text-ink tracking-tight">
          Configure New RFQ Auction
        </h1>
        <p className="text-sm text-muted mt-1">
          Set up carrier invitation, service parameters, and British anti-sniping extension rules.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: General Info */}
        <div className="bg-surface border border-hairline rounded p-5 shadow-subtle space-y-4">
          <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider border-b border-hairline pb-2">
            1. RFQ Specification & Route
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                RFQ Name *
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-mono font-semibold text-ink uppercase">
                  Reference ID *
                </label>
                <button
                  type="button"
                  onClick={generateNewReferenceId}
                  className="text-[10px] font-mono text-accent-orange hover:underline"
                >
                  Regenerate
                </button>
              </div>
              <input
                type="text"
                required
                value={referenceId}
                onChange={(e) => setReferenceId(e.target.value)}
                className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink font-mono font-semibold"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                Settlement Currency *
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value as Currency)}
                className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
              >
                <option value="INR">INR (₹ - Indian Rupee)</option>
                <option value="USD">USD ($ - US Dollar)</option>
                <option value="EUR">EUR (€ - Euro)</option>
                <option value="GBP">GBP (£ - British Pound)</option>
                <option value="AED">AED (AED - UAE Dirham)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                Pickup / Service Date *
              </label>
              <input
                type="date"
                required
                value={pickupDate}
                onChange={(e) => setPickupDate(e.target.value)}
                className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Auction Schedule & Time Caps */}
        <div className="bg-surface border border-hairline rounded p-5 shadow-subtle space-y-4">
          <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider border-b border-hairline pb-2">
            2. Auction Schedule & Guardrail Caps
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                Bid Start Time *
              </label>
              <input
                type="datetime-local"
                required
                value={bidStartTime}
                onChange={(e) => setBidStartTime(e.target.value)}
                className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
              />
            </div>

            <div>
              <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                Scheduled Bid Close *
              </label>
              <input
                type="datetime-local"
                required
                value={bidCloseTime}
                onChange={(e) => setBidCloseTime(e.target.value)}
                className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
              />
            </div>

            <div>
              <label className="block text-xs font-mono font-semibold text-accent-brick uppercase mb-1 flex items-center justify-between">
                <span>Forced Close Cap *</span>
                <span className="text-[10px] text-muted font-normal">Strict Limit</span>
              </label>
              <input
                type="datetime-local"
                required
                value={forcedCloseTime}
                onChange={(e) => setForcedCloseTime(e.target.value)}
                className="w-full text-xs font-mono bg-bg border border-accent-brick/40 rounded px-3 py-2 text-accent-brick focus:outline-none focus:border-accent-brick font-semibold"
              />
            </div>
          </div>
        </div>

        {/* Section 3: British Auction Engine */}
        <div className="bg-surface border border-hairline rounded p-5 shadow-subtle space-y-4">
          <div className="flex items-center justify-between border-b border-hairline pb-3">
            <div>
              <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
                3. British Anti-Sniping Configuration
              </h2>
              <p className="text-[11px] text-muted">
                Automatically extends auction if bidding occurs near close time
              </p>
            </div>

            {/* Toggle Button */}
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono text-muted">
                {isBritish ? 'Enabled' : 'Disabled (Standard)'}
              </span>
              <button
                type="button"
                onClick={() => setIsBritish(!isBritish)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  isBritish ? 'bg-accent-orange' : 'bg-muted/30'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    isBritish ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          </div>

          {isBritish && (
            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                    Trigger Window X (mins) *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required={isBritish}
                    value={triggerWindowX}
                    onChange={(e) => setTriggerWindowX(parseInt(e.target.value, 10) || 1)}
                    className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
                  />
                  <span className="text-[10px] font-mono text-muted mt-1 block">
                    Last {triggerWindowX}m before close
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                    Extension Duration Y (mins) *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required={isBritish}
                    value={extensionDurationY}
                    onChange={(e) => setExtensionDurationY(parseInt(e.target.value, 10) || 1)}
                    className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
                  />
                  <span className="text-[10px] font-mono text-muted mt-1 block">
                    Adds +{extensionDurationY}m to close
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-mono font-semibold text-ink uppercase mb-1">
                    Extension Trigger *
                  </label>
                  <select
                    value={extensionTrigger}
                    onChange={(e) => setExtensionTrigger(e.target.value as ExtensionTrigger)}
                    className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink"
                  >
                    <option value="L1_CHANGE_IN_LAST_X">L1 Change Only (Lowest bidder changes)</option>
                    <option value="BID_IN_LAST_X">Any Bid (Any quote placed)</option>
                    <option value="ANY_RANK_CHANGE_IN_LAST_X">Any Rank Change (Any carrier rank shifts)</option>
                  </select>
                  <span className="text-[10px] font-mono text-muted mt-1 block">
                    Condition to trigger extension
                  </span>
                </div>
              </div>

              {/* Plain English Banner */}
              <div className="p-3 bg-accent-orange/[0.08] border border-accent-orange/30 rounded text-xs font-mono text-ink">
                <span className="text-accent-orange font-bold uppercase block text-[10px] mb-0.5">
                  Rule Explanation:
                </span>
                {getExplanation()}
              </div>
            </div>
          )}
        </div>

        {/* Section 4: Carrier Invitation (Multi-select) */}
        <div className="bg-surface border border-hairline rounded p-5 shadow-subtle space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-hairline pb-2">
            <div>
              <h2 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
                4. Carrier Invitations ({selectedSupplierIds.length} Selected) *
              </h2>
              <p className="text-[11px] text-muted">
                Only invited carriers are authorized to submit quotes
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={handleSelectAll}
                className="text-xs font-mono text-accent-green hover:underline"
              >
                Select All
              </button>
              <span className="text-hairline">|</span>
              <button
                type="button"
                onClick={handleClearAll}
                className="text-xs font-mono text-muted hover:underline"
              >
                Clear All
              </button>
            </div>
          </div>

          {/* Carrier Search */}
          <input
            type="text"
            placeholder="Search carriers by name or code..."
            value={supplierSearch}
            onChange={(e) => setSupplierSearch(e.target.value)}
            className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink focus:outline-none focus:border-ink placeholder:text-muted"
          />

          {isLoadingSuppliers ? (
            <p className="text-xs font-mono text-muted py-4 text-center">Loading carriers...</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 max-h-48 overflow-y-auto pr-1">
              {filteredSuppliers.map((s) => {
                const isSelected = selectedSupplierIds.includes(s.id);
                return (
                  <div
                    key={s.id}
                    onClick={() => toggleSupplier(s.id)}
                    className={`p-2.5 rounded border text-xs cursor-pointer select-none transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-ink text-surface border-ink font-semibold'
                        : 'bg-bg/60 border-hairline text-ink hover:border-ink/40'
                    }`}
                  >
                    <div>
                      <div>{s.name}</div>
                      <div className={`text-[10px] font-mono ${isSelected ? 'text-surface/70' : 'text-muted'}`}>
                        {s.code}
                      </div>
                    </div>
                    <span className="font-mono text-xs ml-2">
                      {isSelected ? '✓' : '+'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Errors */}
        {errorMsg && (
          <div className="p-3 bg-accent-brick/10 border border-accent-brick/30 rounded text-accent-brick text-xs font-mono">
            {errorMsg}
          </div>
        )}

        {/* Submit Bar */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="px-4 py-2 rounded text-xs font-mono text-muted hover:text-ink hover:bg-bg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || selectedSupplierIds.length === 0}
            className="px-6 py-2.5 rounded text-xs font-mono font-bold uppercase tracking-wider text-white bg-accent-orange hover:bg-accent-orange/90 transition-all disabled:bg-muted/40 disabled:cursor-not-allowed shadow-sm"
          >
            {isSubmitting ? 'Publishing RFQ...' : 'Publish RFQ Auction'}
          </button>
        </div>
      </form>
    </div>
  );
};
