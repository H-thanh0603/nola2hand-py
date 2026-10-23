import { Fragment, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import Chart from 'chart.js/auto';
import { api, IMAGE_TYPES, MAX_IMAGE_BYTES, uploadFile } from '../api';
import { useSession } from '../session';
import { useCategories } from '../categories';
import {
  ErrorState,
  Icon,
  Loading,
  Pagination,
  StatusPill,
  useAsync,
  useModal,
  useToast,
} from '../ui';
import {
  CONDITION_NAMES,
  DELIVERY_NAMES,
  LISTING_STATUS_NAMES,
  OFFER_ST,
  ORDER_ST,
} from '../constants';
import { fmtDate, fmtVND, img, onImgError } from '../utils';
import { VIETNAM_PROVINCES } from '../provinces';

const TABS = [
  ['dashboard', 'Tổng quan', 'grid'],
  ['listings', 'Tin đăng', 'box'],
  ['new', 'Đăng tin mới', 'plus'],
  ['offers', 'Trả giá', 'chat'],
  ['insights', 'Phân tích đánh giá', 'star'],
  ['orders', 'Đơn bán', 'orders'],
];

function ReviewInsights() {
  const { data, error, loading } = useAsync(() => api('/reviews/insights'), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  const sentiments = {
    POSITIVE: 'Tích cực',
    NEUTRAL: 'Trung lập',
    NEGATIVE: 'Tiêu cực',
  };
  return (
    <section className="sect">
      <h2>Phân tích đánh giá</h2>
      <p className="muted">
        Tối đa 500 đánh giá mới nhất; nhãn ước lượng không thay thế nội dung gốc.
      </p>
      <div className="stat-grid">
        {data.sentiments.map((item) => (
          <div className="stat" key={item.sentiment}>
            <div className="t">{sentiments[item.sentiment] || item.sentiment}</div>
            <div className="v">{item.count}</div>
          </div>
        ))}
      </div>
      <p>
        Điểm trung bình {data.averageRating.toFixed(1)}/5 · {data.sampleSize} đánh giá ·{' '}
        {data.sources.ai} nhãn AI, {data.sources.local} nhãn cục bộ.
      </p>
      <h3>Vấn đề thường gặp</h3>
      {data.issues.map((issue) => (
        <p key={issue.name}>
          {issue.name}: <b>{issue.count}</b>
        </p>
      ))}
    </section>
  );
}

const LISTING_PILLS = Object.fromEntries(
  Object.entries(LISTING_STATUS_NAMES).map(([status, label]) => [
    status,
    [
      label,
      status === 'ACTIVE'
        ? 'p-ok'
        : status === 'PENDING_REVIEW'
          ? 'p-warn'
          : status === 'REJECTED'
            ? 'p-bad'
            : status === 'RESERVED'
              ? 'p-info'
              : 'p-mut',
    ],
  ]),
);

const BLOCKED_EDIT = ['RESERVED', 'SOLD_OUT', 'DELETED'];
const MAX_IMAGES = 10;

const dayStr = (date) => date.toISOString().slice(0, 10);
const defaultRange = () => ({
  from: dayStr(new Date(Date.now() - 30 * 86400000)),
  to: dayStr(new Date()),
});

/* ---------------- dashboard ---------------- */

function Stat({ label, value, accent = false }) {
  return (
    <div className="stat">
      <div className="t">{label}</div>
      <div className="v" style={accent ? { color: 'var(--green-dark)' } : undefined}>
        {value}
      </div>
    </div>
  );
}

function RevenueChart() {
  const [form, setForm] = useState(defaultRange);
  const [range, setRange] = useState(form);
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  const { loading, data, error } = useAsync(
    () => api(`/seller/charts/revenue?from=${range.from}&to=${range.to}`),
    [range.from, range.to],
  );

  useEffect(() => {
    if (!data) return undefined;
    Chart.defaults.font.family = "'Be Vietnam Pro', system-ui, sans-serif";
    Chart.defaults.color = '#718178';
    const values = data.data.map((row) => row.revenue);
    chartRef.current = new Chart(canvasRef.current, {
      type: 'bar',
      data: {
        labels: data.data.map((row) => row.date.slice(5)),
        datasets: [
          {
            label: 'Doanh thu (đ)',
            data: values,
            backgroundColor: '#087f5b',
            borderRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            grid: { display: false },
            ticks: { maxTicksLimit: 8, maxRotation: 0, font: { size: 10 } },
          },
          y: {
            beginAtZero: true,
            suggestedMax: values.some((value) => value > 0) ? undefined : 100000,
            grid: { color: '#eaf0ec' },
            border: { display: false },
            ticks: {
              maxTicksLimit: 5,
              callback: (value) =>
                value >= 1e6 ? value / 1e6 + 'tr' : value >= 1000 ? value / 1e3 + 'k' : value,
            },
          },
        },
      },
    });
    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [data]);

  const rows = data?.data || [];
  const totalRevenue = rows.reduce((sum, row) => sum + row.revenue, 0);
  const totalOrders = rows.reduce((sum, row) => sum + row.orders, 0);

  return (
    <div className="sect">
      <h2>📈 Doanh thu shop theo ngày</h2>
      <div className="toolbar">
        <label className="muted" htmlFor="sellerChart-from" style={{ alignSelf: 'center', fontSize: 13 }}>
          Từ ngày
        </label>
        <input
          type="date"
          className="input"
          id="sellerChart-from"
          value={form.from}
          onChange={(event) => setForm((value) => ({ ...value, from: event.target.value }))}
        />
        <label className="muted" htmlFor="sellerChart-to" style={{ alignSelf: 'center', fontSize: 13 }}>
          đến
        </label>
        <input
          type="date"
          className="input"
          id="sellerChart-to"
          value={form.to}
          onChange={(event) => setForm((value) => ({ ...value, to: event.target.value }))}
        />
        <button className="btn btn-green btn-sm" onClick={() => setRange(form)}>
          <Icon name="chart" /> Xem
        </button>
      </div>
      {error ? (
        <p role="alert" style={{ color: 'var(--red)' }}>
          {error.message}
        </p>
      ) : (
        <>
          <canvas ref={canvasRef} height="110" />
          {loading ? (
            <Loading label="Đang tải biểu đồ..." />
          ) : (
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              <Stat
                label={`Doanh thu (${range.from} → ${range.to})`}
                value={fmtVND(totalRevenue)}
                accent
              />
              <Stat label="Đơn hàng" value={totalOrders} />
              <Stat
                label="Thu ròng / đơn phát sinh"
                value={totalOrders ? fmtVND(Math.round(totalRevenue / totalOrders)) : '—'}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Dashboard() {
  const navigate = useNavigate();
  const { loading, data, error } = useAsync(() => api('/seller/dashboard'), []);

  if (loading) return <Loading label="Đang tải tổng quan..." />;
  if (error) return <ErrorState error={error} />;

  const kpis = data.kpis;
  const activeListings =
    (data.listingStatus.find((row) => row.status === 'ACTIVE') || {})._count || 0;

  return (
    <>
      <div className="stat-grid">
        <Stat label="Thu ròng ví 7 ngày (không gồm COD)" value={fmtVND(kpis.weeklyRevenue)} accent />
        <Stat label="Đơn chờ xử lý" value={kpis.pendingOrders} />
        <Stat label="Tổng lượt xem" value={kpis.totalViews} />
        <Stat label="Tin đang bán" value={activeListings} />
      </div>
      <div className="stat-grid">
        <Stat
          label="Tổng giá trị đơn đang thực hiện/hoàn tất"
          value={fmtVND(kpis.orderValue)}
        />
        <Stat label="Tiền đang giữ trong ký quỹ" value={fmtVND(kpis.escrowHeld)} />
      </div>
      <div className="row2" style={{ alignItems: 'start' }}>
        <div className="sect">
          <h2>🧾 Đơn bán gần đây</h2>
          {data.recentOrders.map((order) => (
            <button
              key={order.id}
              type="button"
              onClick={() => navigate(`/orders/${order.id}`)}
              style={{
                display: 'flex',
                width: '100%',
                justifyContent: 'space-between',
                padding: '10px 0',
                border: 0,
                borderBottom: '1px solid #f0f3f1',
                background: 'none',
                fontFamily: 'inherit',
                fontSize: 13,
                textAlign: 'left',
                cursor: 'pointer',
              }}
            >
              <span>
                <b>#{order.code}</b> <StatusPill map={ORDER_ST} status={order.status} />
              </span>
              <b>{fmtVND(order.totalAmount)}</b>
            </button>
          ))}
          {!data.recentOrders.length && <p className="muted">Chưa có.</p>}
        </div>
        <div className="sect">
          <h2>🔥 Sản phẩm nổi bật</h2>
          {data.topProducts.map((listing) => (
            <div
              key={listing.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '10px 0',
                borderBottom: '1px solid #f0f3f1',
                fontSize: 13,
              }}
            >
              <span>{listing.title}</span>
              <span className="muted">
                👁 {listing.views} · 🧾 {listing.orders} đơn
              </span>
            </div>
          ))}
          {!data.topProducts.length && <p className="muted">Chưa có.</p>}
        </div>
      </div>
      <RevenueChart />
    </>
  );
}

/* ---------------- listings ---------------- */

function SellerListings() {
  const toast = useToast();
  const { openModal, closeModal } = useModal();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(null);
  const { loading, data, error, reload } = useAsync(
    () =>
      api(
        `/seller/listings?limit=20&page=${page}${status ? `&status=${encodeURIComponent(status)}` : ''}`,
      ),
    [page, status],
  );

  async function preview(id) {
    setBusy('preview-' + id);
    try {
      const listing = await api('/seller/listings/' + id);
      openModal(
        <>
          <h2>{listing.title}</h2>
          <img
            className="preview-photo"
            src={img(listing.images?.[0]?.url)}
            alt={listing.title}
            onError={onImgError}
          />
          <h3>{fmtVND(listing.price)}</h3>
          <p className="preview-description">{listing.description}</p>
          <p>
            {listing.city} · {LISTING_STATUS_NAMES[listing.status] || listing.status}
          </p>
          <button className="btn btn-line" onClick={closeModal}>
            Đóng
          </button>
        </>,
      );
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  async function toggleVisibility(listing) {
    setBusy('visibility-' + listing.id);
    try {
      await api(`/listings/${listing.id}/visibility`, {
        method: 'PATCH',
        body: { status: listing.status === 'ACTIVE' ? 'HIDDEN' : 'ACTIVE' },
      });
      toast('Đã cập nhật', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  async function remove(listing) {
    if (!window.confirm('Xoá tin này?')) return;
    setBusy('delete-' + listing.id);
    try {
      await api('/listings/' + listing.id, { method: 'DELETE' });
      toast('Đã xoá', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  async function boost(id) {
    setBusy('boost-' + id);
    try {
      const result = await api(`/listings/${id}/boost`, {
        method: 'POST',
        body: { days: 1 },
      });
      toast(result.message, 'ok');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  const rows = data?.data || [];

  return (
    <>
      <div className="toolbar">
        <select
          className="input"
          aria-label="Lọc theo trạng thái"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Tất cả trạng thái</option>
          {Object.entries(LISTING_STATUS_NAMES).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {loading && <Loading label="Đang tải tin đăng..." />}
      {error && <ErrorState error={error} />}
      {!loading && !error && (
        <>
          <div className="sect" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Tin đăng</th>
                    <th>Giá</th>
                    <th>Trạng thái</th>
                    <th>Lượt xem</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((listing) => (
                    <tr key={listing.id}>
                      <td>
                        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                          <img
                            src={img(listing.images?.[0]?.url)}
                            alt={listing.title}
                            style={{
                              width: 56,
                              height: 44,
                              objectFit: 'cover',
                              borderRadius: 8,
                            }}
                            onError={onImgError}
                          />
                          <b>{listing.title}</b>
                        </div>
                      </td>
                      <td>
                        <b>{fmtVND(listing.price)}</b>
                      </td>
                      <td>
                        <StatusPill map={LISTING_PILLS} status={listing.status} />
                      </td>
                      <td>{listing.views || 0}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button
                          className="btn btn-line btn-sm"
                          disabled={Boolean(busy)}
                          onClick={() => preview(listing.id)}
                        >
                          Xem trước
                        </button>
                        {!BLOCKED_EDIT.includes(listing.status) && (
                          <button
                            className="btn btn-line btn-sm"
                            onClick={() => navigate(`/edit-listing/${listing.id}`)}
                          >
                            Sửa
                          </button>
                        )}
                        {['ACTIVE', 'HIDDEN'].includes(listing.status) && (
                          <button
                            className="btn btn-line btn-sm"
                            disabled={Boolean(busy)}
                            onClick={() => toggleVisibility(listing)}
                          >
                            {listing.status === 'ACTIVE' ? 'Ẩn' : 'Hiện'}
                          </button>
                        )}
                        <button
                          className="btn btn-line btn-sm"
                          title="Đẩy tin 5.000đ/ngày"
                          disabled={Boolean(busy)}
                          onClick={() => boost(listing.id)}
                        >
                          ⚡ Đẩy
                        </button>
                        <button
                          className="btn btn-line btn-sm"
                          style={{ color: 'var(--red)' }}
                          disabled={Boolean(busy)}
                          onClick={() => remove(listing)}
                        >
                          Xoá
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!rows.length && (
                    <tr>
                      <td colSpan="5" className="muted">
                        Chưa có tin nào.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <Pagination meta={data.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- listing form ---------------- */

const PRICE_STEP = 10_000;
const PRICE_MAX = 10_000_000_000;

function priceText(value) {
  return value === '' ? '' : Number(value).toLocaleString('vi-VN');
}

function priceDigits(value) {
  const digits = String(value).replace(/\D/g, '').replace(/^0+(?=\d)/, '');
  return digits ? String(Math.min(Number(digits), PRICE_MAX)) : '';
}

function ListingForm({ listing = null }) {
  const categories = useCategories();
  const navigate = useNavigate();
  const toast = useToast();
  const { openModal, closeModal } = useModal();
  const editing = Boolean(listing);
  const { data: specConfig } = useAsync(
    () => api('/categories/specifications', { auth: false }),
    [],
  );
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [linkText, setLinkText] = useState('');
  const [form, setForm] = useState(() => ({
    title: listing?.title || '',
    categoryId: listing?.categoryId || '',
    condition: listing?.condition || 'USED_GOOD',
    price: listing?.price ?? '',
    isFree: listing?.isFree || false,
    description: listing?.description || '',
    city: listing?.city || '',
    deliveryMethod: listing?.deliveryMethod || 'ANY',
    specifications: listing?.specifications || {},
    images: (listing?.images || []).map((image) => image.url),
  }));

  useEffect(() => {
    if (form.categoryId || !categories.length) return;
    setForm((value) => ({ ...value, categoryId: categories[0].id }));
  }, [categories, form.categoryId]);

  useEffect(() => {
    if (editing) return undefined;
    let live = true;
    api('/users/me/addresses')
      .then((result) => {
        if (!live) return;
        const list = Array.isArray(result) ? result : result.data || [];
        const address = list.find((item) => item.isDefault) || list[0];
        if (address?.city) {
          setForm((value) => (value.city ? value : { ...value, city: address.city }));
        }
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [editing]);

  const category = categories.find((item) => item.id === Number(form.categoryId));
  const specFields = (category && specConfig?.[category.slug]) || {};

  function setSpec(key, value) {
    setForm((current) => ({
      ...current,
      specifications: { ...current.specifications, [key]: value },
    }));
  }

  function adjustPrice(delta) {
    setForm((current) => {
      const next = Math.min(PRICE_MAX, Math.max(0, (Number(current.price) || 0) + delta));
      return { ...current, price: String(next) };
    });
  }

  async function addImages(event) {
    const input = event.currentTarget;
    const files = [...input.files];
    input.value = '';
    if (!files.length) return;
    if (form.images.length + files.length > MAX_IMAGES) {
      toast(`Tối đa ${MAX_IMAGES} ảnh`, 'err');
      return;
    }
    if (files.some((file) => !IMAGE_TYPES.includes(file.type) || file.size > MAX_IMAGE_BYTES)) {
      toast('Chỉ nhận JPEG/PNG/WebP, tối đa 5MB mỗi ảnh', 'err');
      return;
    }
    setUploading(true);
    try {
      for (const file of files) {
        const result = await uploadFile(file, 'PRODUCT');
        setForm((current) => ({ ...current, images: [...current.images, result.url] }));
      }
      toast('Đã tải ảnh lên máy chủ', 'ok');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setUploading(false);
    }
  }

  function removeImage(index) {
    setForm((current) => ({
      ...current,
      images: current.images.filter((_, position) => position !== index),
    }));
  }

  function addImageLinks() {
    const links = linkText
      .split('\n')
      .map((value) => value.trim())
      .filter(Boolean);
    if (!links.length) return;
    setForm((current) => ({
      ...current,
      images: [...new Set([...current.images, ...links])].slice(0, MAX_IMAGES),
    }));
    setLinkText('');
  }

  function buildSpecifications() {
    return Object.fromEntries(
      Object.keys(specFields)
        .map((key) => [key, String(form.specifications[key] ?? '').trim()])
        .filter(([, value]) => value),
    );
  }

  function preview() {
    const filled = buildSpecifications();
    openModal(
      <>
        <h2>{form.title || 'Tiêu đề sản phẩm'}</h2>
        <img
          className="preview-photo"
          src={img(form.images[0])}
          alt="Ảnh xem trước"
          onError={onImgError}
        />
        <h3>{form.isFree ? 'Cho tặng 0đ' : fmtVND(form.price)}</h3>
        <p className="preview-description">{form.description}</p>
        <dl className="specification-list">
          {Object.entries(filled).map(([key, value]) => (
            <Fragment key={key}>
              <dt>{specFields[key]}</dt>
              <dd>{value}</dd>
            </Fragment>
          ))}
        </dl>
        <p className="muted">Xem trước thông tin; tin vẫn cần admin duyệt.</p>
        <button type="button" className="btn btn-line" onClick={closeModal}>
          Đóng
        </button>
      </>,
    );
  }

  async function submit(event) {
    event.preventDefault();
    if (!form.images.length) {
      toast('Thêm ít nhất 1 ảnh sản phẩm', 'err');
      return;
    }
    setSaving(true);
    const body = {
      categoryId: Number(form.categoryId),
      title: form.title.trim(),
      description: form.description.trim(),
      price: form.isFree ? 0 : Number(form.price) || 0,
      condition: form.condition,
      isFree: form.isFree,
      images: form.images,
      city: form.city.trim(),
      deliveryMethod: form.deliveryMethod,
      specifications: buildSpecifications(),
    };
    try {
      if (editing) {
        await api('/listings/' + listing.id, { method: 'PATCH', body });
      } else {
        await api('/listings', { method: 'POST', body });
      }
      toast(
        editing ? 'Đã lưu, tin được gửi duyệt lại' : 'Đăng tin thành công, đang chờ duyệt!',
        'ok',
      );
      navigate('/seller/listings');
    } catch (error) {
      toast(error.message, 'err');
      setSaving(false);
    }
  }

  return (
    <div className="sect" style={{ maxWidth: 640 }}>
      <h2>{editing ? 'Sửa tin đăng' : '＋ Đăng tin mới'}</h2>
      <form onSubmit={submit}>
        <div className="form-row">
          <label className="lbl" htmlFor="nl-title">
            Tiêu đề * (tối thiểu 10 ký tự)
          </label>
          <input
            className="input"
            id="nl-title"
            required
            minLength="10"
            maxLength="80"
            placeholder="VD: Tai nghe Sony WH-1000XM4 99%"
            value={form.title}
            onChange={(event) => setForm((value) => ({ ...value, title: event.target.value }))}
          />
        </div>
        <div className="row2">
          <div className="form-row">
            <label className="lbl" htmlFor="nl-cat">
              Danh mục *
            </label>
            <select
              className="input"
              id="nl-cat"
              value={form.categoryId}
              onChange={(event) =>
                setForm((value) => ({ ...value, categoryId: Number(event.target.value) }))
              }
            >
              {categories.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label className="lbl" htmlFor="nl-city">
              Tỉnh / thành phố *
            </label>
            <select
              className="input"
              id="nl-city"
              required
              value={form.city}
              onChange={(event) => setForm((value) => ({ ...value, city: event.target.value }))}
            >
              <option value="">Chọn tỉnh / thành phố</option>
              {form.city && !VIETNAM_PROVINCES.includes(form.city) && (
                <option value={form.city}>{form.city} (giá trị hiện tại)</option>
              )}
              {VIETNAM_PROVINCES.map((province) => (
                <option key={province} value={province}>
                  {province}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="nl-price">
            Giá bán (VNĐ) *
          </label>
          <div className="price-field">
            <button
              type="button"
              className="btn btn-line btn-sm"
              disabled={form.isFree}
              onClick={() => adjustPrice(-PRICE_STEP)}
              aria-label="Giảm 10.000 đồng"
            >
              -10k
            </button>
            <div className="price-wrap">
              <input
                className="input"
                id="nl-price"
                type="text"
                inputMode="numeric"
                required
                disabled={form.isFree}
                placeholder="VD: 1.000.000"
                value={priceText(form.price)}
                onChange={(event) =>
                  setForm((value) => ({ ...value, price: priceDigits(event.target.value) }))
                }
              />
              <span className="price-unit">VNĐ</span>
            </div>
            <button
              type="button"
              className="btn btn-line btn-sm"
              disabled={form.isFree}
              onClick={() => adjustPrice(PRICE_STEP)}
              aria-label="Tăng 10.000 đồng"
            >
              +10k
            </button>
          </div>
          <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
            Mỗi lần nhấn tăng/giảm 10.000 đ.
          </p>
          <label className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10 }}>
            <input
              type="checkbox"
              id="nl-free"
              style={{ accentColor: 'var(--green)' }}
              checked={form.isFree}
              onChange={(event) =>
                setForm((value) => ({
                  ...value,
                  isFree: event.target.checked,
                  price: event.target.checked ? 0 : value.price,
                }))
              }
            />
            🎁 Cho tặng 0đ (miễn phí)
          </label>
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="nl-files">
            Ảnh sản phẩm * (chụp/chọn từ máy, tối thiểu 1 ảnh)
          </label>
          <input
            className="input"
            id="nl-files"
            type="file"
            accept={IMAGE_TYPES.join(',')}
            multiple
            disabled={uploading}
            onChange={addImages}
          />
          {uploading && <p className="muted">Đang tải ảnh lên...</p>}
          <div className="evidence-grid" style={{ margin: '8px 0 0' }}>
            {form.images.map((url, index) => (
              <span key={url + index} style={{ position: 'relative', display: 'inline-block' }}>
                <img src={img(url)} alt={`Ảnh ${index + 1}`} onError={onImgError} />
                <button
                  type="button"
                  className="btn btn-line btn-sm"
                  style={{ position: 'absolute', top: 2, right: 2, padding: '2px 8px' }}
                  onClick={() => removeImage(index)}
                  aria-label={`Xóa ảnh ${index + 1}`}
                >
                  ✕
                </button>
              </span>
            ))}
            {!form.images.length && (
              <p className="muted" style={{ fontSize: 12.5 }}>
                Chưa có ảnh nào. Ảnh đầu tiên làm ảnh bìa.
              </p>
            )}
          </div>
          <details style={{ marginTop: 8 }}>
            <summary className="muted" style={{ fontSize: 12.5, cursor: 'pointer' }}>
              Hoặc dán link ảnh (mỗi dòng 1 link)
            </summary>
            <textarea
              className="input"
              rows="2"
              placeholder="https://..."
              value={linkText}
              onChange={(event) => setLinkText(event.target.value)}
            />
            <button type="button" className="btn btn-line btn-sm" onClick={addImageLinks}>
              Thêm link ảnh
            </button>
          </details>
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="nl-desc">
            Mô tả *
          </label>
          <textarea
            className="input"
            id="nl-desc"
            rows="4"
            required
            minLength="20"
            placeholder="Gợi ý: tình trạng thực tế + lỗi (nếu có) + phụ kiện kèm theo + lý do bán..."
            value={form.description}
            onChange={(event) =>
              setForm((value) => ({ ...value, description: event.target.value }))
            }
          />
        </div>
        <details className="listing-extra">
          <summary>Thông tin thêm (không bắt buộc)</summary>
          <div className="row2">
            <div className="form-row">
              <label className="lbl" htmlFor="nl-cond">
                Tình trạng
              </label>
              <select
                className="input"
                id="nl-cond"
                value={form.condition}
                onChange={(event) =>
                  setForm((value) => ({ ...value, condition: event.target.value }))
                }
              >
                {Object.entries(CONDITION_NAMES).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label className="lbl" htmlFor="nl-delivery">
                Hình thức giao nhận
              </label>
              <select
                className="input"
                id="nl-delivery"
                value={form.deliveryMethod}
                onChange={(event) =>
                  setForm((value) => ({ ...value, deliveryMethod: event.target.value }))
                }
              >
                {Object.entries(DELIVERY_NAMES).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label === 'Giao hàng hoặc gặp trực tiếp'
                      ? 'Gặp trực tiếp hoặc giao hàng'
                      : label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {Object.keys(specFields).length > 0 && (
            <fieldset className="specification-form">
              <legend>Thông số sản phẩm</legend>
              <p className="muted">
                Thông tin do người bán cung cấp. Hãy ghi rõ các lỗi và lịch sử sửa chữa.
              </p>
              {Object.entries(specFields).map(([key, label]) => {
                const numeric = ['batteryHealth', 'width', 'depth', 'height', 'power'].includes(key);
                return (
                  <div className="form-row" key={key}>
                    <label className="lbl" htmlFor={`spec-${key}`}>
                      {label}
                    </label>
                    <input
                      className="input"
                      id={`spec-${key}`}
                      type={numeric ? 'number' : undefined}
                      min={numeric ? '0' : undefined}
                      step={numeric ? 'any' : undefined}
                      max={key === 'batteryHealth' ? '100' : undefined}
                      maxLength={numeric ? undefined : 250}
                      value={form.specifications[key] ?? ''}
                      onChange={(event) => setSpec(key, event.target.value)}
                    />
                  </div>
                );
              })}
            </fieldset>
          )}
        </details>
        <button className="btn btn-line" type="button" onClick={preview}>
          Xem trước
        </button>{' '}
        <button className="btn btn-green" style={{ width: '100%' }} disabled={uploading || saving}>
          {saving
            ? 'Đang lưu...'
            : editing
              ? 'Lưu thay đổi và gửi duyệt lại'
              : 'Đăng tin (chờ duyệt)'}
        </button>
      </form>
    </div>
  );
}

/* ---------------- orders & offers ---------------- */

function SellerOrders() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { loading, data, error } = useAsync(
    () => api(`/orders/sales?limit=20&page=${page}`),
    [page],
  );

  if (loading) return <Loading label="Đang tải đơn bán..." />;
  if (error) return <ErrorState error={error} />;

  return (
    <>
      {data.data.map((order) => (
        <button
          key={order.id}
          type="button"
          className="card"
          onClick={() => navigate(`/orders/${order.id}`)}
          style={{
            padding: '16px 20px',
            marginBottom: 12,
            display: 'flex',
            gap: 16,
            alignItems: 'center',
            cursor: 'pointer',
            width: '100%',
            textAlign: 'left',
            fontFamily: 'inherit',
          }}
        >
          <div style={{ flex: 1 }}>
            <b>#{order.code}</b> <StatusPill map={ORDER_ST} status={order.status} />
            <div style={{ fontSize: 13, marginTop: 4 }}>
              {order.listing.title} · Buyer: {order.buyer.fullName}
            </div>
          </div>
          <b style={{ color: 'var(--green-dark)' }}>{fmtVND(order.totalAmount)}</b>
        </button>
      ))}
      {!data.data.length && <p className="muted">Chưa có đơn nào.</p>}
      <Pagination meta={data.meta} onPage={setPage} />
    </>
  );
}

function SellerOffers() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(null);
  const { loading, data, error, reload } = useAsync(
    () => api(`/offers/inbox?${new URLSearchParams({ page, limit: 10 })}`),
    [page],
  );

  async function act(offer, action) {
    setBusy(offer.id);
    try {
      await api(`/offers/${offer.id}`, { method: 'PATCH', body: { action } });
      toast('Đã cập nhật', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Loading label="Đang tải yêu cầu trả giá..." />;
  if (error) return <ErrorState error={error} />;

  return (
    <div className="sect">
      <h2>Yêu cầu trả giá</h2>
      {data.data.map((offer) => (
        <div className="offer-card" key={offer.id}>
          <h3>{offer.listing.title}</h3>
          <p>
            {offer.buyer.fullName} · Giá niêm yết {fmtVND(offer.listing.price)} → đề nghị{' '}
            <b>{fmtVND(offer.offeredPrice)}</b>
          </p>
          <p>{offer.message || ''}</p>
          <p className="muted">
            <StatusPill map={OFFER_ST} status={offer.status} /> · hết hạn{' '}
            {fmtDate(offer.expiresAt)}
          </p>
          {offer.status === 'PENDING' && new Date(offer.expiresAt) > new Date() && (
            <>
              <button
                className="btn btn-green btn-sm"
                disabled={busy === offer.id}
                onClick={() => act(offer, 'ACCEPT')}
              >
                Đồng ý
              </button>{' '}
              <button
                className="btn btn-line btn-sm"
                disabled={busy === offer.id}
                onClick={() => act(offer, 'REJECT')}
              >
                Từ chối
              </button>
            </>
          )}
        </div>
      ))}
      {!data.data.length && <p className="muted">Chưa có đề nghị trả giá.</p>}
      <Pagination meta={data.meta} onPage={setPage} />
    </div>
  );
}

/* ---------------- become seller ---------------- */

function BecomeSellerWizard() {
  const { user, setUser } = useSession();
  const { openModal, closeModal } = useModal();
  const navigate = useNavigate();
  const toast = useToast();
  const [step, setStep] = useState(1);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    shopName: 'Shop ' + (user?.fullName || ''),
    phone: user?.phone || '',
    city: '',
    street: '',
  });

  async function submit(event) {
    event.preventDefault();
    if (form.shopName.trim().length < 2) {
      toast('Tên shop tối thiểu 2 ký tự', 'err');
      return;
    }
    if ((form.city && !form.street) || (!form.city && form.street)) {
      toast('Nhập đủ tỉnh/thành và địa chỉ, hoặc bỏ trống cả hai', 'err');
      return;
    }
    setBusy(true);
    try {
      await api('/users/me/become-seller', {
        method: 'POST',
        body: {
          shopName: form.shopName.trim(),
          phone: form.phone.trim() || undefined,
          city: form.city.trim() || undefined,
          street: form.street.trim() || undefined,
        },
      });
      const me = await api('/auth/me');
      setUser({ ...user, roles: me.roles, phone: me.phone });
      toast('Mở kênh người bán thành công!', 'ok');
      openModal(
        <>
          <h2>🎉 Gian hàng đã mở!</h2>
          <p className="muted">
            {form.shopName.trim()} sẵn sàng đón khách. Vào Hồ sơ để xác minh email/danh tính
            lấy huy hiệu ✓, buyer sẽ tin shop hơn.
          </p>
          <button
            className="btn btn-green"
            style={{ width: '100%' }}
            onClick={() => {
              closeModal();
              navigate('/seller/new');
            }}
          >
            ＋ Đăng tin đầu tiên
          </button>
          <button
            className="btn btn-line"
            style={{ width: '100%', marginTop: 8 }}
            onClick={() => {
              closeModal();
              navigate('/seller');
            }}
          >
            Về kênh người bán
          </button>
        </>,
      );
    } catch (error) {
      toast(error.message, 'err');
      setBusy(false);
    }
  }

  if (step === 1) {
    return (
      <>
        <h2>🏪 Mở gian hàng</h2>
        <p className="muted">Bước 1/2 — Biết trước khi bán</p>
        <div className="stat-grid">
          <Stat label="Đăng tin" value="Miễn phí" />
          <Stat label="Phí sàn" value="Khi bán được" />
          <Stat label="Tiền về" value="Ví SafePay" />
        </div>
        <div className="sect" style={{ margin: '12px 0' }}>
          <p>💰 Phí sàn chỉ thu khi bán được hàng, theo từng danh mục.</p>
          <p>🔒 Tiền cọc được giữ hộ tới khi người mua xác nhận nhận hàng.</p>
          <p>⚠️ Tin vi phạm bị ẩn, tái phạm bị khóa shop.</p>
        </div>
        <label className="free-filter">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(event) => setAgreed(event.target.checked)}
          />{' '}
          Tôi đã đọc và đồng ý quy định bán hàng
        </label>
        <button
          className="btn btn-green"
          style={{ width: '100%', marginTop: 12 }}
          onClick={() => {
            if (!agreed) {
              toast('Bạn cần đồng ý quy định bán hàng', 'err');
              return;
            }
            setStep(2);
          }}
        >
          Tiếp tục →
        </button>
      </>
    );
  }

  return (
    <>
      <h2>🏪 Thông tin shop</h2>
      <p className="muted">
        Bước 2/2 — Buyer tin shop có tên rõ ràng, SĐT và địa chỉ lấy hàng.
      </p>
      <form onSubmit={submit}>
        <div className="form-row">
          <label className="lbl" htmlFor="seller-shop">
            Tên shop *
          </label>
          <input
            className="input"
            id="seller-shop"
            required
            minLength="2"
            maxLength="100"
            value={form.shopName}
            onChange={(event) =>
              setForm((value) => ({ ...value, shopName: event.target.value }))
            }
          />
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="seller-phone">
            SĐT liên hệ (VD: 0987654321)
          </label>
          <input
            className="input"
            id="seller-phone"
            inputMode="tel"
            maxLength="20"
            pattern={'(\\+84|0)(3|5|7|8|9)[0-9]{8}'}
            placeholder="Để buyer và shipper liên lạc"
            value={form.phone}
            onChange={(event) => setForm((value) => ({ ...value, phone: event.target.value }))}
          />
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="seller-city">
            Tỉnh / thành phố
          </label>
          <input
            className="input"
            id="seller-city"
            maxLength="100"
            placeholder="VD: TP. Hồ Chí Minh"
            value={form.city}
            onChange={(event) => setForm((value) => ({ ...value, city: event.target.value }))}
          />
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="seller-street">
            Địa chỉ lấy hàng
          </label>
          <input
            className="input"
            id="seller-street"
            maxLength="255"
            placeholder="Số nhà, đường..."
            value={form.street}
            onChange={(event) => setForm((value) => ({ ...value, street: event.target.value }))}
          />
        </div>
        <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Đang mở gian hàng...' : 'Mở gian hàng'}
        </button>
      </form>
    </>
  );
}

function SellerOnboarding() {
  const { openModal } = useModal();
  return (
    <div className="wrap">
      <section className="seller-onboarding sect">
        <div className="onboarding-icon">
          <Icon name="shop" />
        </div>
        <h1>Mở gian hàng của bạn</h1>
        <p className="muted">
          Đăng món đồ còn tốt, trao đổi với người mua và quản lý đơn hàng tại một nơi.
        </p>
        <button className="btn btn-green" onClick={() => openModal(<BecomeSellerWizard />)}>
          <Icon name="plus" /> Bắt đầu bán hàng
        </button>
        <Link className="btn btn-line" to="/">
          Tiếp tục mua sắm
        </Link>
      </section>
    </div>
  );
}

/* ---------------- shell / exports ---------------- */

function SellerShell() {
  const { user } = useSession();
  const { tab: tabParam } = useParams();
  const tab = tabParam || 'dashboard';

  if (!TABS.some(([key]) => key === tab)) {
    return <Navigate to="/seller/dashboard" replace />;
  }

  let content = null;
  if (tab === 'dashboard') content = <Dashboard />;
  else if (tab === 'listings') content = <SellerListings />;
  else if (tab === 'new') content = <ListingForm />;
  else if (tab === 'orders') content = <SellerOrders />;
  else if (tab === 'offers') content = <SellerOffers />;
  else if (tab === 'insights') content = <ReviewInsights />;

  return (
    <div className="wrap seller-shell">
      <header className="seller-header">
        <div>
          <h1>Kênh người bán</h1>
          <p>Chào {user?.fullName}. Quản lý gian hàng của bạn tại đây.</p>
        </div>
        <Link className="btn btn-green btn-sm" to="/seller/new">
          <Icon name="plus" /> Đăng tin mới
        </Link>
      </header>
      <nav className="seller-navigation" aria-label="Kênh người bán">
        {TABS.map(([key, label, icon]) => (
          <Link key={key} to={`/seller/${key}`} aria-current={tab === key ? 'page' : undefined}>
            <Icon name={icon} />
            {label}
          </Link>
        ))}
        <Link to="/returns">
          <Icon name="return" /> Trả hàng
        </Link>
        <Link to={`/shop/${user?.id}`}>
          <Icon name="shop" /> Xem gian hàng
        </Link>
      </nav>
      <div id="seller-content">{content}</div>
    </div>
  );
}

export function Seller() {
  const { loggedIn, hasRole } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loggedIn) navigate('/login', { replace: true });
  }, [loggedIn, navigate]);

  if (!loggedIn) return null;
  if (!hasRole('SELLER')) return <SellerOnboarding />;
  return <SellerShell />;
}

function SellerEditInner({ id }) {
  const { loading, data, error } = useAsync(() => api('/seller/listings/' + id), [id]);

  if (loading) return <Loading label="Đang tải tin đăng..." />;
  if (error) return <ErrorState error={error} />;
  if (BLOCKED_EDIT.includes(data.status)) {
    return (
      <div className="empty">
        <div className="e">🔒</div>
        <h1>Tin này không thể chỉnh sửa</h1>
        <p className="muted">Tin đang được giữ, đã bán hoặc đã xóa.</p>
        <Link className="btn btn-line" to="/seller/listings">
          Về danh sách tin
        </Link>
      </div>
    );
  }
  return <ListingForm listing={data} />;
}

export function SellerEdit() {
  const { loggedIn, hasRole } = useSession();
  const { id } = useParams();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loggedIn) navigate('/login', { replace: true });
  }, [loggedIn, navigate]);

  if (!loggedIn) return null;
  if (!hasRole('SELLER')) return <Navigate to="/seller" replace />;
  return (
    <div className="wrap">
      <SellerEditInner id={id} />
    </div>
  );
}
