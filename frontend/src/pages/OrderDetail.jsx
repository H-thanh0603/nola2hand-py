import { useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { api, uploadFile } from '../api';
import { ESCROW_STATUS_NAMES, ORDER_ST, WORKFLOW_LABELS } from '../constants';
import { useSession } from '../session';
import {
  ErrorState,
  Loading,
  StatusPill,
  useAsync,
  useModal,
  useToast,
} from '../ui';
import { fmtDate, fmtVND, img, onImgError } from '../utils';
import { ReturnCard } from './Returns';

const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const DISPUTE_REASONS = [
  'Hàng không đúng mô tả',
  'Không nhận được hàng',
  'Hàng lỗi/hỏng',
  'Người bán không phản hồi',
];

function evidenceList(value) {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function EvidenceInput({ value, onChange, label = 'Ảnh bằng chứng' }) {
  const toast = useToast();
  const [uploading, setUploading] = useState(false);

  async function upload(event) {
    const input = event.target;
    const files = [...input.files];
    if (!files.length) return;
    const urls = evidenceList(value);
    if (files.length + urls.length > 5) {
      toast('Tối đa 5 ảnh', 'err');
      input.value = '';
      return;
    }
    if (files.some((file) => !IMAGE_TYPES.includes(file.type) || file.size > MAX_IMAGE_BYTES)) {
      toast('Chỉ nhận JPEG/PNG/WebP, tối đa 5MB mỗi ảnh', 'err');
      input.value = '';
      return;
    }
    setUploading(true);
    try {
      for (const file of files) {
        const result = await uploadFile(file, 'EVIDENCE');
        urls.push(result.url);
      }
      onChange(urls.join('\n'));
      toast('Đã tải ảnh lên máy chủ', 'ok');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setUploading(false);
      input.value = '';
    }
  }

  return (
    <div className="form-row">
      <label className="lbl">{label} (URL mỗi dòng, tối đa 5)</label>
      <textarea className="input" rows={2} value={value} onChange={(event) => onChange(event.target.value)} />
      <input
        className="input"
        style={{ marginTop: 8 }}
        type="file"
        multiple
        accept="image/jpeg,image/png,image/webp"
        onChange={upload}
        disabled={uploading}
      />
      {uploading && <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>Đang tải ảnh...</p>}
    </div>
  );
}

function DepositForm({ order, onDone }) {
  const toast = useToast();
  const { closeModal } = useModal();
  const min = Math.ceil(order.totalAmount * 0.1);
  const [amount, setAmount] = useState(Math.ceil(order.totalAmount * 0.2));
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await api(`/escrow/orders/${order.id}/deposit`, {
        method: 'POST',
        body: { amount: Number(amount), paymentMethod: 'SAFEPAY_WALLET' },
      });
      closeModal();
      toast('Đặt cọc thành công! 🎉', 'ok');
      onDone?.();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 6 }}>🔒 Đặt cọc SafePay</h3>
      <p className="muted" style={{ fontSize: 12.5, marginBottom: 14 }}>
        Tối thiểu 10% ({fmtVND(min)}). Tiền được giữ hộ, chỉ chuyển cho seller khi bạn xác nhận nhận hàng.
      </p>
      <div className="form-row">
        <label className="lbl">Số tiền cọc (đ)</label>
        <input
          className="input"
          type="number"
          min={min}
          max={order.totalAmount}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          required
        />
      </div>
      <div className="form-row">
        <label className="lbl">Phương thức</label>
        <select className="input" value="SAFEPAY_WALLET" disabled>
          <option value="SAFEPAY_WALLET">👛 Ví SafePay</option>
        </select>
        <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          MoMo, VietQR và chuyển khoản sẽ mở khi có webhook xác minh thanh toán.
        </p>
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang xử lý...' : 'Xác nhận đặt cọc'}
      </button>
    </form>
  );
}

