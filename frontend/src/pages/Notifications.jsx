import { useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import { ErrorState, Loading, Pagination, useAsync, useToast } from '../ui';
import { fmtDate, qs } from '../utils';

function linkFor(notification) {
  const data = notification.data || {};
  if (data.listingId) return '/listing/' + data.listingId;
  if (data.orderId) return '/orders/' + data.orderId;
  if (data.conversationId) return '/chat';
  if (data.offerId) return '/offers';
  return null;
}

function NotificationsInner() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const page = Math.max(1, Number(params.get('page')) || 1);
  const unread = params.get('unread') === 'true';
  const [marking, setMarking] = useState(false);

  const { data, loading, error, reload } = useAsync(
    () => api('/notifications?' + qs({ page, limit: 10, unread: unread ? 'true' : '' })),
    [page, unread],
  );

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next);
  }

  async function open(notification) {
    const link = linkFor(notification);
    if (!notification.isRead) {
      try {
        await api(`/notifications/${notification.id}/read`, { method: 'PATCH' });
      } catch (error) {
        toast(error.message, 'err');
        return;
      }
    }
    if (link) navigate(link);
    else reload();
  }

  async function markAll() {
    setMarking(true);
    try {
      await api('/notifications/read-all', { method: 'PATCH' });
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setMarking(false);
    }
  }

  const items = data?.data || [];

  return (
    <div className="wrap">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <h1 style={{ fontSize: 23 }}>
          🔔 Thông báo ({data?.unreadCount ?? 0} chưa đọc)
        </h1>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={'btn btn-sm ' + (unread ? 'btn-green' : 'btn-line')}
            onClick={() => setParam('unread', unread ? '' : 'true')}
          >
            {unread ? 'Đang xem chưa đọc' : 'Chỉ chưa đọc'}
          </button>
          <button type="button" className="btn btn-line btn-sm" disabled={marking} onClick={markAll}>
            {marking ? 'Đang xử lý...' : 'Đánh dấu đọc tất cả'}
          </button>
        </div>
      </div>

      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        <>
          {items.map((notification) => {
            const link = linkFor(notification);
            const body = (
              <>
                <b style={{ fontSize: 13.5 }}>{notification.title}</b>
                <div style={{ fontSize: 13, marginTop: 4 }}>{notification.body || ''}</div>
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                  {fmtDate(notification.createdAt)}
                </div>
                {link && <span className="badge b-blue" style={{ marginTop: 8 }}>Xem chi tiết →</span>}
              </>
            );
            const style = {
              padding: '16px 20px',
              marginBottom: 10,
              boxShadow: 'none',
              opacity: notification.isRead ? 0.75 : 1,
              borderLeft: notification.isRead ? undefined : '4px solid var(--green)',
              cursor: 'pointer',
              color: 'inherit',
              textDecoration: 'none',
              display: 'block',
            };
            return link ? (
              <Link
                key={notification.id}
                to={link}
                className="card"
                style={style}
                onClick={() => {
                  if (!notification.isRead) {
                    api(`/notifications/${notification.id}/read`, { method: 'PATCH' }).catch(() => {});
                  }
                }}
              >
                {body}
              </Link>
            ) : (
              <div
                key={notification.id}
                className="card"
                style={style}
                role="button"
                tabIndex={0}
                onClick={() => open(notification)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    open(notification);
                  }
                }}
              >
                {body}
              </div>
            );
          })}
          {!items.length && (
            <div className="empty">
              <div className="e">🔔</div>
              Chưa có thông báo.
            </div>
          )}
          <Pagination meta={data?.meta} onPage={(value) => setParam('page', value)} />
        </>
      )}
    </div>
  );
}

export default function Notifications() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <NotificationsInner />;
}
