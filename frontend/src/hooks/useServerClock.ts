import { useState, useEffect } from 'react';
import { getServerNow } from '../api/client';

export function useServerClock() {
  const [now, setNow] = useState<Date>(getServerNow);

  useEffect(() => {
    const timer = setInterval(() => {
      setNow(getServerNow());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const utcString = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  
  return {
    now,
    utcString,
  };
}

