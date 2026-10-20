import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { ORDER_ST } from '../constants';
import { useSession } from '../session';
import {
  ErrorState,
  Loading,
  Pagination,
  StatusPill,
  useAsync,
} from '../ui';
import { fmtDate, fmtVND, img, onImgError, qs } from '../utils';

const STATUSES = Object.keys(ORDER_ST);

function OrdersInner() {
  const { hasRole } = useSession();
  const seller = hasRole('SELLER');
  const [params, setParams] = useSearchParams();
  const tab = seller && params.get('tab') === 'sales' ? 'sales' : 'mine';
  const status = params.get('status') || '';
  const page = Math.max(1, Number(params.get('page')) || 1);

  const { data, loading, error } = useAsync(
    () => api(`/orders/${tab === 'sales' ? 'sales' : 'mine'}?` + qs({ page, limit: 10, status })),
    [tab, status, page],
  );

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    if (key === 'tab' && value === 'mine') next.delete('tab');
    setParams(next);
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 16 }}>📦 Đơn hàng</h1>

      <div className="toolbar">
        {seller && (
          <>
            <button
              type="button"
              className={'btn btn-sm ' + (tab === 'mine' ? 'btn-green' : 'btn-line')}
              onClick={() => setParam('tab', 'mine')}
            >
              Đơn tôi mua
            </button>
            <button
              type="button"
              className={'btn btn-sm ' + (tab === 'sales' ? 'btn-green' : 'btn-line')}
              onClick={() => setParam('tab', 'sales')}
            >
              Đơn tôi bán
            </button>
          </>
        )}
        <select
          className="input"
          aria-label="Lọc trạng thái đơn"
          value={status}
          onChange={(event) => setParam('status', event.target.value)}
        >
          <option value="">Tất cả trạng thái</option>
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {ORDER_ST[item][0]}
            </option>
          ))}
        </select>
      </div>

      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        <>
          {(data?.data || []).map((order) => (
            <Link
              key={order.id}
              to={'/orders/' + order.id}
              className="card"
              style={{
                padding: '16px 20px',
                marginBottom: 12,
                display: 'flex',
                gap: 16,
                alignItems: 'center',
                textDecoration: 'none',
                color: 'inherit',
              }}
            >
              <img
                src={img(order.listing?.images?.[0]?.url)}
                alt={order.listing?.title || 'Đơn hàng'}
                style={{ width: 96, height: 76, objectFit: 'cover', borderRadius: 10 }}
                onError={onImgError}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <b>#{order.code}</b> <StatusPill map={ORDER_ST} status={order.status} />
                <div style={{ fontSize: 13, marginTop: 4 }}>{order.listing?.title}</div>
                <div className="muted" style={{ fontSize: 11.5 }}>
                  {fmtDate(order.createdAt)}
                </div>
              </div>
              <b style={{ color: 'var(--green-dark)' }}>{fmtVND(order.totalAmount)}</b>
            </Link>
          ))}
          {!data?.data?.length && <p className="muted">Chưa có đơn nào.</p>}
          <Pagination meta={data?.meta} onPage={(value) => setParam('page', value)} />
        </>
      )}
    </div>
  );
}

export default function Orders() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <OrdersInner />;
}
