export const API = '/api/v1';

export const store = {
  get token() {
    return localStorage.getItem('nola_token');
  },
  set token(value) {
    value
      ? localStorage.setItem('nola_token', value)
      : localStorage.removeItem('nola_token');
  },
  get user() {
    try {
      return JSON.parse(localStorage.getItem('nola_user'));
    } catch {
      return null;
    }
  },
  set user(value) {
    value
      ? localStorage.setItem('nola_user', JSON.stringify(value))
      : localStorage.removeItem('nola_user');
  },
};

export async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && store.token) headers.Authorization = 'Bearer ' + store.token;
  const response = await fetch(API + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // hiện luôn lý do cụ thể từ backend thay vì chỉ "Dữ liệu không hợp lệ"
    const detail = Array.isArray(data.details) ? data.details[0]?.message : null;
    const message = data.message || 'Lỗi ' + response.status;
    const error = new Error(detail && detail !== message ? `${message}: ${detail}` : message);
    error.status = response.status;
    error.details = data.details;
    throw error;
  }
  return data;
}

export async function uploadFile(file, purpose = 'PRODUCT') {
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  return api('/upload', {
    method: 'POST',
    body: {
      mimeType: file.type,
      base64: String(dataUrl).split(',')[1],
      purpose,
    },
  });
}

export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
