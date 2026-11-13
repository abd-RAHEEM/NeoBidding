import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchRfqDetail } from '../api/rfqs';
import { Badge } from '../components/common/Badge';
import { Countdown } from '../components/common/Countdown';
import { StatsStrip } from '../components/common/StatsStrip';
import { TimelineBar } from '../components/common/TimelineBar';
import { SupplierRankingTab } from '../components/rfq/SupplierRankingTab';
import { BidHistoryTab } from '../components/rfq/BidHistoryTab';
import { ActivityLog } from '../components/rfq/ActivityLog';
import { BidForm } from '../components/rfq/BidForm';

export const AuctionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<'RANKING' | 'HISTORY'>('RANKING');

  const {
    data: rfq,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['rfq', id],
    queryFn: () => fetchRfqDetail(id!),
    enabled: !!id,
    refetchInterval: 3000, // 3-second auto-poll
  });

  if (isLoading) {
    return (
      <div className="py-24 text-center">
        <div className="inline-block w-6 h-6 border-2 border-ink border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-xs font-mono text-muted">Loading live auction state...</p>
      </div>
    );
  }

  if (error || !rfq) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <div className="p-6 rounded bg-accent-brick/10 border border-accent-brick/30 text-accent-brick inline-block">
          <p className="font-mono text-xs font-semibold">Failed to load auction ledger</p>
          <p className="text-xs mt-1">{(error as any)?.message || 'Auction not found'}</p>
        </div>
        <div className="mt-4">
          <Link to="/" className="text-xs font-mono text-ink underline">
            ← Return to Auctions
          </Link>
        </div>
      </div>
    );
  }

  const isBritish = rfq.mode === 'BRITISH';
  const cfg = rfq.british_config;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Breadcrumb & Status Bar */}
      <div>
        <Link
          to="/"
          className="inline-flex items-center text-xs font-mono text-muted hover:text-ink transition-colors mb-3"
        >
          ← Back to Auctions Ledger
        </Link>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-surface p-5 rounded border border-hairline shadow-subtle">
          <div>
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="font-mono text-xs font-bold text-muted">
                {rfq.reference_id}
              </span>
              <Badge status={rfq.status} />
              <Badge mode={rfq.mode} />
              {isBritish && cfg && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-bg text-muted border border-hairline">
                  Trigger: {cfg.extension_trigger}
                </span>
              )}
            </div>
            <h1 className="text-2xl sm:text-3xl font-serif font-bold text-ink tracking-tight">
              {rfq.name}
            </h1>
            <p className="text-xs text-muted font-mono mt-1">
              Pickup Date: {rfq.pickup_date} • Currency: {rfq.currency}
            </p>
          </div>

          {/* Countdown & Extension Status */}
          <div className="flex items-center gap-4 border-t lg:border-t-0 pt-3 lg:pt-0 border-hairline">
            <div className="text-right">
              <span className="text-[10px] font-mono text-muted uppercase block">
                {rfq.status === 'SCHEDULED' ? 'Auction Opens In' : 'Bidding Closes In'}
              </span>
              <div className="mt-1">
                <Countdown
                  targetTime={rfq.current_close_time}
                  startTime={rfq.bid_start_time}
                  status={rfq.status}
                  isInTriggerWindow={rfq.in_trigger_window}
                />
              </div>
            </div>

            {isBritish && rfq.stats.extension_count > 0 && (
              <div className="px-3 py-1.5 rounded bg-accent-orange/10 border border-accent-orange/20 text-right">
                <span className="text-[10px] font-mono text-accent-orange uppercase font-bold block">
                  Anti-Sniping Fired
                </span>
                <span className="text-xs font-mono font-bold text-accent-orange">
                  +{rfq.stats.extension_count * (cfg?.extension_duration_minutes || 0)}m Total
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Timeline Guardrail Bar */}
      <TimelineBar
        startTime={rfq.bid_start_time}
        originalCloseTime={rfq.original_close_time}
        currentCloseTime={rfq.current_close_time}
        forcedCloseTime={rfq.forced_close_time}
        triggerWindowMinutes={cfg?.trigger_window_minutes}
        status={rfq.status}
        inTriggerWindow={rfq.in_trigger_window}
      />

      {/* Stats Strip */}
      <StatsStrip stats={rfq.stats} currency={rfq.currency} />

      {/* Main Content Grid: Views & Bid Submission */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Views & Activity (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Tabs Navigation */}
          <div>
            <div className="flex items-center space-x-2 border-b border-hairline pb-2 mb-3">
              <button
                type="button"
                onClick={() => setActiveTab('RANKING')}
                className={`px-3 py-1.5 rounded text-xs font-mono font-semibold transition-all ${
                  activeTab === 'RANKING'
                    ? 'bg-ink text-surface shadow-sm'
                    : 'text-muted hover:text-ink hover:bg-surface'
                }`}
              >
                1. Supplier Ranking ({rfq.supplier_rankings.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('HISTORY')}
                className={`px-3 py-1.5 rounded text-xs font-mono font-semibold transition-all ${
                  activeTab === 'HISTORY'
                    ? 'bg-ink text-surface shadow-sm'
                    : 'text-muted hover:text-ink hover:bg-surface'
                }`}
              >
                2. Bid History ({rfq.bid_history.length})
              </button>
            </div>

            {/* Tab 1: Supplier Ranking */}
            {activeTab === 'RANKING' && (
              <SupplierRankingTab
                rankings={rfq.supplier_rankings}
                currency={rfq.currency}
              />
            )}

            {/* Tab 2: Full Bid History */}
            {activeTab === 'HISTORY' && (
              <BidHistoryTab
                bids={rfq.bid_history}
                currency={rfq.currency}
              />
            )}
          </div>

          {/* Activity Log & Audit Trail */}
          <ActivityLog events={rfq.activity_log} />
        </div>

        {/* Right Column: Bid Submission Form & Rules (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Bid Form */}
          <BidForm
            rfqId={rfq.id}
            currency={rfq.currency}
            status={rfq.status}
            invitedSuppliers={rfq.invited_suppliers}
            supplierRankings={rfq.supplier_rankings}
            onBidSubmitted={() => refetch()}
          />

          {/* British Auction Engine Spec Card */}
          <div className="bg-surface border border-hairline rounded p-4 shadow-subtle text-xs font-mono">
            <h4 className="font-bold text-ink uppercase tracking-wider mb-2 border-b border-hairline pb-1.5">
              Auction Engine Rules & Guardrails
            </h4>
            <div className="space-y-2 text-muted">
              <div>
                <strong className="text-ink">Trigger Window (X): </strong>
                {isBritish && cfg ? `${cfg.trigger_window_minutes} minutes before current close` : 'None (Standard)'}
              </div>
              <div>
                <strong className="text-ink">Extension Duration (Y): </strong>
                {isBritish && cfg ? `+${cfg.extension_duration_minutes} minutes added per trigger` : 'None'}
              </div>
              <div>
                <strong className="text-ink">Trigger Policy: </strong>
                {isBritish && cfg ? cfg.extension_trigger : 'STANDARD_AUCTION'}
              </div>
              <div>
                <strong className="text-accent-brick">Hard Forced Cap: </strong>
                Strict closure cap — no extension may exceed forced close time under any condition.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
