import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useServerClock } from '../../hooks/useServerClock';

export const Header: React.FC = () => {
  const location = useLocation();
  const { utcString } = useServerClock();

  return (
    <header className="border-b border-hairline bg-surface sticky top-0 z-50 shadow-subtle">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <Link to="/" className="flex items-center space-x-2 group">
            <span className="text-xl">⚖️</span>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-serif text-xl font-bold tracking-tight text-ink group-hover:text-accent-orange transition-colors">
                  NEOBIDDING
                </span>
                <span className="text-[10px] uppercase font-mono tracking-widest px-1.5 py-0.5 rounded bg-ink/5 text-muted border border-hairline">
                  Trading Desk
                </span>
              </div>
              <p className="text-[11px] text-muted -mt-0.5 hidden sm:block">
                British Reverse Auction & Carrier Bidding Engine
              </p>
            </div>
          </Link>
        </div>

        {/* Server Clock Sync */}
        <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-bg border border-hairline">
          <span className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
          <span className="text-xs font-mono text-muted tracking-tight">
            SERVER CLOCK: <strong className="text-ink font-semibold tabular-nums">{utcString}</strong>
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex items-center space-x-2">
          <Link
            to="/"
            className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-all ${
              location.pathname === '/'
                ? 'bg-ink text-surface shadow-sm'
                : 'text-muted hover:text-ink hover:bg-bg'
            }`}
          >
            Auctions
          </Link>
          <Link
            to="/rfqs/new"
            className={`px-3.5 py-1.5 rounded text-xs font-mono font-semibold transition-all inline-flex items-center space-x-1.5 ${
              location.pathname === '/rfqs/new'
                ? 'bg-accent-orange text-white shadow-sm'
                : 'bg-accent-orange/10 text-accent-orange hover:bg-accent-orange hover:text-white'
            }`}
          >
            <span>+</span>
            <span>Create RFQ</span>
          </Link>
        </nav>
      </div>
    </header>
  );
};

