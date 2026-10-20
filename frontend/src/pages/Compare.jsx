import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import {
  clearComparison,
  comparisonIds,
  toggleComparison,
  useComparison,
} from '../compare';
import { CONDITION_NAMES, DELIVERY_NAMES } from '../constants';
import { fmtDate, fmtVND, img, onImgError } from '../utils';
import { ErrorState, Loading, useAsync } from '../ui';

function Row({ label, values }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      {values.map((value, index) => (
        <td key={index}>{value}</td>
      ))}
    </tr>
  );
}

export default function Compare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const trayIds = useComparison();
  const raw = searchParams.get('ids');
  const ids = raw
    ? raw.split(',').map(Number)
    : comparisonIds().length
      ? comparisonIds()
      : trayIds;

  const valid =
    ids.length > 0 &&
    ids.length <= 3 &&
    new Set(ids).size === ids.length &&
    ids.every((id) => Number.isSafeInteger(id) && id > 0);
  const idsKey = ids.join(',');

  const { data, loading, error } = useAsync(async () => {
    if (!valid) return null;
    const [comparison, fields] = await Promise.all([
      api('/listings/compare?ids=' + idsKey, { auth: false }),
      api('/categories/specifications', { auth: false }),
    ]);
    return { comparison, fields: fields || {} };
  }, [idsKey, valid]);

  if (!ids.length) {
    return (
      <div className="wrap empty">
        <h1>So sánh sản phẩm</h1>
        <p>Chọn tối đa 3 món từ các thẻ sản phẩm.</p>
        <Link className="btn btn-green" to="/">
          Chọn sản phẩm
        </Link>
      </div>
    );
  }

  if (!valid) {
    return (
      <ErrorState error={{ message: 'Chọn 1–3 sản phẩm khác nhau' }} />
    );
  }

  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const items = data?.comparison?.items || [];
  const unavailable = data?.comparison?.unavailable || [];
  const fields = data?.fields || {};
  const keys = [
    ...new Set(items.flatMap((listing) => Object.keys(listing.specifications || {}))),
  ];

  function remove(id) {
    if (comparisonIds().includes(id)) toggleComparison(id);
    const remaining = ids.filter((value) => value !== id);
    const params = new URLSearchParams();
    if (remaining.length) params.set('ids', remaining.join(','));
    setSearchParams(params);
  }

  function clear() {
    clearComparison();
    setSearchParams(new URLSearchParams());
  }

  function history(listing) {
    if (!listing.priceHistory?.length) return 'Chưa có lịch sử';
    return (
      <>
        <p>
          Đầu: {fmtVND(listing.priceHistory[0].price)} → hiện tại{' '}
          {fmtVND(listing.price)}
        </p>
        <details>
          <summary>{listing.priceHistory.length} lần ghi giá</summary>
          {listing.priceHistory.map((point) => (
            <p key={point.id}>
              {fmtDate(point.createdAt)} · {fmtVND(point.price)}
            </p>
          ))}
        </details>
      </>
    );
  }

  return (
    <div className="wrap">
      <h1>So sánh tối đa 3 sản phẩm</h1>
      <p className="muted">
        Thông số và tình trạng do seller cung cấp; lịch sử là giá niêm yết.
      </p>
      {unavailable.length > 0 && (
        <p role="status">
          Một số món đã không còn đang bán và được bỏ khỏi bảng.
        </p>
      )}

      {items.length ? (
        <div className="comparison-table">
          <table className="tbl">
            <thead>
              <tr>
                <th>Tiêu chí</th>
                {items.map((listing) => (
                  <th key={listing.id}>
                    <img
                      src={img(listing.images?.[0]?.url)}
                      alt={listing.title}
                      onError={onImgError}
                    />
                    <Link to={'/listing/' + listing.id}>{listing.title}</Link>
                    <button
                      type="button"
                      className="btn btn-line btn-sm"
                      style={{ marginTop: 8 }}
                      onClick={() => remove(listing.id)}
                    >
                      Bỏ chọn
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <Row label="Giá" values={items.map((l) => fmtVND(l.price))} />
              <Row
                label="Tình trạng"
                values={items.map((l) => CONDITION_NAMES[l.condition])}
              />
              <Row
                label="Danh mục"
                values={items.map((l) => l.category?.name)}
              />
              <Row
                label="Địa điểm"
                values={items.map((l) => l.city || 'Chưa ghi')}
              />
              <Row
                label="Giao nhận"
                values={items.map((l) => DELIVERY_NAMES[l.deliveryMethod])}
              />
              <Row
                label="Shop"
                values={items.map((listing) => (
                  <>
                    <Link to={'/shop/' + listing.sellerId}>
                      {listing.seller?.fullName}
                    </Link>
                    {listing.seller?.idVerified && (
                      <p>✓ Danh tính đã duyệt</p>
                    )}
                    {listing.seller?.emailVerifiedAt && (
                      <p>✓ Email đã xác nhận</p>
                    )}
                  </>
                ))}
              />
              {!keys.length && (
                <Row
                  label="Thông số"
                  values={items.map(() => 'Seller chưa cung cấp')}
                />
              )}
              {keys.map((key) => (
                <Row
                  key={key}
                  label={
                    items
                      .map((listing) => fields[listing.category?.slug]?.[key])
                      .find(Boolean) || key
                  }
                  values={items.map(
                    (listing) => listing.specifications?.[key] || '—',
                  )}
                />
              ))}
              <Row label="Lịch sử giá" values={items.map(history)} />
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty">Các món đã không còn đang bán.</div>
      )}

      <Link className="btn btn-line" to="/">
        Chọn thêm sản phẩm
      </Link>{' '}
      <button className="btn btn-line" type="button" onClick={clear}>
        Xóa chọn
      </button>
    </div>
  );
}
