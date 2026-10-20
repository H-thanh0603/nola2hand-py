import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useCategories } from '../categories';
import { useSession } from '../session';
import { CATEGORY_DESIGNS, CONDITION_NAMES, DELIVERY_NAMES } from '../constants';
import { fmtVND, img, onImgError, qs } from '../utils';
import {
  ErrorState,
  Icon,
  ListingCard,
  Loading,
  Pagination,
  categoryIcon,
  useAsync,
  useToast,
} from '../ui';

const FILTER_KEYS = [
  'q',
  'condition',
  'minPrice',
  'maxPrice',
  'city',
  'deliveryMethod',
  'verified',
  'isFree',
];

const FILTER_LABELS = {
  q: 'Từ khóa',
  condition: 'Tình trạng',
  minPrice: 'Từ',
  maxPrice: 'Đến',
  city: 'Địa điểm',
  deliveryMethod: 'Giao nhận',
  verified: 'Xác minh',
  isFree: 'Cho tặng',
};

function readFilters(params) {
  const filters = {};
  FILTER_KEYS.forEach((key) => {
    const value = params.get(key);
    if (value) filters[key] = value;
  });
  return filters;
}

function filterValueLabel(key, value) {
  if (key === 'condition') return CONDITION_NAMES[value] || value;
  if (key === 'deliveryMethod') return DELIVERY_NAMES[value] || value;
  if (value === 'true') return 'Có';
  return value;
}

