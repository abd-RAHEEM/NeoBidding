import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Header } from './components/common/Header';
import { AuctionsListPage } from './pages/AuctionsListPage';
import { CreateRfqPage } from './pages/CreateRfqPage';
import { AuctionDetailPage } from './pages/AuctionDetailPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2000,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col bg-bg text-ink">
          <Header />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<AuctionsListPage />} />
              <Route path="/rfqs/new" element={<CreateRfqPage />} />
              <Route path="/rfqs/:id" element={<AuctionDetailPage />} />
            </Routes>
          </main>
          <footer className="border-t border-hairline py-4 bg-surface text-center text-xs font-mono text-muted">
            RFQ Ledger British Auction Engine • Hiring Assignment Implementation
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
