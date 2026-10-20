import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { ErrorState, Loading, Pagination, Avatar, useAsync } from '../ui';

export default function Shops() {
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get('q') || '';
  const page = Math.max(1, Number(searchParams.get('page')) || 1);
  const [draft, setDraft] = useState(q);
  const paramsString = searchParams.toString();

  useEffect(() => {
    setDraft(new URLSearchParams(paramsString).get('q') || '');
  }, [paramsString]);

  const { data, loading, error } = useAsync(
    () =>
      api(
        '/shops/search?' +
          new URLSearchParams({ q, limit: '12', page: String(page) }),
        { auth: false },
      ),
    [q, page],
  );

  function submit(event) {
    event.preventDefault();
    const next = new URLSearchParams();
    const value = draft.trim();
    if (value) next.set('q', value);
    setSearchParams(next);
  }

  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const shops = data?.data || [];

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 4 }}>🏪 Tìm gian hàng</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        Khám phá các shop uy tín trên Nola2Hand.
      </p>
      <form
        className="searchbar"
        style={{ maxWidth: 520, marginBottom: 20 }}
        onSubmit={submit}
      >
        <input
          placeholder="Nhập tên shop..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          aria-label="Tên shop"
        />
        <button type="submit">🔍 Tìm</button>
      </form>

      {shops.length ? (
        <>
          <div
            className="pgrid"
            style={{ gridTemplateColumns: 'repeat(3,1fr)' }}
          >
            {shops.map((shop) => (
              <Link
                key={shop.id}
                className="card"
                to={'/shop/' + shop.id}
                style={{
                  padding: 22,
                  textAlign: 'center',
                  textDecoration: 'none',
                  transition: '.18s',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    marginBottom: 12,
                  }}
                >
                  <Avatar
                    user={{ fullName: shop.shopName, avatarUrl: shop.avatarUrl }}
                    size={72}
                  />
                </div>
                <b style={{ fontSize: 15 }}>{shop.shopName}</b>
                <div style={{ margin: '8px 0', color: '#f59e0b', fontSize: 14 }}>
                  ★ {Number(shop.rating || 0).toFixed(1)}{' '}
                  <span className="muted" style={{ fontSize: 12 }}>
                    ({shop.totalReviews} đánh giá)
                  </span>
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  📦 {shop.productsCount} sản phẩm ·{' '}
                  {shop.responseRate == null
                    ? 'Chưa đủ dữ liệu phản hồi'
                    : 'Phản hồi ' + shop.responseRate + '%'}
                </div>
                <span
                  className="btn btn-line btn-sm"
                  style={{ marginTop: 12, display: 'inline-flex' }}
                >
                  Xem gian hàng
                </span>
              </Link>
            ))}
          </div>
          <Pagination
            meta={data.meta}
            onPage={(next) => {
              const params = new URLSearchParams();
              if (q) params.set('q', q);
              if (next > 1) params.set('page', String(next));
              setSearchParams(params);
            }}
          />
        </>
      ) : (
        <div className="empty">
          <div className="e">🏪</div>
          {q ? (
            <p>
              Không tìm thấy gian hàng &quot;<b>{q}</b>&quot;.
            </p>
          ) : (
            <p>Chưa có gian hàng nào.</p>
          )}
        </div>
      )}
    </div>
  );
}
