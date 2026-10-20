import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api';
import { useCategories } from '../categories';
import { CONDITION_NAMES, DELIVERY_NAMES } from '../constants';
import { useSession } from '../session';
import { qs } from '../utils';
import { ErrorState, Loading, useAsync, useToast } from '../ui';

const FILTER_LABELS = {
  q: 'Từ khóa',
  categoryId: 'Danh mục',
  condition: 'Tình trạng',
  minPrice: 'Giá từ',
  maxPrice: 'Giá đến',
  city: 'Địa điểm',
  deliveryMethod: 'Giao nhận',
  verified: 'Đã xác minh',
  isFree: 'Cho tặng',
};

export default function SavedSearches() {
  const { token } = useSession();
  const categories = useCategories();
  const toast = useToast();
  const [busy, setBusy] = useState(null);

  const { data: searches, loading, error, reload } = useAsync(
    () => (token ? api('/saved-searches') : Promise.resolve([])),
    [token],
  );

  if (!token) return <Navigate to="/login" replace />;
  if (loading && !searches) return <Loading />;
  if (error) return <ErrorState error={error} />;

  async function toggle(search) {
    setBusy(search.id);
    try {
      await api('/saved-searches/' + search.id, {
        method: 'PATCH',
        body: { enabled: !search.enabled },
      });
      reload();
    } catch (requestError) {
      toast(requestError.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  async function remove(search) {
    if (!confirm('Xóa tìm kiếm theo dõi này?')) return;
    setBusy(search.id);
    try {
      await api('/saved-searches/' + search.id, { method: 'DELETE' });
      reload();
    } catch (requestError) {
      toast(requestError.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  function valueLabel(key, value) {
    if (key === 'categoryId') {
      return categories.find((item) => item.id === Number(value))?.name || value;
    }
    if (key === 'condition') return CONDITION_NAMES[value] || value;
    if (key === 'deliveryMethod') return DELIVERY_NAMES[value] || value;
    if (value === 'true') return 'Có';
    if (value === 'false') return 'Không';
    return value;
  }

  return (
    <div className="wrap">
      <h1>🔔 Tìm kiếm đang theo dõi</h1>
      <p className="muted">
        Thông báo trong ứng dụng khi tin mới được duyệt; không gửi lại cùng một
        tin.
      </p>

      {searches?.length ? (
        searches.map((search) => {
          const { categoryId, ...query } = search.filters;
          const category = categories.find(
            (item) => item.id === Number(categoryId),
          );
          const path = category ? '/category/' + category.slug : '/';
          return (
            <div className="sect" key={search.id}>
              <h2>{search.name}</h2>
              <div className="chips">
                {Object.entries(search.filters).map(([key, value]) => (
                  <span className="chip" key={key}>
                    {FILTER_LABELS[key] || key}: {valueLabel(key, value)}
                  </span>
                ))}
              </div>
              <Link className="btn btn-green btn-sm" to={path + '?' + qs(query)}>
                Xem kết quả
              </Link>{' '}
              <button
                className="btn btn-line btn-sm"
                disabled={busy === search.id}
                onClick={() => toggle(search)}
              >
                {search.enabled ? 'Tạm dừng thông báo' : 'Bật thông báo'}
              </button>{' '}
              <button
                className="btn btn-line btn-sm"
                disabled={busy === search.id}
                onClick={() => remove(search)}
              >
                Xóa
              </button>
            </div>
          );
        })
      ) : (
        <div className="empty">
          Chưa theo dõi tìm kiếm nào. Vào trang danh mục và chọn Theo dõi tìm
          kiếm.
        </div>
      )}
    </div>
  );
}
