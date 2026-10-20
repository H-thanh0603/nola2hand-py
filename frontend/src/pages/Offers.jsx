import { useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { OFFER_ST } from '../constants';
import { useSession } from '../session';
import {
  ErrorState,
  Loading,
  Pagination,
  StatusPill,
  useAsync,
  useModal,
  useToast,
} from '../ui';
import { fmtDate, fmtVND, img, onImgError, qs } from '../utils';

const PHONE = /^(\+84|0)(3|5|7|8|9)\d{8}$/;
const STATUSES = Object.keys(OFFER_ST);

const isExpired = (offer) => offer.expiresAt && new Date(offer.expiresAt) <= new Date();
const displayStatus = (offer) =>
  offer.status === 'PENDING' && isExpired(offer) ? 'EXPIRED' : offer.status;

function BuyOfferForm({ offer, onDone }) {
  const { user } = useSession();
  const toast = useToast();
  const { closeModal } = useModal();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: user?.fullName || '',
    phone: user?.phone || '',
    address: '',
    note: '',
  });
  const [busy, setBusy] = useState(false);

  function set(key) {
    return (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!form.name.trim()) return toast('Nhập tên người nhận', 'err');
    if (!PHONE.test(form.phone.trim())) return toast('SĐT giao hàng chưa đúng (VD: 0987654321)', 'err');
    if (!form.address.trim()) return toast('Nhập địa chỉ giao hàng', 'err');
    setBusy(true);
    try {
      const order = await api('/orders', {
        method: 'POST',
        body: {
          listingId: offer.listingId,
          offerId: offer.id,
          shipName: form.name.trim(),
          shipPhone: form.phone.trim(),
          shipAddress: form.address.trim(),
          note: form.note,
          paymentMethod: 'MOMO_QR',
        },
      });
      closeModal();
      toast('Tạo đơn thành công!', 'ok');
      onDone?.();
      navigate('/orders/' + order.id);
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 16 }}>🛒 Mua với giá đã thương lượng</h3>
      <p className="muted" style={{ fontSize: 13, marginBottom: 12 }}>{fmtVND(offer.offeredPrice)}</p>
      <div className="form-row">
        <label className="lbl">Người nhận *</label>
        <input className="input" value={form.name} onChange={set('name')} required />
      </div>
      <div className="form-row">
        <label className="lbl">Số điện thoại *</label>
        <input className="input" value={form.phone} onChange={set('phone')} inputMode="tel" required />
      </div>
      <div className="form-row">
        <label className="lbl">Địa chỉ *</label>
        <input className="input" value={form.address} onChange={set('address')} required />
      </div>
      <div className="form-row">
        <label className="lbl">Ghi chú</label>
        <textarea className="input" rows={2} value={form.note} onChange={set('note')} />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang tạo đơn...' : 'Tạo đơn hàng'}
      </button>
    </form>
  );
}

