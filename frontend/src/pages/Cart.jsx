import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import {
  ErrorState,
  Loading,
  useAsync,
  useModal,
  useToast,
} from '../ui';
import { fmtVND, img, onImgError } from '../utils';

const PHONE = /^(\+84|0)(3|5|7|8|9)\d{8}$/;
const SHIP_FEE = 15000;

function CheckoutForm({ cart, promo, onDone }) {
  const { user } = useSession();
  const toast = useToast();
  const { closeModal } = useModal();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: user?.fullName || '',
    phone: user?.phone || '',
    address: '',
    note: '',
    paymentMethod: 'MOMO_QR',
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
    if (!cart.items.length) return toast('Giỏ hàng trống', 'err');

    setBusy(true);
    const orders = [];
    const errors = [];
    for (const item of cart.items) {
      try {
        const order = await api('/orders', {
          method: 'POST',
          body: {
            listingId: item.listingId,
            shipName: form.name.trim(),
            shipPhone: form.phone.trim(),
            shipAddress: form.address.trim(),
            note: form.note,
            paymentMethod: form.paymentMethod,
            promoCode: promo && cart.items.length === 1 ? promo.code : undefined,
          },
        });
        orders.push(order);
        await api('/cart/' + item.listingId, { method: 'DELETE' }).catch(() => {});
      } catch (error) {
        errors.push(item.listing?.title ? `${item.listing.title}: ${error.message}` : error.message);
      }
    }
    setBusy(false);

    if (!orders.length) {
      toast(errors[0] || 'Không tạo được đơn nào', 'err');
      return;
    }

    closeModal();
    onDone?.();
    toast(`Đã tạo ${orders.length} đơn hàng${errors.length ? `, ${errors.length} món lỗi` : ''} 🎉`, errors.length ? 'err' : 'ok');
    navigate(orders.length === 1 ? '/orders/' + orders[0].id : '/orders');
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 16 }}>💳 Xác nhận đặt hàng</h3>
      <div className="form-row">
        <label className="lbl">Người nhận *</label>
        <input className="input" value={form.name} onChange={set('name')} required />
      </div>
      <div className="form-row">
        <label className="lbl">Số điện thoại *</label>
        <input className="input" value={form.phone} onChange={set('phone')} inputMode="tel" required />
      </div>
      <div className="form-row">
        <label className="lbl">Địa chỉ giao hàng *</label>
        <input
          className="input"
          value={form.address}
          onChange={set('address')}
          placeholder="Số nhà, đường, phường/xã, tỉnh/thành"
          required
        />
      </div>
      <div className="form-row">
        <label className="lbl">Ghi chú</label>
        <textarea className="input" rows={2} value={form.note} onChange={set('note')} />
      </div>
      <div className="form-row">
        <label className="lbl">Thanh toán cọc qua</label>
        <select className="input" value={form.paymentMethod} onChange={set('paymentMethod')}>
          <option value="MOMO_QR">📷 MoMo / VietQR (demo)</option>
          <option value="SAFEPAY_WALLET">👛 Ví SafePay</option>
          <option value="BANK_TRANSFER">🏦 Chuyển khoản</option>
        </select>
      </div>
      {promo && (
        <p className="muted" style={{ fontSize: 12 }}>
          Mã {promo.promo?.code}: giảm {fmtVND(promo.discount)}
        </p>
      )}
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang tạo đơn...' : 'Xác nhận đặt hàng'}
      </button>
    </form>
  );
}

