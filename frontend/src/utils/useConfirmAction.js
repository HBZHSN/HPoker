import { useEffect, useState } from 'react';

export const isConfirmed = (pending, key, now) =>
  pending?.key === key && pending.expires > now;

export function useConfirmAction() {
  const [pending, setPending] = useState(null);

  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => setPending(null), Math.max(0, pending.expires - Date.now()));
    return () => clearTimeout(timer);
  }, [pending]);

  const confirm = (key, label, action) => {
    if (isConfirmed(pending, key, Date.now())) {
      setPending(null);
      action();
    } else {
      setPending({ key, label, expires: Date.now() + 5000 });
    }
  };

  return { pending, confirm };
}