function OffersInner() {
  const { hasRole } = useSession();
  const seller = hasRole('SELLER');
  const [params, setParams] = useSearchParams();
  const tab = seller && params.get('tab') === 'inbox' ? 'inbox' : 'mine';
  const status = params.get('status') || '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const toast = useToast();
  const { openModal } = useModal();
  const [busy, setBusy] = useState(null);

  const { data, loading, error, reload } = useAsync(
    () => api(`/offers/${tab === 'inbox' ? 'inbox' : 'mine'}?` + qs({ page, limit: 10, status })),
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

  async function act(offer, action) {
    setBusy(offer.id);
    try {
      await api('/offers/' + offer.id, { method: 'PATCH', body: { action } });
      toast('Đã cập nhật', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 16 }}>
        💰 {tab === 'inbox' ? 'Yêu cầu trả giá nhận được' : 'Yêu cầu trả giá của tôi'}
      </h1>

      <div className="toolbar">
        {seller && (
          <>
            <button
              type="button"
              className={'btn btn-sm ' + (tab === 'mine' ? 'btn-green' : 'btn-line')}
              onClick={() => setParam('tab', 'mine')}
            >
              Tôi gửi
            </button>
            <button
              type="button"
              className={'btn btn-sm ' + (tab === 'inbox' ? 'btn-green' : 'btn-line')}
              onClick={() => setParam('tab', 'inbox')}
            >
              Tôi nhận
            </button>
          </>
        )}
        <select
          className="input"
          aria-label="Lọc trạng thái trả giá"
          value={status}
          onChange={(event) => setParam('status', event.target.value)}
        >
          <option value="">Tất cả trạng thái</option>
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {OFFER_ST[item][0]}
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
          {(data?.data || []).map((offer) => {
            const expired = isExpired(offer);
            const canBuy = offer.status === 'ACCEPTED' && !expired;
            const canCancel = offer.status === 'PENDING' && !expired && tab === 'mine';
            const canHandle = offer.status === 'PENDING' && !expired && tab === 'inbox';
            return (
              <div
                key={offer.id}
                className="card"
                style={{
                  padding: 18,
                  marginBottom: 12,
                  display: 'flex',
                  gap: 16,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                {tab === 'mine' && (
                  <img
                    src={img(offer.listing?.images?.[0]?.url)}
                    alt={offer.listing?.title || 'Tin đăng'}
                    style={{ width: 110, height: 88, objectFit: 'cover', borderRadius: 10 }}
                    onError={onImgError}
                  />
                )}
                <div style={{ flex: 1, minWidth: 180 }}>
                  <b>{offer.listing?.title || 'Tin không còn tồn tại'}</b>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {tab === 'inbox' ? 'Người mua: ' + (offer.buyer?.fullName || '') : 'Người bán: ' + (offer.listing?.seller?.fullName || '')}
                  </div>
                  {offer.message && <div style={{ fontSize: 13, marginTop: 4 }}>{offer.message}</div>}
                  <div style={{ marginTop: 6 }}>
                    {tab === 'inbox' && offer.listing?.price != null && (
                      <span className="muted">Giá niêm yết {fmtVND(offer.listing.price)} → </span>
                    )}
                    Đề xuất: <b style={{ color: 'var(--green-dark)', fontSize: 17 }}>{fmtVND(offer.offeredPrice)}</b>{' '}
                    <StatusPill map={OFFER_ST} status={displayStatus(offer)} />
                  </div>
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 5 }}>
                    {offer.status === 'PENDING' && expired ? 'Đã hết hạn' : 'Hết hạn'} {fmtDate(offer.expiresAt)}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexDirection: 'column' }}>
                  {canBuy && (
                    <button
                      type="button"
                      className="btn btn-green btn-sm"
                      onClick={() => openModal(<BuyOfferForm offer={offer} onDone={reload} />)}
                    >
                      🛒 Mua với giá này
                    </button>
                  )}
                  {canCancel && (
                    <button
                      type="button"
                      className="btn btn-line btn-sm"
                      disabled={Boolean(busy)}
                      onClick={() => act(offer, 'CANCEL')}
                    >
                      {busy === offer.id ? 'Đang xử lý...' : 'Huỷ'}
                    </button>
                  )}
                  {canHandle && (
                    <>
                      <button
                        type="button"
                        className="btn btn-green btn-sm"
                        disabled={Boolean(busy)}
                        onClick={() => act(offer, 'ACCEPT')}
                      >
                        Đồng ý
                      </button>
                      <button
                        type="button"
                        className="btn btn-line btn-sm"
                        disabled={Boolean(busy)}
                        onClick={() => act(offer, 'REJECT')}
                      >
                        Từ chối
                      </button>
                    </>
                  )}
                  {tab === 'mine' && offer.listingId && (
                    <Link className="btn btn-line btn-sm" to={'/listing/' + offer.listingId}>
                      Xem tin
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
          {!data?.data?.length && (
            <div className="empty">
              <div className="e">💰</div>
              {tab === 'inbox' ? 'Chưa có đề nghị trả giá.' : 'Chưa có yêu cầu nào.'}
            </div>
          )}
          <Pagination meta={data?.meta} onPage={(value) => setParam('page', value)} />
        </>
      )}
    </div>
  );
}

export default function Offers() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <OffersInner />;
}
