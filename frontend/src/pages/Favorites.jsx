import { Navigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import {
  ErrorState,
  ListingCard,
  Loading,
  Pagination,
  useAsync,
} from '../ui';
import { qs } from '../utils';

function FavoritesInner() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get('page')) || 1);

  const { data, loading, error } = useAsync(
    () => api('/listings/me/favorites?' + qs({ page, limit: 12 })),
    [page],
  );

  function goPage(value) {
    const next = new URLSearchParams(params);
    next.set('page', value);
    setParams(next);
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 16 }}>
        🤍 Tin đã lưu ({data?.meta?.total ?? 0})
      </h1>

      {loading && !data ? (
        <Loading />
      ) : error ? (
        <ErrorState error={error} />
      ) : data?.data?.length ? (
        <>
          <div className="pgrid">
            {data.data.map((favorite) => (favorite.listing ? <ListingCard key={favorite.id} listing={favorite.listing} /> : null))}
          </div>
          <Pagination meta={data.meta} onPage={goPage} />
        </>
      ) : (
        <div className="empty">
          <div className="e">🤍</div>
          Chưa lưu tin nào.
        </div>
      )}
    </div>
  );
}

export default function Favorites() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <FavoritesInner />;
}