function ShipForm({ order, onDone }) {
  const toast = useToast();
  const { closeModal } = useModal();
  const [trackingCode, setTrackingCode] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await api(`/orders/${order.id}/status`, {
        method: 'PATCH',
        body: { to: 'SHIPPING', trackingCode: trackingCode.trim() || undefined },
      });
      closeModal();
      toast('Đã cập nhật đơn hàng', 'ok');
      onDone?.();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>🚚 Gửi hàng</h3>
      <div className="form-row">
        <label className="lbl">Mã vận đơn</label>
        <input
          className="input"
          value={trackingCode}
          onChange={(event) => setTrackingCode(event.target.value)}
          placeholder="VD: VN682910482"
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang xử lý...' : 'Xác nhận'}
      </button>
    </form>
  );
}

function DisputeForm({ order, onDone }) {
  const toast = useToast();
  const { closeModal } = useModal();
  const [reason, setReason] = useState(DISPUTE_REASONS[0]);
  const [description, setDescription] = useState('');
  const [evidences, setEvidences] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (description.trim().length < 10) {
      toast('Mô tả vấn đề tối thiểu 10 ký tự', 'err');
      return;
    }
    setBusy(true);
    try {
      await api(`/disputes/orders/${order.id}/disputes`, {
        method: 'POST',
        body: { reason, description: description.trim(), evidences: evidenceList(evidences) },
      });
      closeModal();
      toast('Đã mở tranh chấp, admin sẽ xử lý trong 24h', 'ok');
      onDone?.();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>⚠️ Mở tranh chấp</h3>
      <div className="form-row">
        <label className="lbl">Lý do *</label>
        <select className="input" value={reason} onChange={(event) => setReason(event.target.value)}>
          {DISPUTE_REASONS.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </div>
      <EvidenceInput value={evidences} onChange={setEvidences} />
      <div className="form-row">
        <label className="lbl">Mô tả chi tiết *</label>
        <textarea
          className="input"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Mô tả vấn đề (tối thiểu 10 ký tự)"
          minLength={10}
          maxLength={2000}
          required
        />
      </div>
      <button className="btn btn-red" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang gửi...' : 'Gửi khiếu nại'}
      </button>
    </form>
  );
}

function ReviewForm({ order, onDone }) {
  const toast = useToast();
  const { closeModal } = useModal();
  const [type, setType] = useState('SELLER');
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await api(`/reviews/orders/${order.id}/reviews`, {
        method: 'POST',
        body: { rating: Number(rating), comment, type },
      });
      closeModal();
      toast('Cảm ơn bạn đã đánh giá!', 'ok');
      onDone?.();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>⭐ Đánh giá sau mua</h3>
      <div className="form-row">
        <label className="lbl">Nội dung đánh giá</label>
        <select className="input" value={type} onChange={(event) => setType(event.target.value)}>
          <option value="SELLER">Người bán</option>
          <option value="PRODUCT">Sản phẩm đã mua</option>
        </select>
      </div>
      <div className="form-row">
        <label className="lbl">Số sao</label>
        <select className="input" value={rating} onChange={(event) => setRating(event.target.value)}>
          <option value="5">★★★★★ (5)</option>
          <option value="4">★★★★ (4)</option>
          <option value="3">★★★ (3)</option>
          <option value="2">★★ (2)</option>
          <option value="1">★ (1)</option>
        </select>
      </div>
      <div className="form-row">
        <label className="lbl">Nhận xét</label>
        <textarea className="input" rows={3} value={comment} onChange={(event) => setComment(event.target.value)} maxLength={1000} />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang gửi...' : 'Gửi đánh giá'}
      </button>
    </form>
  );
}

function ReturnForm({ order, onDone }) {
  const toast = useToast();
  const { closeModal } = useModal();
  const [reason, setReason] = useState('');
  const [evidences, setEvidences] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (reason.trim().length < 10) {
      toast('Lý do tối thiểu 10 ký tự', 'err');
      return;
    }
    setBusy(true);
    try {
      await api(`/returns/orders/${order.id}`, {
        method: 'POST',
        body: { reason: reason.trim(), evidences: evidenceList(evidences) },
      });
      closeModal();
      toast('Đã gửi yêu cầu; đơn tạm dừng giải ngân', 'ok');
      onDone?.();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>Yêu cầu trả hàng</h3>
      <div className="form-row">
        <label className="lbl">Lý do (tối thiểu 10 ký tự)</label>
        <textarea
          className="input"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          minLength={10}
          maxLength={1000}
        />
      </div>
      <EvidenceInput value={evidences} onChange={setEvidences} />
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang gửi...' : 'Gửi yêu cầu'}
      </button>
    </form>
  );
}

