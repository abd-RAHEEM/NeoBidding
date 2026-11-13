import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchRfqs } from '../api/rfqs';
import { RfqCard } from '../components/rfq/RfqCard';
import { RfqFilter } from '../components/rfq/RfqFilter';
import { Link } from 'react-router-dom';

export const AuctionsListPage: React.FC = () => {
  const [status, setStatus] = useState<string>('ALL');
  const [search, setSearch] = useState<string>('');

  const { data: rfqs, isLoading, error } = useQuery({
    queryKey: ['rfqs', status, search],
    queryFn: () => fetchRfqs({ status, search }),
    refetchInterval: 3000, // 3-second auto-refresh
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Ledger Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-serif font-bold text-ink tracking-tight">
            Auctions Ledger
          </h1>
          <p className="text-sm text-muted mt-1">
            Real-time reverse bidding dashboard with automatic British anti-sniping extensions.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Link
            to="/rfqs/new"
            className="px-4 py-2 rounded text-xs font-mono font-semibold bg-accent-orange text-white hover:bg-accent-orange/90 transition-all shadow-sm flex items-center space-x-1.5"
          >
            <span>+</span>
            <span>Create New RFQ</span>
          </Link>
        </div>
      </div>

      {/* Filter & Search */}
      <RfqFilter
        status={status}
        onStatusChange={setStatus}
        search={search}
        onSearchChange={setSearch}
      />

      {/* Content Area */}
      {isLoading ? (
        <div className="py-20 text-center">
          <div className="inline-block w-6 h-6 border-2 border-ink border-t-transparent rounded-full animate-spin mb-3" />
          <p className="text-xs font-mono text-muted">Loading live auction ledgers...</p>
        </div>
      ) : error ? (
        <div className="p-6 rounded bg-accent-brick/10 border border-accent-brick/30 text-accent-brick text-center">
          <p className="font-mono text-xs font-semibold">Failed to load auctions</p>
          <p className="text-xs mt-1">{(error as any)?.message || 'Please check backend connection.'}</p>
        </div>
      ) : !rfqs || rfqs.length === 0 ? (
        <div className="p-12 text-center bg-surface border border-dashed border-hairline rounded">
          <span className="text-3xl mb-2 block">📋</span>
          <h3 className="font-serif text-lg font-bold text-ink mb-1">No Auctions Found</h3>
          <p className="text-xs font-mono text-muted max-w-sm mx-auto mb-4">
            {search || status !== 'ALL'
              ? 'No auctions match the current search or status filter.'
              : 'There are no RFQs registered yet. Create your first British auction to start.'}
          </p>
          <Link
            to="/rfqs/new"
            className="inline-flex items-center px-4 py-2 rounded text-xs font-mono font-semibold bg-ink text-surface hover:bg-ink/90 transition-all"
          >
            + Create RFQ
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {rfqs.map((rfq) => (
            <RfqCard key={rfq.id} rfq={rfq} />
          ))}
        </div>
      )}
    </div>
  );
};
