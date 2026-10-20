import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import { CONDITION_NAMES, DELIVERY_NAMES } from '../constants';
import { fmtDate, fmtVND, img, onImgError } from '../utils';
import { toggleComparison, useComparison } from '../compare';
import {
  Avatar,
  ErrorState,
  Icon,
  ListingCard,
  Loading,
  useAsync,
  useModal,
  useToast,
} from '../ui';

const validPhone = (value) =>
  /^(\+84|0)(3|5|7|8|9)\d{8}$/.test((value || '').trim());

function OfferModal({ listing }) {
  const { closeModal } = useModal();
  const toast = useToast();
  const navigate = useNavigate();
  const [offeredPrice, setOfferedPrice] = useState('');
  const [shipMethod, setShipMethod] = useState('NOLA_SHIP');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const price = Number(offeredPrice);
    if (!Number.isFinite(price) || price < 1000) {
      toast('Giá đề xuất tối thiểu 1.000 đ', 'err');
      return;
    }
    setBusy(true);
    try {
      await api('/listings/' + listing.id + '/offers', {
        method: 'POST',
        body: { offeredPrice: price, message, shipMethod },
      });
      closeModal();
      toast('Đã gửi yêu cầu trả giá!', 'ok');
      navigate('/offers');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 6 }}>💰 Trả giá</h3>
      <p className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
        {listing.title}
        <br />
        Giá niêm yết: <b>{fmtVND(listing.price)}</b>
      </p>
      <div className="form-row">
        <label className="lbl" htmlFor="off-price">
          Giá đề xuất (đ)
        </label>
        <input
          className="input"
          id="off-price"
          type="number"
          min="1000"
          placeholder="vd: 450000"
          value={offeredPrice}
          onChange={(event) => setOfferedPrice(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="off-ship">
          Nhận hàng
        </label>
        <select
          className="input"
          id="off-ship"
          value={shipMethod}
          onChange={(event) => setShipMethod(event.target.value)}
        >
          <option value="NOLA_SHIP">🚚 Giao hàng NoLa</option>
          <option value="MEETUP">🤝 Gặp mặt trực tiếp</option>
        </select>
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="off-msg">
          Lời nhắn
        </label>
        <textarea
          className="input"
          id="off-msg"
          rows="2"
          placeholder="Nhắn gửi người bán..."
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang gửi...' : 'Gửi yêu cầu (hiệu lực 24h)'}
      </button>
    </form>
  );
}

function BuyModal({ listing }) {
  const { closeModal } = useModal();
  const { user } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState(user?.fullName || '');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (!name.trim()) {
      toast('Nhập tên người nhận', 'err');
      return;
    }
    if (!validPhone(phone)) {
      toast('SĐT giao hàng chưa đúng (VD: 0987654321)', 'err');
      return;
    }
    if (!address.trim()) {
      toast('Nhập địa chỉ giao hàng', 'err');
      return;
    }
    setBusy(true);
    try {
      const order = await api('/orders', {
        method: 'POST',
        body: {
          listingId: listing.id,
          shipName: name,
          shipPhone: phone,
          shipAddress: address,
          note,
          paymentMethod: 'MOMO_QR',
        },
      });
      closeModal();
      toast('Tạo đơn thành công!', 'ok');
      navigate('/orders/' + order.id);
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 16 }}>🛒 Xác nhận mua</h3>
      <div className="form-row">
        <label className="lbl" htmlFor="od-name">
          Người nhận *
        </label>
        <input
          className="input"
          id="od-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="od-phone">
          Số điện thoại *
        </label>
        <input
          className="input"
          id="od-phone"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="od-addr">
          Địa chỉ giao hàng *
        </label>
        <input
          className="input"
          id="od-addr"
          placeholder="Số nhà, đường, phường/xã, tỉnh/thành"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="od-qty">
          Số lượng
        </label>
        <input className="input" id="od-qty" value="1" readOnly />
        <p className="muted" style={{ fontSize: 11, marginTop: 4 }}>
          Mỗi tin đăng là một món đồ duy nhất.
        </p>
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="od-note">
          Ghi chú
        </label>
        <textarea
          className="input"
          id="od-note"
          rows="2"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang tạo đơn...' : 'Tạo đơn hàng'}
      </button>
    </form>
  );
}

function ReportModal({ listing }) {
  const { closeModal } = useModal();
  const toast = useToast();
  const [reason, setReason] = useState('Thông tin sai sự thật');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await api('/reports', {
        method: 'POST',
        body: {
          targetType: 'LISTING',
          targetId: listing.id,
          targetUserId: listing.sellerId,
          reason,
          description,
        },
      });
      closeModal();
      toast(result.message || 'Đã gửi báo cáo, cảm ơn bạn', 'ok');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 6 }}>🚩 Báo cáo tin đăng</h3>
      <p className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
        {listing.title}
      </p>
      <div className="form-row">
        <label className="lbl" htmlFor="report-reason">
          Lý do
        </label>
        <select
          className="input"
          id="report-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        >
          <option>Thông tin sai sự thật</option>
          <option>Hàng giả, hàng nhái</option>
          <option>Giá hoặc nội dung lừa đảo</option>
          <option>Nội dung không phù hợp</option>
          <option>Khác</option>
        </select>
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="report-desc">
          Mô tả thêm
        </label>
        <textarea
          className="input"
          id="report-desc"
          rows="3"
          maxLength="1000"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang gửi...' : 'Gửi báo cáo'}
      </button>
    </form>
  );
}

