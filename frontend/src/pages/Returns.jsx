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
  useModal,
} from '../ui';
import { fmtDate, fmtVND, qs } from '../utils';

const FLOW = ['REQUESTED', 'APPROVED', 'SHIPPED', 'RECEIVED', 'REFUNDED'];
const STATUSES = ['REQUESTED', 'APPROVED', 'SHIPPED', 'RECEIVED', 'REFUNDED', 'REJECTED', 'CANCELLED'];

function ReturnActionModal({ request, action, onDone, close }) {
  const toast = useToast();
  const [note, setNote] = useState('');
  const [tracking, setTracking] = useState('');
  const [busy, setBusy] = useState(false);

  const titles = {
    APPROVE: 'Duyệt yêu cầu trả hàng',
    REJECT: 'Từ chối yêu cầu trả hàng',
    RECEIVE: 'Xác nhận đã nhận hàng trả',
    SHIP: 'Gửi trả hàng cho người bán',
    COD_REFUND: 'Ghi nhận hoàn tiền COD',
    REFUND: 'Hoàn tiền qua ví SafePay',
    CANCEL: 'Hủy yêu cầu trả hàng',
  };

  const isShip = action === 'SHIP';
  const isCod = action === 'COD_REFUND';

  async function submit(e) {
    e.preventDefault();
    if ((isShip && !tracking.trim()) || (!isShip && !note.trim())) {
      toast('Vui lòng nhập thông tin', 'err');
      return;
    }
    setBusy(true);
    try {
      const body = { action };
      if (isShip) body.trackingCode = tracking.trim();
      else if (isCod) body.codReference = note.trim();
      else body.note = note.trim();

      await api('/returns/' + request.id, { method: 'PATCH', body });
      toast('Đã cập nhật tiến trình', 'ok');
      close();
      onDone();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>{titles[action]}</h3>
      
      {isShip && (
        <div className="form-row">
          <label className="lbl">Mã vận đơn / thông tin bàn giao *</label>
          <input className="input" value={tracking} onChange={e => setTracking(e.target.value)} required />
        </div>
      )}

      {!isShip && (
        <div className="form-row">
          <label className="lbl">{isCod ? 'Chứng từ / Hình thức hoàn tiền *' : 'Ghi chú xử lý *'}</label>
          <textarea className="input" rows={3} value={note} onChange={e => setNote(e.target.value)} required />
        </div>
      )}

      <button className="btn btn-green" style={{ width: '100%', marginTop: 10 }} disabled={busy}>
        {busy ? 'Đang xử lý...' : 'Xác nhận'}
      </button>
    </form>
  );
}

export function ReturnCard({ request, onChanged }) {
  const { user, hasRole } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState('');

  const order = request.order || {};
  const buyer = user?.id === order.buyerId;
  const seller = user?.id === order.sellerId;
  const admin = hasRole('ADMIN_FINANCE') && !buyer && !seller;

       const { openModal, closeModal } = useModal();

  async function act(action) {
    if (action === 'CANCEL' || action === 'COD_CONFIRM') {
      if (!window.confirm(action === 'CANCEL' ? 'Hủy yêu cầu trả hàng?' : `Bạn đã nhận lại tiền COD chưa?`)) return;
      // For these two, we can just call API directly since there's no note needed
      setBusy(action);
      try {
        await api('/returns/' + request.id, { method: 'PATCH', body: { action } });
        toast('Đã cập nhật', 'ok');
        onChanged?.();
      } catch (error) {
        toast(error.message, 'err');
      } finally {
        setBusy('');
      }
      return;
    }

    // Open modal for the rest
    openModal(<ReturnActionModal request={request} action={action} onDone={onChanged} close={closeModal} />);
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
