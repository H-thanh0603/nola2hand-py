import { useEffect, useState } from 'react';

const KEY = 'nola_compare';

export function comparisonIds() {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(value)
      ? [...new Set(value.filter((n) => Number.isSafeInteger(n) && n > 0))].slice(0, 3)
      : [];
  } catch {
    return [];
  }
}

function emit() {
  window.dispatchEvent(new Event('nola-compare'));
}

export function toggleComparison(id) {
  let ids = comparisonIds();
  if (ids.includes(id)) {
    ids = ids.filter((value) => value !== id);
  } else {
    if (ids.length >= 3) return { ids, added: false, limit: true };
    ids.push(id);
  }
  localStorage.setItem(KEY, JSON.stringify(ids));
  emit();
  return { ids, added: ids.includes(id), limit: false };
}

export function clearComparison() {
  localStorage.removeItem(KEY);
  emit();
}

export function useComparison() {
  const [ids, setIds] = useState(comparisonIds);
  useEffect(() => {
    const update = () => setIds(comparisonIds());
    window.addEventListener('nola-compare', update);
    return () => window.removeEventListener('nola-compare', update);
  }, []);
  return ids;
}
