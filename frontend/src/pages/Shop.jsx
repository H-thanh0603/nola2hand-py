import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import {
  Avatar,
  ErrorState,
  ListingCard,
  Loading,
  Pagination,
  useAsync,
  useToast,
} from '../ui';

export default function Shop() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const navigate = useNavigate();
  const toast = useToast();
  const { token } = useSession();

  const { data: shop, loading, error } = useAsync(
    () =>
      api(
        '/shops/' + id + '?' + new URLSearchParams({ page: String(page), limit: '12' }),
        { auth: false },
      ),
    [id, page],
  );

  if (loading && !shop) return <Loading />;
  if (error) return <ErrorState error={error} />;
  if (!shop) return null;

  const reputation = shop.reputation || {};

  function startChat() {
    if (!token) {
      navigate('/login');
      return;
    }
    if (shop.id) navigate('/chat/' + shop.id);
    else toast('Không mở được hội thoại', 'err');
  }

  return (
    <div className="wrap">
      <div className="crumbs">
        <Link to="/shops">Gian hàng</Link> /{' '}
        <b style={{ color: 'var(--ink)' }}>{shop.shopName}</b>
      </div>

      <div
        className="card"
        style={{
          padding: 28,
          marginBottom: 20,
          display: 'flex',
          gap: 20,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <Avatar
          user={{ fullName: shop.shopName, avatarUrl: shop.avatarUrl }}
          size={84}
        />
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 style={{ fontSize: 24 }}>{shop.shopName}</h1>
          <div className="muted" style={{ fontSize: 13 }}>
            Chủ shop: {shop.fullName} · Tham gia{' '}
            {new Date(shop.joinedAt).toLocaleDateString('vi-VN')}
          </div>
          <div
            style={{
              display: 'flex',
              gap: 14,
              marginTop: 10,
              flexWrap: 'wrap',
            }}
          >
            <span className="badge b-green">
              ★ {Number(shop.rating || 0).toFixed(1)} ({shop.totalReviews} đánh
              giá)
            </span>
            <span className="badge b-blue">
              📦 {shop.listings?.meta?.total || 0} sản phẩm
            </span>
            <span className="badge b-amber">
              {shop.responseRate == null
                ? 'Chưa đủ dữ liệu phản hồi'
                : 'Phản hồi ' + shop.responseRate + '%'}
            </span>
            <span className="badge b-gray">
              🧾 {shop.totalOrders} đơn đã bán
            </span>
          </div>
        </div>
        <button className="btn btn-dark" onClick={startChat}>
          💬 Chat với shop
        </button>
      </div>

      <h2 style={{ fontSize: 18, marginBottom: 14 }}>
        📦 Sản phẩm của shop ({shop.listings?.meta?.total || 0})
      </h2>
      <div className="pgrid">
        {shop.listings?.data?.length ? (
          shop.listings.data.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))
        ) : (
          <p className="muted">Shop chưa có sản phẩm nào đang bán.</p>
        )}
      </div>
      <Pagination
        meta={shop.listings?.meta}
        onPage={(next) => {
          const params = new URLSearchParams();
          if (next > 1) params.set('page', String(next));
          setSearchParams(params);
        }}
      />

      {shop.recentReviews?.length ? (
        <>
          <h2 style={{ fontSize: 18, margin: '24px 0 14px' }}>
            ⭐ Đánh giá gần đây
          </h2>
          {shop.recentReviews.map((review) => (
            <div
              key={review.id}
              className="card"
              style={{ padding: '16px 20px', marginBottom: 10, boxShadow: 'none' }}
            >
              <div
                style={{
                  display: 'flex',
                  gap: 10,
                  alignItems: 'center',
                  marginBottom: 6,
                }}
              >
                <Avatar user={review.reviewer} size={32} />
                <b style={{ fontSize: 13 }}>{review.reviewer?.fullName}</b>
                <span style={{ color: '#f59e0b' }}>
                  {'★'.repeat(review.rating)}
                </span>
              </div>
              <p style={{ fontSize: 13 }}>{review.comment || ''}</p>
            </div>
          ))}
        </>
      ) : null}

      <section className="sect">
        <h2>Hồ sơ uy tín shop</h2>
        <div className="chips">
          {reputation.emailVerified ? (
            <span className="badge b-blue">✓ Email đã xác nhận</span>
          ) : (
            <span className="badge b-gray">Email chưa xác nhận</span>
          )}
          {reputation.identityVerified ? (
            <span className="badge b-green">✓ Danh tính đã duyệt</span>
          ) : (
            <span className="badge b-gray">Danh tính chưa được duyệt</span>
          )}
        </div>
        <div className="stat-grid">
          <div className="stat">
            <div className="t">Đơn hoàn tất</div>
            <div className="v">{reputation.completedOrders}</div>
          </div>
          <div className="stat">
            <div className="t">Tỷ lệ hủy</div>
            <div className="v">
              {reputation.cancellationRate == null
                ? 'Chưa có đơn'
                : reputation.cancellationRate + '%'}
            </div>
          </div>
          <div className="stat">
            <div className="t">Phản hồi 90 ngày</div>
            <div className="v">
              {reputation.responseRate == null
                ? 'Chưa có dữ liệu'
                : reputation.responseRate + '%'}
            </div>
          </div>
          <div className="stat">
            <div className="t">Thời gian phản hồi trung vị</div>
            <div className="v">
              {reputation.medianResponseSeconds == null
                ? '—'
                : reputation.medianResponseSeconds < 3600
                  ? Math.round(reputation.medianResponseSeconds / 60) + ' phút'
                  : (reputation.medianResponseSeconds / 3600).toFixed(1) + ' giờ'}
            </div>
          </div>
        </div>
        <p className="muted">
          {reputation.totalOrders} đơn phát sinh · {reputation.cancelledOrders}{' '}
          đơn hủy · {reputation.returnedOrders} đơn trả hàng đã hoàn tiền. Tỷ lệ
          hủy gồm hủy bởi hai bên và hết hạn cọc, không phải kết luận lỗi của
          shop. Phản hồi tính {reputation.inquiries} lượt hỏi (
          {reputation.responses} đã trả lời), tối đa 10.000 tin trong 90 ngày.
        </p>
      </section>
    </div>
  );
}