function timelineLabel(status) {
  const direct = (ORDER_ST[status] || [])[0];
  if (direct) return direct;
  if (status.startsWith('RETURN_')) {
    return 'Trả hàng: ' + (WORKFLOW_LABELS[status.slice(7)] || status.slice(7));
  }
  return WORKFLOW_LABELS[status] || status;
}

function OrderDetailInner() {
  const { id } = useParams();
  const { user } = useSession();
  const toast = useToast();
  const { openModal } = useModal();
  const [busy, setBusy] = useState('');
  const { data: order, loading, error, reload } = useAsync(() => api('/orders/' + id), [id]);

  async function changeStatus(to, extra = {}) {
    const body = { to, ...extra };
    if (to === 'CANCELLED') {
      const note = window.prompt('Lý do huỷ:');
      if (note === null) return;
      body.note = note.trim() || undefined;
    }
    setBusy(to);
    try {
      await api(`/orders/${order.id}/status`, { method: 'PATCH', body });
      toast('Đã cập nhật đơn hàng', 'ok');
      reload();
    } catch (actionError) {
      toast(actionError.message, 'err');
    } finally {
      setBusy('');
    }
  }

  async function payRemainder() {
    if (!window.confirm(`Thanh toán ${fmtVND(order.remainingAmount)} từ ví vào ký quỹ?`)) return;
    setBusy('remainder');
    try {
      const result = await api(`/escrow/orders/${order.id}/pay-remainder`, { method: 'POST' });
      toast(result.message, 'ok');
      reload();
    } catch (actionError) {
      toast(actionError.message, 'err');
    } finally {
      setBusy('');
    }
  }

  async function confirmCod() {
    if (!window.confirm(`Bạn đã thực nhận ${fmtVND(order.remainingAmount)} COD? Thao tác được ghi vào lịch sử đơn.`)) {
      return;
    }
    setBusy('cod');
    try {
      const result = await api(`/orders/${order.id}/confirm-cod`, { method: 'POST' });
      toast(result.message, 'ok');
      reload();
    } catch (actionError) {
      toast(actionError.message, 'err');
    } finally {
      setBusy('');
    }
  }

  if (loading && !order) return <div className="wrap"><Loading /></div>;
  if (error) return <div className="wrap"><ErrorState error={error} /></div>;
  if (!order) return null;

  const isBuyer = order.buyerId === user?.id;
  const isSeller = order.sellerId === user?.id;
  const disabled = Boolean(busy);
  const actions = [];

  if (isBuyer && order.status === 'PENDING_DEPOSIT') {
    actions.push(
      <button
        key="deposit"
        className="btn btn-green"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => openModal(<DepositForm order={order} onDone={reload} />)}
      >
        🔒 Đặt cọc giữ hàng (SafePay)
      </button>,
    );
  }
  if (isBuyer && ['DEPOSITED', 'CONFIRMED', 'SHIPPING', 'DELIVERED'].includes(order.status) && order.remainingAmount > 0) {
    actions.push(
      <button
        key="remainder"
        className="btn btn-line"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={payRemainder}
      >
        Thanh toán còn lại qua ví: {fmtVND(order.remainingAmount)}
      </button>,
    );
  }
  if (isSeller && order.status === 'DELIVERED' && order.settlementMethod === 'COD' && order.remainingAmount > 0) {
    actions.push(
      <button
        key="cod"
        className="btn btn-line"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={confirmCod}
      >
        Xác nhận đã thu COD
      </button>,
    );
  }
  if (isBuyer && order.status === 'DELIVERED') {
    actions.push(
      <button
        key="complete"
        className="btn btn-green"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => changeStatus('COMPLETED')}
      >
        ✅ Xác nhận đã nhận hàng
      </button>,
    );
  }
  if (isBuyer && ['SHIPPING', 'DELIVERED', 'DEPOSITED', 'CONFIRMED'].includes(order.status)) {
    actions.push(
      <button
        key="dispute"
        className="btn btn-line"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => openModal(<DisputeForm order={order} onDone={reload} />)}
      >
        ⚠️ Mở tranh chấp / khiếu nại
      </button>,
    );
  }
  if (isBuyer && order.status === 'COMPLETED' && !order.review) {
    actions.push(
      <button
        key="review"
        className="btn btn-line"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => openModal(<ReviewForm order={order} onDone={reload} />)}
      >
        ⭐ Đánh giá người bán
      </button>,
    );
  }
  if (isSeller && order.status === 'DEPOSITED') {
    actions.push(
      <div key="confirm-cancel" style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <button
          className="btn btn-green"
          style={{ flex: 1 }}
          disabled={disabled}
          onClick={() => changeStatus('CONFIRMED')}
        >
          Xác nhận đơn
        </button>
        <button
          className="btn btn-line"
          style={{ flex: 1 }}
          disabled={disabled}
          onClick={() => changeStatus('CANCELLED')}
        >
          Huỷ
        </button>
      </div>,
    );
  }
  if (isSeller && order.status === 'CONFIRMED') {
    actions.push(
      <button
        key="ship"
        className="btn btn-green"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => openModal(<ShipForm order={order} onDone={reload} />)}
      >
        🚚 Xác nhận gửi hàng
      </button>,
    );
  }
  if (isSeller && order.status === 'SHIPPING') {
    actions.push(
      <button
        key="delivered"
        className="btn btn-green"
        style={{ width: '100%', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => changeStatus('DELIVERED')}
      >
        📬 Đã giao tới buyer
      </button>,
    );
  }
  if (order.status === 'PENDING_DEPOSIT') {
    actions.push(
      <button
        key="cancel"
        className="btn btn-line"
        style={{ width: '100%', color: 'var(--red)', borderColor: '#f3c1c1', marginBottom: 10 }}
        disabled={disabled}
        onClick={() => changeStatus('CANCELLED')}
      >
        Huỷ đơn
      </button>,
    );
  }

  const chatUser = isBuyer ? order.seller : isSeller ? order.buyer : null;
  const canReturn = isBuyer && ['DELIVERED', 'COMPLETED'].includes(order.status) && !order.dispute;

  return (
    <div className="wrap">
      <p>
        <Link className="btn btn-line btn-sm" to="/returns">
          Trả hàng và hoàn tiền →
        </Link>
      </p>
      <div className="crumbs">
        <Link to="/orders">Đơn hàng</Link> / <b style={{ color: 'var(--ink)' }}>#{order.code}</b>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 10 }}>
        <h1 style={{ fontSize: 23 }}>Đơn #{order.code}</h1>
        <StatusPill map={ORDER_ST} status={order.status} />
      </div>

      <div className="row2" style={{ gridTemplateColumns: '1.4fr 1fr', alignItems: 'start' }}>
        <div>
          <div className="card" style={{ padding: 20, marginBottom: 14 }}>
            <div style={{ display: 'flex', gap: 14 }}>
              <img
                src={img(order.listing?.images?.[0]?.url)}
                alt={order.listing?.title || 'Sản phẩm'}
                style={{ width: 110, height: 90, objectFit: 'cover', borderRadius: 10 }}
                onError={onImgError}
              />
              <div>
                <b>{order.listing?.title}</b>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Người bán: {order.seller?.fullName} · Người mua: {order.buyer?.fullName}
                </div>
                <div style={{ marginTop: 6 }}>
                  Giá chốt: <b style={{ color: 'var(--green-dark)' }}>{fmtVND(order.priceAgreed)}</b>
                </div>
              </div>
            </div>
            <div style={{ display: 'grid', gap: 8, fontSize: 13, marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="muted">Tiền cọc</span>
                <b>{fmtVND(order.depositAmount)}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="muted">Còn lại</span>
                <b>{fmtVND(order.remainingAmount)}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="muted">Ship</span>
                <b>{fmtVND(order.shippingFee)}</b>
              </div>
              <p className="muted">
                {order.settlementMethod === 'WALLET'
                  ? 'Phần còn lại thanh toán qua ví, tiền giữ trong SafePay.'
                  : 'Phần còn lại thu COD khi nhận hàng, gồm phí giao hàng. Người bán xác nhận thu tiền, người mua xác nhận hoàn tất.'}
              </p>
              {order.reservationExpiresAt && order.status === 'PENDING_DEPOSIT' && (
                <p className="badge b-amber">Giữ món đến {fmtDate(order.reservationExpiresAt)}</p>
              )}
              {order.codCollectedAt && <p className="badge b-green">Người bán đã khai báo thu COD</p>}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  borderTop: '1px dashed var(--line)',
                  paddingTop: 10,
                }}
              >
                <b>Tổng</b>
                <b style={{ fontSize: 18, color: 'var(--green-dark)' }}>{fmtVND(order.totalAmount)}</b>
              </div>
              {order.escrow && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="muted">Ký quỹ SafePay</span>
                  <span className={'pill ' + (order.escrow.status === 'HELD' ? 'p-warn' : 'p-ok')}>
                    {ESCROW_STATUS_NAMES[order.escrow.status] || order.escrow.status} · {fmtVND(order.escrow.amount)}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 15, marginBottom: 14 }}>Lịch sử đơn hàng</h3>
            <div className="tl">
              {(order.timeline || []).map((item, index) => (
                <div key={item.id || index} className={'tl-item ' + (index < (order.timeline || []).length ? 'done' : '')}>
                  <b style={{ fontSize: 12.5 }}>{timelineLabel(item.status)}</b>
                  <div style={{ fontSize: 13 }}>{item.note || ''}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{fmtDate(item.createdAt)}</div>
                </div>
              ))}
              {!order.timeline?.length && <p className="muted">Chưa có.</p>}
            </div>
          </div>
        </div>

        <div>
          <div className="card" style={{ padding: 20, marginBottom: 14 }}>
            <h3 style={{ fontSize: 15, marginBottom: 10 }}>📍 Giao nhận</h3>
            <div style={{ fontSize: 13 }}>
              <b>{order.shipName || ''}</b> · {order.shipPhone || ''}
              <div className="muted">{order.shipAddress || ''}</div>
              {order.trackingCode && (
                <div style={{ marginTop: 8 }}>
                  Mã vận đơn: <b>{order.trackingCode}</b>
                </div>
              )}
            </div>
          </div>

          <div className="card" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 15, marginBottom: 12 }}>Thao tác</h3>
            {actions.length > 0 ? actions : <p className="muted" style={{ fontSize: 13 }}>Không có thao tác khả dụng.</p>}
            {chatUser && (
              <Link
                className="btn btn-line"
                style={{ width: '100%', marginTop: 10 }}
                to={'/chat/' + chatUser.id}
              >
                💬 Chat với {isBuyer ? 'người bán' : 'người mua'}
              </Link>
            )}
          </div>
        </div>
      </div>

      {order.returnRequest ? (
        <section className="sect" style={{ marginTop: 18 }}>
          <h2>Tiến trình trả hàng</h2>
          <ReturnCard request={{ ...order.returnRequest, order }} onChanged={reload} />
        </section>
      ) : canReturn ? (
        <section className="sect" style={{ marginTop: 18 }}>
          <h2>Trả hàng</h2>
          <p className="muted">Trong 7 ngày sau khi giao; shop cần nhận lại hàng trước khi hoàn tiền.</p>
          <button
            type="button"
            className="btn btn-line"
            disabled={disabled}
            onClick={() => openModal(<ReturnForm order={order} onDone={reload} />)}
          >
            Yêu cầu trả hàng
          </button>
        </section>
      ) : null}
    </div>
  );
}

export default function OrderDetail() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <OrderDetailInner />;
}