export default function Listing() {
  const { id } = useParams();
  const { token, user } = useSession();
  const navigate = useNavigate();
  const toast = useToast();
  const { openModal } = useModal();
  const compareIds = useComparison();
  const [imageIndex, setImageIndex] = useState(0);
  const [saved, setSaved] = useState(false);

  const { data: listing, loading, error } = useAsync(
    () => api('/listings/' + id, { auth: false }),
    [id],
  );

  const { data: extra } = useAsync(async () => {
    const [related, fields, history] = await Promise.all([
      api('/listings/' + id + '/related?limit=4', { auth: false }).catch(() => ({
        items: [],
      })),
      api('/categories/specifications', { auth: false }).catch(() => ({})),
      api('/listings/' + id + '/price-history', { auth: false }).catch(() => []),
    ]);
    return {
      related: related.items || [],
      fields: fields || {},
      history: Array.isArray(history) ? history : [],
    };
  }, [id]);

  useEffect(() => {
    setImageIndex(0);
    setSaved(false);
  }, [id]);

  if (loading && !listing) return <Loading />;
  if (error) return <ErrorState error={error} />;
  if (!listing) return null;

  const images = listing.images || [];
  const mainImage = images[imageIndex] || images[0];
  const compared = compareIds.includes(listing.id);
  const specLabels = extra?.fields?.[listing.category?.slug] || {};

  function requireLogin() {
    if (!token) {
      navigate('/login');
      return false;
    }
    return true;
  }

  async function toggleFav() {
    if (!requireLogin()) return;
    try {
      const result = await api('/listings/' + listing.id + '/favorite', {
        method: 'POST',
      });
      setSaved(result.favorited);
      toast(result.favorited ? 'Đã lưu tin 🤍' : 'Đã bỏ lưu', 'ok');
    } catch (requestError) {
      toast(requestError.message, 'err');
    }
  }

  function startChat() {
    if (!requireLogin()) return;
    if (listing.seller?.id === user?.id) {
      toast('Đây là tin của bạn', 'err');
      return;
    }
    navigate('/chat/' + listing.seller.id + '?listingId=' + listing.id);
  }

  function openOffer() {
    if (!requireLogin()) return;
    openModal(<OfferModal listing={listing} />);
  }

  function buyNow() {
    if (!requireLogin()) return;
    openModal(<BuyModal listing={listing} />);
  }

  function openReport() {
    if (!requireLogin()) return;
    openModal(<ReportModal listing={listing} />);
  }

  async function addToCart() {
    if (!requireLogin()) return;
    try {
      const result = await api('/cart', {
        method: 'POST',
        body: { listingId: listing.id },
      });
      toast(result.message + ' 🛒', 'ok');
    } catch (requestError) {
      toast(requestError.message, 'err');
    }
  }

  function compare() {
    const result = toggleComparison(listing.id);
    if (result.limit) {
      toast('Chỉ so sánh tối đa 3 sản phẩm. Bỏ chọn một món trước.', 'err');
      return;
    }
    toast(result.added ? 'Đã thêm vào so sánh' : 'Đã bỏ khỏi so sánh', 'ok');
  }

  return (
    <div className="wrap">
      <div className="crumbs">
        <Link to="/">Trang chủ</Link> /{' '}
        <Link
          to={
            listing.category?.slug
              ? '/category/' + listing.category.slug
              : '/'
          }
        >
          {listing.category?.name || ''}
        </Link>{' '}
        / <b style={{ color: 'var(--ink)' }}>{listing.title.slice(0, 40)}...</b>
      </div>

      <div className="card" style={{ padding: 28 }}>
        <div className="dgrid">
          <div className="gallery">
            <img
              className="main"
              alt={listing.title}
              src={img(mainImage?.url)}
              onError={onImgError}
            />
            <div className="thumbs">
              {images.map((image, index) => (
                <img
                  key={image.id || image.url}
                  src={img(image.url)}
                  alt={listing.title + ' — ảnh ' + (index + 1)}
                  className={index === imageIndex ? 'on' : ''}
                  onClick={() => setImageIndex(index)}
                  onError={onImgError}
                />
              ))}
            </div>
            <div
              className="card"
              style={{ padding: 20, marginTop: 18, boxShadow: 'none' }}
            >
              <h3 style={{ fontSize: 15, marginBottom: 10 }}>
                📝 Mô tả chi tiết
              </h3>
              <p style={{ fontSize: 13.5, whiteSpace: 'pre-wrap' }}>
                {listing.description}
              </p>
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {listing.isVerified && (
                <span className="badge b-green">✨ Đã kiểm định</span>
              )}
              <span className="badge b-gray">
                <Icon name="eye" /> {listing.views || 0} lượt xem
              </span>
              {CONDITION_NAMES[listing.condition] && (
                <span className="badge b-gray">
                  {CONDITION_NAMES[listing.condition]}
                </span>
              )}
            </div>
            <h1 style={{ fontSize: 22, margin: '12px 0 6px' }}>
              {listing.title}
            </h1>
            <div
              style={{
                fontSize: 28,
                fontWeight: 800,
                color: 'var(--green-dark)',
              }}
            >
              {listing.isFree ? '🎁 Cho tặng 0đ' : fmtVND(listing.price)}
            </div>

            <div
              className="card"
              style={{
                padding: 16,
                display: 'flex',
                gap: 12,
                alignItems: 'center',
                margin: '16px 0',
                boxShadow: 'none',
              }}
            >
              <Avatar user={listing.seller} size={48} />
              <div style={{ flex: 1 }}>
                <b>{listing.seller?.fullName || ''}</b>{' '}
                {listing.seller?.emailVerifiedAt && (
                  <span className="badge b-blue">✓ Email đã xác nhận</span>
                )}{' '}
                {listing.seller?.idVerified && (
                  <span className="badge b-green">✓ Danh tính đã duyệt</span>
                )}
                <Link
                  className="text-link shop-profile-link"
                  to={'/shop/' + listing.sellerId}
                >
                  Xem hồ sơ uy tín <Icon name="arrow" />
                </Link>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 10,
                marginBottom: 12,
              }}
            >
              <button
                className={'btn btn-line' + (saved ? ' is-saved' : '')}
                onClick={toggleFav}
                aria-pressed={saved}
              >
                <Icon name="heart" /> Lưu tin
              </button>
              <button className="btn btn-dark" onClick={startChat}>
                <Icon name="chat" /> Chat
              </button>
            </div>
            <button
              className="btn btn-green"
              style={{ width: '100%', padding: 14 }}
              onClick={openOffer}
            >
              💰 Trả giá
            </button>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 10,
                marginTop: 10,
              }}
            >
              <button
                className="btn btn-line"
                style={{ padding: 14 }}
                onClick={addToCart}
              >
                🛒 Thêm vào giỏ
              </button>
              <button
                className="btn btn-green"
                style={{ padding: 14 }}
                onClick={buyNow}
              >
                Mua ngay
              </button>
            </div>
            <div
              style={{
                display: 'flex',
                gap: 8,
                marginTop: 10,
                flexWrap: 'wrap',
              }}
            >
              <button
                className={'btn btn-line btn-sm' + (compared ? ' is-saved' : '')}
                onClick={compare}
              >
                ⇄ So sánh
              </button>
              <button className="btn btn-line btn-sm" onClick={openReport}>
                🚩 Báo cáo tin
              </button>
            </div>
            <div
              style={{
                display: 'flex',
                gap: 8,
                marginTop: 12,
                background: 'var(--green-softer)',
                borderRadius: 10,
                padding: 12,
              }}
            >
              <span>
                <Icon name="shield" />
              </span>
              <div className="muted" style={{ fontSize: 12 }}>
                <b style={{ color: 'var(--ink)' }}>SafePay:</b> tiền được giữ
                hộ đến khi bạn nhận hàng & đồng kiểm ưng ý.
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="row2" style={{ marginTop: 20 }}>
        <div className="sect">
          <h2>Hồ sơ tình trạng</h2>
          <p className="muted">
            Do người bán cung cấp · {listing.city || 'Chưa ghi địa điểm'} ·{' '}
            {DELIVERY_NAMES[listing.deliveryMethod] || ''}
          </p>
          <dl className="specification-list">
            {Object.entries(listing.specifications || {}).map(([key, value]) => (
              <div key={key} style={{ display: 'contents' }}>
                <dt>{specLabels[key] || key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          {!Object.keys(listing.specifications || {}).length && (
            <p className="muted">Người bán chưa bổ sung thông số.</p>
          )}
        </div>
        <div className="sect">
          <h2>Lịch sử giá</h2>
          <p className="muted">
            Giá do người bán điều chỉnh; không phải giá giao dịch đã chốt.
          </p>
          <div className="history-list">
            {extra?.history?.length ? (
              extra.history.map((point) => (
                <div key={point.id}>
                  <span>{fmtDate(point.createdAt)}</span>
                  <b>{fmtVND(point.price)}</b>
                </div>
              ))
            ) : (
              <p>Chưa có lịch sử giá.</p>
            )}
          </div>
        </div>
      </div>

      {extra?.related?.length ? (
        <section style={{ marginTop: 26 }}>
          <h2 style={{ fontSize: 18, marginBottom: 14 }}>
            💡 Có thể bạn cũng thích
          </h2>
          <div className="pgrid">
            {extra.related.map((item) => (
              <ListingCard key={item.id} listing={item} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