export default function Catalog() {
  const { slug } = useParams();
  const categories = useCategories();
  const [searchParams, setSearchParams] = useSearchParams();
  const { token } = useSession();
  const navigate = useNavigate();
  const toast = useToast();

  const category = slug
    ? categories.find((item) => item.slug === decodeURIComponent(slug))
    : null;
  const filters = readFilters(searchParams);
  const activeFilters = Object.keys(filters).length > 0;
  const urlPage = Math.max(1, Number(searchParams.get('page')) || 1);
  const sort = searchParams.get('sort') || '';
  const home = !slug && !activeFilters && urlPage <= 1;
  const basePath = category ? '/category/' + category.slug : '/';

  const [draft, setDraft] = useState(() => readFilters(searchParams));
  const [filterError, setFilterError] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [bannerBroken, setBannerBroken] = useState(false);
  const paramsString = searchParams.toString();

  useEffect(() => {
    setDraft(readFilters(new URLSearchParams(paramsString)));
  }, [paramsString]);

  const query = { ...filters, limit: 12 };
  if (sort) query.sort = sort;
  if (urlPage > 1) query.page = urlPage;
  if (category) query.categoryId = category.id;
  const queryString = qs(query);

  const { data, loading, error } = useAsync(async () => {
    const [res, banners, recommended] = await Promise.all([
      api('/listings?' + queryString, { auth: false }),
      home
        ? api('/banners?position=HOME_HERO', { auth: false }).catch(() => [])
        : Promise.resolve([]),
      home
        ? api('/listings/recommended?limit=8', { auth: Boolean(token) }).catch(() => null)
        : Promise.resolve(null),
    ]);
    return { res, banners, recommended };
  }, [queryString, category?.id, home, token]);

  function setFilter(key, value) {
    const next = new URLSearchParams(searchParams);
    if (key !== 'page') next.delete('page');
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  function patchDraft(key, value) {
    setDraft((previous) => ({ ...previous, [key]: value }));
  }

  function applyFilters(event) {
    event.preventDefault();
    const min = String(draft.minPrice || '').trim();
    const max = String(draft.maxPrice || '').trim();
    const invalid =
      (min && (!Number.isFinite(Number(min)) || Number(min) < 0)) ||
      (max && (!Number.isFinite(Number(max)) || Number(max) < 0)) ||
      (min && max && Number(min) > Number(max));
    if (invalid) {
      setFilterError('Giá phải không âm; giá đến phải lớn hơn hoặc bằng giá từ.');
      return;
    }
    setFilterError('');
    const next = new URLSearchParams();
    const q = String(draft.q || '').trim();
    if (q) next.set('q', q);
    if (draft.condition) next.set('condition', draft.condition);
    if (min) next.set('minPrice', min);
    if (max) next.set('maxPrice', max);
    if (draft.isFree === 'true') next.set('isFree', 'true');
    const city = String(draft.city || '').trim();
    if (city) next.set('city', city);
    if (draft.deliveryMethod) next.set('deliveryMethod', draft.deliveryMethod);
    if (draft.verified === 'true') next.set('verified', 'true');
    if (sort) next.set('sort', sort);
    setSearchParams(next);
  }

  async function saveSearch() {
    if (!token) {
      navigate('/login');
      return;
    }
    const suggested = filters.q || category?.name || 'Đồ tôi đang tìm';
    const name = prompt('Tên tìm kiếm theo dõi:', suggested);
    if (!name?.trim()) return;
    const payload = { ...filters };
    if (category) payload.categoryId = category.id;
    try {
      await api('/saved-searches', {
        method: 'POST',
        body: { name: name.trim(), filters: payload },
      });
      toast(
        'Đã theo dõi. Tin mới phù hợp sẽ xuất hiện trong thông báo.',
        'ok',
      );
    } catch (requestError) {
      toast(requestError.message, 'err');
    }
  }

  if (slug && !category && !categories.length) return <Loading />;
  if (slug && !category) {
    return (
      <div className="empty">
        <div className="e">📦</div>
        <h1>Không tìm thấy danh mục</h1>
        <p>Danh mục có thể đã được gỡ hoặc chưa tải được.</p>
        <Link className="btn btn-green" to="/">
          Về trang chủ
        </Link>
      </div>
    );
  }

  const design =
    CATEGORY_DESIGNS[category?.slug] || {
      theme: 'tech',
      title: 'Đồ cũ, giá trị mới.',
      description:
        'Khám phá các tin đăng trong danh mục và tìm món đồ phù hợp với bạn.',
      topics: [],
    };

  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const res = data?.res;
  const banners = data?.banners || [];
  const recommended = data?.recommended;
  const heroListing = res?.data?.[0];
  const page = Math.max(1, res?.meta?.page || 1);

  return (
    <>
      {category ? (
        <div className="wrap category-intro">
          <nav className="crumbs" aria-label="Đường dẫn">
            <Link to="/">Trang chủ</Link> / <span>{category.name}</span>
          </nav>
          <section className={'category-hero ' + design.theme}>
            <div>
              <span className="eyebrow">Khám phá danh mục</span>
              <h1>{category.name}</h1>
              <h2>{design.title}</h2>
              <p>{design.description}</p>
              <div className="chips">
                {design.topics.map((topic) => (
                  <Link
                    key={topic}
                    className={
                      'chip' + (filters.q === topic ? ' on' : '')
                    }
                    to={basePath + '?' + qs({ q: topic })}
                  >
                    {topic} ↗
                  </Link>
                ))}
              </div>
            </div>
            <div className="category-art" aria-hidden="true">
              <span>
                <Icon name={categoryIcon(category.slug)} />
              </span>
              <small>Đồ cũ. Giá trị mới.</small>
            </div>
          </section>
        </div>
      ) : activeFilters || page > 1 ? (
        <div className="wrap search-intro">
          <nav className="crumbs" aria-label="Đường dẫn">
            <Link to="/">Trang chủ</Link> / Tìm sản phẩm
          </nav>
          <h1>
            {filters.q
              ? `Kết quả cho “${filters.q}”`
              : 'Tìm món đồ phù hợp'}
          </h1>
          <p className="muted">
            Điều chỉnh bộ lọc để chọn đúng món bạn cần.
          </p>
        </div>
      ) : (
        <section className="hero">
          <div className="wrap">
            <div className="home-hero">
              <div className="hero-copy">
                <span className="hero-kicker">
                  <Icon name="cycle" /> Mua sắm thêm bền vững
                </span>
                <h1>
                  Mua món mình cần.
                  <br />
                  Giữ điều đáng giá.
                </h1>
                <p className="muted">
                  Đồ còn tốt, giá dễ mua. Tìm món đồ hợp với bạn
                  <br className="desktop-break" /> và trao cơ hội mới cho
                  những điều quen thuộc.
                </p>
                <div className="hero-actions">
                  <button
                    type="button"
                    className="btn btn-green"
                    onClick={() =>
                      document
                        .getElementById('catalog-results')
                        ?.scrollIntoView({ behavior: 'smooth' })
                    }
                  >
                    Khám phá sản phẩm <Icon name="arrow" />
                  </button>
                  <Link className="btn btn-line" to="/seller">
                    Đăng tin bán đồ
                  </Link>
                </div>
                <div className="hero-benefits">
                  <span>
                    <Icon name="shield" /> Ký quỹ SafePay
                  </span>
                  <span>
                    <Icon name="chat" /> Trao đổi trực tiếp
                  </span>
                </div>
              </div>
              <div className="hero-visual">
                {heroListing ? (
                  <Link className="hero-product" to={'/listing/' + heroListing.id}>
                    <span className="hero-product-tag">
                      Một lựa chọn từ cộng đồng
                    </span>
                    <img
                      src={img(heroListing.images?.[0]?.url)}
                      alt={heroListing.title}
                      onError={onImgError}
                    />
                    <div className="hero-product-caption">
                      <div>
                        <span>
                          {heroListing.category?.name || 'Đồ còn tốt'}
                        </span>
                        <strong>{heroListing.title}</strong>
                      </div>
                      <b>
                        {heroListing.isFree
                          ? 'Cho tặng 0đ'
                          : fmtVND(heroListing.price)}
                      </b>
                    </div>
                    <span className="hero-product-link">
                      <Icon name="arrow" />
                    </span>
                  </Link>
                ) : (
                  <div className="hero-empty">
                    <Icon name="cycle" />
                    <h2>
                      Cũ với bạn.
                      <br />
                      Mới với ai đó.
                    </h2>
                    <Link className="btn btn-green" to="/seller">
                      Đăng món đồ đầu tiên
                    </Link>
                  </div>
                )}
                <span className="visual-note">
                  <Icon name="heart" /> Thêm vòng đời cho đồ tốt
                </span>
              </div>
            </div>
            <div className="trust-strip">
              <span>
                <Icon name="search" /> Tìm theo tình trạng, giá và địa điểm
              </span>
              <span>
                <Icon name="compare" /> So sánh trước khi chọn
              </span>
              <span>
                <Icon name="shield" /> Tiền cọc được giữ hộ qua SafePay
              </span>
            </div>
          </div>
        </section>
      )}

      {category || activeFilters || page > 1 ? null : (
        <section className="wrap category-discovery">
          <div className="section-heading">
            <div>
              <h2>Bạn đang tìm gì?</h2>
              <p className="muted">Bắt đầu từ một danh mục bạn yêu thích.</p>
            </div>
            <Link className="text-link" to="/shops">
              Khám phá gian hàng <Icon name="arrow" />
            </Link>
          </div>
          <div className="catgrid">
            {categories.map((item) => (
              <Link
                key={item.id}
                className={'catcard cat-' + item.slug}
                to={'/category/' + item.slug}
              >
                <span className="e">
                  <Icon name={categoryIcon(item.slug)} />
                </span>
                <b>{item.name}</b>
                <span>
                  Xem sản phẩm <Icon name="arrow" />
                </span>
              </Link>
            ))}
          </div>
          {banners[0] && !bannerBroken && (
            <div className="home-banner card">
              <img
                src={img(banners[0].imageUrl)}
                alt={banners[0].title || 'Ưu đãi Nola2Hand'}
                onError={() => setBannerBroken(true)}
              />
            </div>
          )}
        </section>
      )}

      <section className="wrap catalog-section" id="catalog-results">
        <div className="section-heading">
          <div>
            <span className="eyebrow">
              {category ? 'Chọn món đồ phù hợp' : 'Đồ tốt đang chờ bạn'}
            </span>
            <h2>
              {category
                ? 'Tin đăng ' + category.name.toLocaleLowerCase('vi')
                : 'Khám phá tin đăng'}
            </h2>
            <button
              type="button"
              className="btn btn-line btn-sm"
              onClick={saveSearch}
            >
              🔔 Theo dõi tìm kiếm này
            </button>
            <p className="muted">
              <b>{res?.meta?.total || 0}</b> tin đăng
              {filters.q ? ` cho “${filters.q}”` : ' đang phù hợp'}
            </p>
          </div>
          <label className="catalog-sort" htmlFor="f-sort">
            Sắp xếp
            <select
              className="input"
              id="f-sort"
              value={sort}
              onChange={(event) => setFilter('sort', event.target.value)}
            >
              <option value="">Tin nổi bật</option>
              <option value="newest">Mới nhất</option>
              <option value="price_asc">Giá thấp đến cao</option>
              <option value="price_desc">Giá cao đến thấp</option>
            </select>
          </label>
        </div>

        <div className="catalog-layout">
          <aside className="catalog-sidebar">
            <button
              type="button"
              className="btn btn-line filter-toggle"
              aria-expanded={filtersOpen}
              aria-controls="catalog-filters"
              onClick={() => setFiltersOpen((value) => !value)}
            >
              <Icon name="filter" /> Bộ lọc tìm kiếm
            </button>
            <form
              id="catalog-filters"
              className={'filter-panel card' + (filtersOpen ? ' filters-open' : '')}
              onSubmit={applyFilters}
            >
              <div className="filter-title">
                <h3>
                  <Icon name="filter" /> Bộ lọc tìm kiếm
                </h3>
                <Link to={basePath}>Đặt lại</Link>
              </div>
              <div className="form-row">
                <label className="lbl" htmlFor="filter-q">
                  Từ khóa
                </label>
                <input
                  className="input"
                  id="filter-q"
                  value={draft.q || ''}
                  placeholder="Tên món đồ..."
                  onChange={(event) => patchDraft('q', event.target.value)}
                />
              </div>
              <div className="form-row">
                <label className="lbl" htmlFor="f-city">
                  Địa điểm
                </label>
                <input
                  className="input"
                  id="f-city"
                  value={draft.city || ''}
                  placeholder="Tỉnh / thành phố"
                  onChange={(event) => patchDraft('city', event.target.value)}
                />
              </div>
              <div className="form-row">
                <label className="lbl" htmlFor="f-delivery">
                  Giao nhận
                </label>
                <select
                  className="input"
                  id="f-delivery"
                  value={draft.deliveryMethod || ''}
                  onChange={(event) =>
                    patchDraft('deliveryMethod', event.target.value)
                  }
                >
                  <option value="">Tất cả</option>
                  <option value="MEETUP">Gặp trực tiếp</option>
                  <option value="DELIVERY">Giao hàng</option>
                </select>
              </div>
              <label className="free-filter">
                <input
                  id="f-verified"
                  type="checkbox"
                  checked={draft.verified === 'true'}
                  onChange={(event) =>
                    patchDraft('verified', event.target.checked ? 'true' : '')
                  }
                />{' '}
                Người bán đã duyệt danh tính
              </label>
              <div className="form-row">
                <label className="lbl" htmlFor="f-cond">
                  Tình trạng
                </label>
                <select
                  className="input"
                  id="f-cond"
                  value={draft.condition || ''}
                  onChange={(event) =>
                    patchDraft('condition', event.target.value)
                  }
                >
                  <option value="">Tất cả tình trạng</option>
                  {Object.entries(CONDITION_NAMES).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <fieldset className="price-filter">
                <legend>Khoảng giá (đ)</legend>
                <label htmlFor="f-min" className="sr-only">
                  Giá thấp nhất
                </label>
                <input
                  className="input"
                  id="f-min"
                  type="number"
                  min="0"
                  step="1"
                  placeholder="Từ"
                  value={draft.minPrice || ''}
                  onChange={(event) => patchDraft('minPrice', event.target.value)}
                />
                <span>—</span>
                <label htmlFor="f-max" className="sr-only">
                  Giá cao nhất
                </label>
                <input
                  className="input"
                  id="f-max"
                  type="number"
                  min="0"
                  step="1"
                  placeholder="Đến"
                  value={draft.maxPrice || ''}
                  onChange={(event) => patchDraft('maxPrice', event.target.value)}
                />
              </fieldset>
              <label className="free-filter">
                <input
                  id="f-free"
                  type="checkbox"
                  checked={draft.isFree === 'true'}
                  onChange={(event) =>
                    patchDraft('isFree', event.target.checked ? 'true' : '')
                  }
                />{' '}
                Chỉ xem đồ cho tặng 0đ
              </label>
              <p id="filter-error" className="filter-error" role="alert">
                {filterError}
              </p>
              <button className="btn btn-green" type="submit">
                Áp dụng bộ lọc
              </button>
            </form>

            <nav className="category-links card" aria-label="Các danh mục">
              <h3>Danh mục khác</h3>
              <Link to="/">Tất cả tin đăng</Link>
              {categories.map((item) => (
                <Link
                  key={item.id}
                  to={'/category/' + item.slug}
                  aria-current={item.id === category?.id ? 'page' : undefined}
                >
                  <Icon name={categoryIcon(item.slug)} /> {item.name} <span>›</span>
                </Link>
              ))}
            </nav>
            <div className="safepay-note">
              <span aria-hidden="true">
                <Icon name="shield" />
              </span>
              <b>Tiền cọc được giữ hộ</b>
              <p>
                Ví SafePay giữ tiền cọc trong khi đơn hàng được xử lý. Xem kỹ
                tình trạng và trao đổi với người bán trước khi mua.
              </p>
            </div>
          </aside>

          <div className="catalog-products">
            {activeFilters && (
              <div className="active-filters">
                <div className="filter-chips">
                  {Object.entries(filters).map(([key, value]) => (
                    <button
                      key={key}
                      type="button"
                      className="chip"
                      onClick={() => setFilter(key, '')}
                    >
                      {FILTER_LABELS[key] || key}:{' '}
                      {filterValueLabel(key, value)} ×
                    </button>
                  ))}
                </div>
                <Link to={basePath}>Xóa bộ lọc ✕</Link>
              </div>
            )}

            <div className="pgrid">
              {res?.data?.length ? (
                res.data.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} />
                ))
              ) : (
                <div className="empty catalog-empty">
                  <div className="e">
                    <Icon
                      name={category ? categoryIcon(category.slug) : 'box'}
                    />
                  </div>
                  <h3>
                    {activeFilters
                      ? 'Chưa tìm thấy món đồ phù hợp'
                      : 'Danh mục này chưa có tin đăng'}
                  </h3>
                  <p>
                    {activeFilters
                      ? 'Thử thay đổi từ khóa hoặc mở rộng khoảng giá.'
                      : 'Bạn có món đồ thuộc danh mục này? Hãy là người đăng tin đầu tiên.'}
                  </p>
                  <Link
                    className="btn btn-green"
                    to={activeFilters ? basePath : '/seller/new'}
                  >
                    {activeFilters ? 'Xóa bộ lọc' : 'Đăng tin bán đồ'}
                  </Link>
                  <Link className="btn btn-line" to="/">
                    Khám phá tất cả tin đăng
                  </Link>
                </div>
              )}
            </div>

            <Pagination
              meta={res?.meta}
              onPage={(next) => setFilter('page', String(next))}
            />
          </div>
        </div>

        {!category && !activeFilters && page <= 1 && recommended?.items?.length ? (
          <>
            <h2 style={{ fontSize: 19, margin: '26px 0 14px' }}>
              ✨ Gợi ý cho bạn{' '}
              {recommended.basedOn === 'favorites' && (
                <span
                  className="muted"
                  style={{ fontSize: 12, fontWeight: 400 }}
                >
                  (dựa trên tin bạn đã lưu)
                </span>
              )}
            </h2>
            <div className="pgrid">
              {recommended.items.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          </>
        ) : null}
      </section>
    </>
  );
}
