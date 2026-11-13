import { useState, useEffect } from 'react';
import { getServerNow } from '../api/client';

export interface CountdownResult {
  formatted: string;
  isExpired: boolean;
  totalSeconds: number;
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  isUrgent: boolean; // < 2 minutes or custom urgent threshold
}

export function useCountdown(
  targetTimeIso: string | null | undefined,
  urgentThresholdSeconds: number = 120
): CountdownResult {
  const calculate = (): CountdownResult => {
    if (!targetTimeIso) {
      return {
        formatted: '--:--',
        isExpired: false,
        totalSeconds: 0,
        days: 0,
        hours: 0,
        minutes: 0,
        seconds: 0,
        isUrgent: false,
      };
    }

    const target = new Date(targetTimeIso).getTime();
    const now = getServerNow().getTime();
    const diffMs = target - now;
    const totalSeconds = Math.max(0, Math.floor(diffMs / 1000));
    const isExpired = diffMs <= 0;

    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const pad = (n: number) => n.toString().padStart(2, '0');

    let formatted = '';
    if (days > 0) {
      formatted = `${days}d ${pad(hours)}h ${pad(minutes)}m`;
    } else if (hours > 0) {
      formatted = `${pad(hours)}h ${pad(minutes)}m ${pad(seconds)}s`;
    } else {
      formatted = `${pad(minutes)}m ${pad(seconds)}s`;
    }

    if (isExpired) {
      formatted = '00m 00s';
    }

    return {
      formatted,
      isExpired,
      totalSeconds,
      days,
      hours,
      minutes,
      seconds,
      isUrgent: !isExpired && totalSeconds <= urgentThresholdSeconds,
    };
  };

  const [state, setState] = useState<CountdownResult>(calculate);

  useEffect(() => {
    setState(calculate());
    const interval = setInterval(() => {
      setState(calculate());
    }, 1000);
    return () => clearInterval(interval);
  }, [targetTimeIso, urgentThresholdSeconds]);

  return state;
}