function CartInner() {
  const toast = useToast();
  const { openModal } = useModal();
  const [busy, setBusy] = useState(null);
  const [code, setCode] = useState('');
  const [promo, setPromo] = useState(null);
  const [promoError, setPromoError] = useState('');

  const { data: cart, loading, error, reload } = useAsync(() => api('/cart'), []);

  useEffect(() => {
    if (cart && cart.items.length !== 1) setPromo(null);
  }, [cart?.items.length]);

  async function removeItem(item) {
    setBusy(item.listingId);
    try {
      await api('/cart/' + item.listingId, { method: 'DELETE' });
      toast('Đã xoá khỏi giỏ', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  async function clearCart() {
    if (!window.confirm('Xoá toàn bộ giỏ hàng?')) return;
    setBusy('clear');
    try {
      await api('/cart', { method: 'DELETE' });
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  async function applyPromo() {
    if (!code.trim()) return;
    if (cart.items.length !== 1) {
      setPromoError('Mỗi tin tạo một đơn riêng; mã chỉ áp dụng khi giỏ có 1 món.');
      return;
    }
    setBusy('promo');
    setPromoError('');
    try {
      const result = await api('/promos/validate', {
        method: 'POST',
        body: { code: code.trim(), orderAmount: cart.total },
      });
      setPromo({ ...result, code: code.trim() });
      toast('Đã áp dụng mã khuyến mãi', 'ok');
    } catch (error) {
      setPromo(null);
      setPromoError(error.message);
    } finally {
      setBusy(null);
    }
  }

  if (loading && !cart) return <div className="wrap"><Loading /></div>;
  if (error) return <div className="wrap"><ErrorState error={error} /></div>;
  if (!cart) return null;

  const discount = cart.items.length === 1 && promo ? promo.discount : 0;
  const estimated = Math.max(0, cart.total - discount) + SHIP_FEE * cart.items.length;

  return (
    <div className="wrap">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, gap: 12, flexWrap: 'wrap' }}>
        <h1 style={{ fontSize: 23 }}>🛒 Giỏ hàng ({cart.count})</h1>
        {cart.count > 0 && (
          <button className="btn btn-line btn-sm" disabled={Boolean(busy)} onClick={clearCart}>
            {busy === 'clear' ? 'Đang xoá...' : 'Xoá tất cả'}
          </button>
        )}
      </div>

      {cart.items.length ? (
        <div className="row2" style={{ gridTemplateColumns: '1.6fr 1fr', alignItems: 'start' }}>
          <div>
            {cart.items.map((item) => {
              const listing = item.listing;
              if (!listing) return null;
              return (
                <div
                  key={item.listingId}
                  className="card"
                  style={{ padding: 16, marginBottom: 12, display: 'flex', gap: 14, alignItems: 'center' }}
                >
                  <Link to={'/listing/' + listing.id}>
                    <img
                      src={img(listing.images?.[0]?.url)}
                      alt={listing.title}
                      style={{ width: 110, height: 88, objectFit: 'cover', borderRadius: 10 }}
                      onError={onImgError}
                    />
                  </Link>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Link to={'/listing/' + listing.id} style={{ fontWeight: 700 }}>
                      {listing.title}
                    </Link>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {/* Mỗi tin là độc nhất; backend không có cột số lượng. */}
                      {listing.seller?.fullName || ''} · {listing.category?.name || ''} · SL: 1
                    </div>
                    <div style={{ marginTop: 6, fontWeight: 800, color: 'var(--green-dark)', fontSize: 16 }}>
                      {listing.isFree ? '🎁 0đ' : fmtVND(listing.price)}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-line btn-sm"
                    style={{ color: 'var(--red)' }}
                    disabled={Boolean(busy)}
                    onClick={() => removeItem(item)}
                  >
                    {busy === item.listingId ? 'Đang xoá...' : '✕ Xoá'}
                  </button>
                </div>
              );
            })}
          </div>

          <div className="card" style={{ padding: 22, position: 'sticky', top: 90 }}>
            <h3 style={{ marginBottom: 14 }}>Tổng đơn hàng</h3>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="muted">Tạm tính ({cart.count} món)</span>
              <b>{fmtVND(cart.total)}</b>
            </div>
            {discount > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span className="muted">Giảm giá</span>
                <b style={{ color: 'var(--green-dark)' }}>-{fmtVND(discount)}</b>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="muted">Phí ship ({cart.count} món)</span>
              <b>{fmtVND(SHIP_FEE * cart.count)}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, borderTop: '1px dashed var(--line)', paddingTop: 10 }}>
              <span>Tổng dự kiến</span>
              <b style={{ color: 'var(--green-dark)', fontSize: 18 }}>{fmtVND(estimated)}</b>
            </div>

            <div className="form-row">
              <label className="lbl">Mã khuyến mãi</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  className="input"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="Nhập mã"
                  maxLength={30}
                />
                <button
                  type="button"
                  className="btn btn-line btn-sm"
                  disabled={Boolean(busy) || cart.items.length !== 1}
                  onClick={applyPromo}
                >
                  {busy === 'promo' ? '...' : 'Áp dụng'}
                </button>
              </div>
              {cart.items.length !== 1 && (
                <p className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
                  Mã chỉ áp dụng khi giỏ có 1 món vì mỗi tin tạo một đơn riêng.
                </p>
              )}
              {promoError && <p style={{ color: 'var(--red)', fontSize: 12, marginTop: 6 }}>{promoError}</p>}
              {promo && (
                <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                  {promo.promo?.name || promo.promo?.code} · giảm {fmtVND(promo.discount)}
                </p>
              )}
            </div>

            <button
              type="button"
              className="btn btn-green"
              style={{ width: '100%', padding: 14 }}
              disabled={Boolean(busy)}
              onClick={() => openModal(<CheckoutForm cart={cart} promo={promo} onDone={reload} />)}
            >
              💳 Đặt hàng ({cart.count} món)
            </button>
            <p className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
              Mỗi tin sẽ tạo 1 đơn riêng (khác người bán). Thanh toán cọc qua SafePay sau khi đặt.
            </p>
          </div>
        </div>
      ) : (
        <div className="empty">
          <div className="e">🛒</div>
          <p>Giỏ hàng trống.</p>
          <br />
          <Link className="btn btn-green" to="/">
            Tiếp tục mua sắm
          </Link>
        </div>
      )}
    </div>
  );
}

export default function Cart() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <CartInner />;
}
