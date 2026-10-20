import { useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { WORKFLOW_LABELS } from '../constants';
import { useSession } from '../session';
import {
  ErrorState,
  EvidenceGrid,
  Loading,
  Pagination,
  useAsync,
  useToast,
  WorkflowBadge,
} from '../ui';
import { fmtDate, fmtVND, qs } from '../utils';

const FLOW = ['REQUESTED', 'APPROVED', 'SHIPPED', 'RECEIVED', 'REFUNDED'];
const STATUSES = ['REQUESTED', 'APPROVED', 'SHIPPED', 'RECEIVED', 'REFUNDED', 'REJECTED', 'CANCELLED'];

export function ReturnCard({ request, onChanged }) {
  const { user, hasRole } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState('');

  const order = request.order || {};
  const buyer = user?.id === order.buyerId;
  const seller = user?.id === order.sellerId;
  const admin = hasRole('ADMIN_FINANCE') && !buyer && !seller;

  async function act(action) {
    const body = { action };
    if (['APPROVE', 'REJECT', 'RECEIVE', 'REFUND'].includes(action)) {
      const note = window.prompt('Ghi lý do / tình trạng hàng nhận lại:');
      if (note === null || !note.trim()) return;
      body.note = note.trim();
    }
    if (action === 'SHIP') {
      const trackingCode = window.prompt('Mã vận đơn hoặc thông tin bàn giao:');
      if (trackingCode === null || !trackingCode.trim()) return;
      body.trackingCode = trackingCode.trim();
    }
    if (action === 'COD_REFUND') {
      const codReference = window.prompt(
        `Đã hoàn thực tế ${fmtVND(request.codAmount)} COD. Nhập chứng từ / hình thức hoàn:`,
      );
      if (codReference === null || !codReference.trim()) return;
      body.codReference = codReference.trim();
    }
    if (action === 'COD_CONFIRM' && !window.confirm(`Bạn đã thực nhận lại ${fmtVND(request.codAmount)} COD ngoài ví?`)) {
      return;
    }
    if (action === 'CANCEL' && !window.confirm('Hủy yêu cầu trả hàng?')) return;

    setBusy(action);
    try {
      await api('/returns/' + request.id, { method: 'PATCH', body });
      toast('Đã cập nhật tiến trình', 'ok');
      onChanged?.();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  const button = (action, label, green = false) => (
    <button
      key={action}
      type="button"
      className={'btn ' + (green ? 'btn-green' : 'btn-line') + ' btn-sm'}
      disabled={Boolean(busy)}
      onClick={() => act(action)}
    >
      {busy === action ? 'Đang xử lý...' : label}
    </button>
  );

  const actions = [];
  if (request.status === 'REQUESTED') {
    if (seller || admin) actions.push(button('APPROVE', 'Duyệt trả hàng', true), button('REJECT', 'Từ chối'));
    if (buyer) actions.push(button('CANCEL', 'Hủy yêu cầu'));
  }
  if (request.status === 'APPROVED' && buyer) actions.push(button('SHIP', 'Đã gửi trả / bàn giao', true));
  if (request.status === 'SHIPPED' && (seller || admin)) {
    actions.push(button('RECEIVE', 'Xác nhận đã nhận hàng trả', true));
  }
  if (request.status === 'RECEIVED') {
    if (seller && request.codAmount > 0 && !request.codRefundedAt) {
      actions.push(button('COD_REFUND', 'Ghi nhận hoàn COD ngoài ví'));
    }
    if (buyer && request.codRefundedAt && !request.codConfirmedAt) {
      actions.push(button('COD_CONFIRM', 'Tôi đã nhận lại tiền COD', true));
    }
    if (admin) actions.push(button('REFUND', 'Hoàn tiền SafePay', true));
  }

  return (
    <article className="workflow-card">
      <h3>
        {order.id ? <Link to={'/orders/' + order.id}>Đơn {order.code}</Link> : 'Đơn ' + (order.code || '')}
        {order.listing?.title ? ' · ' + order.listing.title : ''}
      </h3>
      <WorkflowBadge status={request.status} />
      <ol className="return-progress">
        {FLOW.map((status) => (
          <li key={status} className={status === request.status ? 'on' : ''}>
            {WORKFLOW_LABELS[status]}
          </li>
        ))}
      </ol>
      <p>{request.reason}</p>
      <p>
        Hoàn vào ví: <b>{fmtVND(request.refundAmount)}</b>
        {request.codAmount ? (
          <>
            {' · '}COD hoàn ngoài ví: <b>{fmtVND(request.codAmount)}</b>
          </>
        ) : null}
      </p>
      <p className="muted">
        Người mua: {order.buyer?.fullName || ''} · Người bán: {order.seller?.fullName || ''} ·{' '}
        {fmtDate(request.requestedAt)}
      </p>
      {request.trackingCode && <p>Gửi trả: {request.trackingCode}</p>}
      {request.receivedNote && <p>Nhận lại: {request.receivedNote}</p>}
      {request.codReference && (
        <p>
          Chứng từ COD: {request.codReference} ·{' '}
          {request.codConfirmedAt ? 'buyer đã xác nhận' : 'chờ buyer xác nhận'}
        </p>
      )}
      {request.resolution && <p>Ghi chú: {request.resolution}</p>}
      <EvidenceGrid urls={request.evidences || []} />
      {actions.length > 0 && <div className="workflow-actions">{actions}</div>}
    </article>
  );
}

function ReturnsInner() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get('page')) || 1);
  const status = params.get('status') || '';

  const { data, loading, error, reload } = useAsync(
    () => api('/returns?' + qs({ page, limit: 10, status })),
    [page, status],
  );

  function setFilter(value) {
    const next = new URLSearchParams(params);
    if (value) next.set('status', value);
    else next.delete('status');
    next.delete('page');
    setParams(next);
  }

  function goPage(value) {
    const next = new URLSearchParams(params);
    next.set('page', value);
    setParams(next);
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 6 }}>↩️ Trả hàng và hoàn tiền</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Yêu cầu trong 7 ngày sau khi giao hàng. Tiền chỉ hoàn sau khi hàng đã nhận lại. Phí sàn đã thu không tự hoàn.
      </p>

      <div className="toolbar">
        <select className="input" aria-label="Lọc trạng thái" value={status} onChange={(event) => setFilter(event.target.value)}>
          <option value="">Tất cả trạng thái</option>
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {WORKFLOW_LABELS[item] || item}
            </option>
          ))}
        </select>
      </div>

      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState error={error} />
      ) : (
        <div id="my-returns">
          {(data?.data || []).map((request) => (
            <ReturnCard key={request.id} request={request} onChanged={reload} />
          ))}
          {!data?.data?.length && <div className="empty">Chưa có yêu cầu trả hàng.</div>}
          <Pagination meta={data?.meta} onPage={goPage} />
        </div>
      )}
    </div>
  );
}

export default function Returns() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <ReturnsInner />;
}
