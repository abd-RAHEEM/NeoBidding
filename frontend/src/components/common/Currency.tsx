import React from 'react';
import type { Currency as CurrencyType } from '../../api/types';

interface CurrencyProps {
  amount: string | number | null | undefined;
  currency?: CurrencyType | string;
  className?: string;
  showCode?: boolean;
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: '₹',
  USD: '$',
  EUR: '€',
  GBP: '£',
  AED: 'AED ',
};

export const Currency: React.FC<CurrencyProps> = ({
  amount,
  currency = 'INR',
  className = '',
  showCode = false,
}) => {
  if (amount === null || amount === undefined || amount === '') {
    return <span className={`text-muted font-mono ${className}`}>—</span>;
  }

  const num = typeof amount === 'number' ? amount : parseFloat(amount);
  if (isNaN(num)) {
    return <span className={`text-muted font-mono ${className}`}>—</span>;
  }

  const formatted = num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  const symbol = CURRENCY_SYMBOLS[currency] || `${currency} `;

  return (
    <span className={`font-mono tabular-nums ${className}`}>
      <span className="text-muted mr-0.5">{symbol}</span>
      <span>{formatted}</span>
      {showCode && <span className="text-xs text-muted ml-1">{currency}</span>}
    </span>
  );
};

