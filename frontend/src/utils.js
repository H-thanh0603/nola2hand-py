export const IMG_PH =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#e8f0e9"/><text x="200" y="150" font-size="44" text-anchor="middle" fill="#9db3a1">📦</text><text x="200" y="185" font-size="14" text-anchor="middle" fill="#9db3a1">Nola2Hand</text></svg>`,
  );

export const fmtVND = (n) =>
  n == null ? '—' : Number(n).toLocaleString('vi-VN') + ' đ';

export const fmtDate = (d) =>
  d
    ? new Date(d).toLocaleString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—';

// Ảnh seed trong DB là URL tuyệt đối kiểu http://localhost:4000/assets/...; đưa về
// đường dẫn tương đối để Vite/public (và bản build) phục vụ đúng.
export const img = (u) => {
  if (!u) return IMG_PH;
  try {
    const parsed = new URL(u, window.location.origin);
    if (parsed.pathname.startsWith('/assets/')) return parsed.pathname;
  } catch {
    /* giữ nguyên URL lạ */
  }
  return u;
};

export const onImgError = (event) => {
  if (event.currentTarget.src !== IMG_PH) event.currentTarget.src = IMG_PH;
};

export function cleanLabel(text) {
  return String(text || '').replace(/^[\s\p{Extended_Pictographic}\uFE0F＋]+/u, '');
}

export function qs(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null) search.set(key, String(value));
  });
  return search.toString();
}
