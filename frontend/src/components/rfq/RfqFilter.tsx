import React from 'react';

interface RfqFilterProps {
  status: string;
  onStatusChange: (status: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
}

export const RfqFilter: React.FC<RfqFilterProps> = ({
  status,
  onStatusChange,
  search,
  onSearchChange,
}) => {
  const statuses = [
    { label: 'All Auctions', value: 'ALL' },
    { label: 'Active', value: 'ACTIVE' },
    { label: 'Scheduled', value: 'SCHEDULED' },
    { label: 'Closed', value: 'CLOSED' },
    { label: 'Forced Closed', value: 'FORCE_CLOSED' },
  ];

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-6 bg-surface p-3 rounded border border-hairline shadow-subtle">
      {/* Search Input */}
      <div className="relative flex-1 max-w-md">
        <input
          type="text"
          placeholder="Search by RFQ Name or Reference ID..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full text-xs font-mono bg-bg border border-hairline rounded px-3 py-2 text-ink placeholder:text-muted focus:outline-none focus:border-ink transition-colors"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-ink text-xs font-mono"
          >
            ✕
          </button>
        )}
      </div>

      {/* Status Pills */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
        {statuses.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => onStatusChange(s.value)}
            className={`px-3 py-1.5 rounded text-xs font-mono transition-all whitespace-nowrap ${
              status === s.value
                ? 'bg-ink text-surface font-semibold shadow-sm'
                : 'text-muted hover:text-ink hover:bg-bg'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
};

