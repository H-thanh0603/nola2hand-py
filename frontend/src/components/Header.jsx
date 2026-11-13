import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useCategories } from '../categories';
import { useSession } from '../session';
import { Avatar, Icon, useToast } from '../ui';
import { fmtVND, img, onImgError } from '../utils';

export function Topbar() {
  const { user, hasRole } = useSession();
  return (
    <div id="topbar">
      <div>Mỗi món đồ, thêm một hành trình.</div>
      <div>
        <Link to="/orders">Đơn mua</Link>
        <Link to="/returns">Trả hàng</Link>
        <Link to="/seller">Kênh người bán</Link>
        {hasRole('ADMIN_FINANCE', 'ADMIN_CONTENT') && <Link to="/admin">Quản trị</Link>}
        {!user && <Link to="/register">Đăng ký</Link>}
      </div>
    </div>
  );
}

export function Header() {
  const categories = useCategories();
  const { user, hasRole, clearSession } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();

  const [category, setCategory] = useState('');
  const [q, setQ] = useState('');
  const [suggest, setSuggest] = useState([]);
  const [highlight, setHighlight] = useState(-1);
  const [showSuggest, setShowSuggest] = useState(false);
  const [boxStyle, setBoxStyle] = useState({});
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifCount, setNotifCount] = useState(0);
  const [cartCount, setCartCount] = useState(0);

  const inputRef = useRef(null);
  const menuRef = useRef(null);
  const timer = useRef();

  const activeSlug = location.pathname.startsWith('/category/')
    ? decodeURIComponent(location.pathname.split('/')[2] || '')
    : '';

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setQ(params.get('q') || '');
    setCategory(activeSlug);
    setShowSuggest(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!user) {
      setNotifCount(0);
      setCartCount(0);
      return undefined;
    }
    let live = true;
    api('/notifications?unread=true&limit=1')
      .then((result) => live && setNotifCount(result.meta?.total || 0))
      .catch(() => {});
    api('/cart')
      .then((result) => live && setCartCount(result.items?.length || 0))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [user, location.pathname]);

  useEffect(() => {
    const close = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setMenuOpen(false);
    };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    if (q.trim().length < 2) {
      setSuggest([]);
      setShowSuggest(false);
      return undefined;
    }
    timer.current = setTimeout(() => {
      const params = new URLSearchParams({ q: q.trim(), limit: 6 });
      api('/listings?' + params, { auth: false })
        .then((result) => {
          setSuggest(result.data || []);
          setShowSuggest(true);
          setHighlight(-1);
          const rect = inputRef.current?.getBoundingClientRect();
          if (rect) {
            setBoxStyle({
              top: rect.bottom + 6,
              left: rect.left,
              width: rect.width,
            });
          }
        })
        .catch(() => setShowSuggest(false));
    }, 300);
    return () => clearTimeout(timer.current);
  }, [q]);

  function destination(slug, query) {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    const suffix = params.toString() ? '?' + params.toString() : '';
    return slug ? `/category/${encodeURIComponent(slug)}${suffix}` : `/${suffix}`;
  }

  function submitSearch() {
    if (showSuggest && highlight >= 0 && suggest[highlight]) {
      navigate('/listing/' + suggest[highlight].id);
      setShowSuggest(false);
      return;
    }
    navigate(destination(category, q.trim()));
    setShowSuggest(false);
  }

  async function logout() {
    try {
      if (user) await api('/auth/logout', { method: 'POST' });
    } catch (error) {
      if (error.status !== 401) {
        toast('Chưa thể thu hồi phiên trên máy chủ: ' + error.message, 'err');
        return;
      }
    }
    clearSession();
    navigate('/login');
  }

  return (
    <header id="site-header">
      <Link className="logo" to="/" aria-label="Nola2Hand — Trang chủ">
        <span className="brand-mark">
          <Icon name="cycle" />
        </span>
        <span>
          <span className="g">nola</span>2hand
          <span className="logo-caption">Đồ cũ. Giá trị mới.</span>
        </span>
      </Link>

      <div className="searchbar">
        <label className="sr-only" htmlFor="search-category">
          Danh mục tìm kiếm
        </label>
        <select
          id="search-category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="">Tất cả danh mục</option>
          {categories.map((item) => (
            <option key={item.id} value={item.slug}>
              {item.name}
            </option>
          ))}
        </select>
        <input
          id="q"
          ref={inputRef}
          aria-label="Từ khóa tìm kiếm"
          placeholder="Tìm món đồ bạn đang cần..."
          value={q}
          onChange={(event) => setQ(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              submitSearch();
            } else if (showSuggest && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
              event.preventDefault();
              const length = suggest.length + 1;
              setHighlight(
                (current) =>
                  (current + (event.key === 'ArrowDown' ? 1 : -1) + length) % length,
              );
            } else if (event.key === 'Escape') {
              setShowSuggest(false);
            }
          }}
          onFocus={() => q.trim().length >= 2 && setShowSuggest(true)}
          onBlur={() => setTimeout(() => setShowSuggest(false), 150)}
        />
        <button onClick={submitSearch} aria-label="Tìm kiếm">
          <Icon name="search" />
          <span>Tìm kiếm</span>
        </button>
        {showSuggest && (
          <div className="search-suggest" style={{ position: 'fixed', ...boxStyle }}>
            {suggest.map((listing, index) => (
              <button
                type="button"
                key={listing.id}
                className={index === highlight ? 'on' : ''}
                onMouseDown={(event) => {
                  event.preventDefault();
                  navigate('/listing/' + listing.id);
                  setShowSuggest(false);
                }}
                onMouseMove={() => setHighlight(index)}
              >
                <img src={img(listing.images?.[0]?.url)} alt="" onError={onImgError} />
                <span>
                  <b>{listing.title}</b>
                  <span>{listing.isFree ? 'Cho tặng 0đ' : fmtVND(listing.price)}</span>
                </span>
              </button>
            ))}
            {q.trim() && (
              <button
                type="button"
                onMouseDown={(event) => {
                  event.preventDefault();
                  submitSearch();
                }}
              >
                🔍 Xem tất cả kết quả cho “{q.trim()}”
              </button>
            )}
          </div>
        )}
      </div>

      <div className="header-actions">
        <Link className="hact" to="/notifications" aria-label="Thông báo">
          <Icon name="bell" />
          <span className="dot" style={{ display: notifCount > 0 ? 'flex' : 'none' }} />
        </Link>
        <Link className="hact desktop-action" to="/favorites" aria-label="Tin đã lưu">
          <Icon name="heart" />
        </Link>
        <Link className="hact desktop-action" to="/chat" aria-label="Tin nhắn">
          <Icon name="chat" />
        </Link>
        <Link className="hact" to="/cart" aria-label="Giỏ hàng">
          <Icon name="cart" />
          <span className="dot" style={{ display: cartCount > 0 ? 'flex' : 'none' }} />
        </Link>

        {user ? (
          <div className="u-menu" ref={menuRef}>
            <button
              type="button"
              className="u-chip"
              aria-haspopup="true"
              aria-expanded={menuOpen}
              aria-label="Tài khoản của tôi"
              onClick={(event) => {
                event.stopPropagation();
                setMenuOpen((open) => !open);
              }}
            >
              <Avatar user={user} />
              <span>{user.fullName.split(' ').slice(-2).join(' ')}</span>
              <span aria-hidden="true">▾</span>
            </button>
            <div className="u-dropdown" hidden={!menuOpen}>
              <p className="u-dropdown-head">
                <b>{user.fullName}</b>
                <span>{user.email}</span>
              </p>
              <Link to="/profile" onClick={() => setMenuOpen(false)}>👤 Hồ sơ cá nhân</Link>
              <Link to="/orders" onClick={() => setMenuOpen(false)}>📦 Đơn mua</Link>
              <Link to="/wallet" onClick={() => setMenuOpen(false)}>💰 Ví SafePay</Link>
              <Link to="/chat" onClick={() => setMenuOpen(false)}>💬 Tin nhắn</Link>
              <Link to="/notifications" onClick={() => setMenuOpen(false)}>🔔 Thông báo</Link>
              <Link to="/favorites" onClick={() => setMenuOpen(false)}>🤍 Tin đã lưu</Link>
              <Link to="/seller" onClick={() => setMenuOpen(false)}>🏪 Kênh người bán</Link>
              {hasRole('ADMIN_FINANCE', 'ADMIN_CONTENT') && (
                <Link to="/admin" onClick={() => setMenuOpen(false)}>🛠️ Trang quản trị</Link>
              )}
              <button type="button" className="u-logout" onClick={logout}>
                ↪ Đăng xuất
              </button>
            </div>
          </div>
        ) : (
          <Link className="btn btn-line btn-sm login-link" to="/login">
            Đăng nhập
          </Link>
        )}
      </div>
    </header>
  );
}

export function CatNav() {
  const categories = useCategories();
  const location = useLocation();
  const active = location.pathname.startsWith('/category/')
    ? decodeURIComponent(location.pathname.split('/')[2] || '')
    : '';

  return (
    <nav id="catnav">
      <Link to="/" className={location.pathname === '/' ? 'on' : ''}>
        <Icon name="grid" /> Khám phá
      </Link>
      {categories.slice(0, 6).map((category) => (
        <Link
          key={category.id}
          to={'/category/' + encodeURIComponent(category.slug)}
          className={active === category.slug ? 'on' : ''}
          aria-current={active === category.slug ? 'page' : undefined}
        >
          {category.name}
        </Link>
      ))}
      <Link to="/shops" className="nav-extra">
        <Icon name="shop" /> Gian hàng
      </Link>
      <Link to="/assistant" className="nav-extra">
        <Icon name="search" /> Trợ lý tìm đồ
      </Link>
      <Link className="nav-sell" to="/seller">
        <Icon name="plus" /> Đăng tin
      </Link>
    </nav>
  );
}

export function MobileNav() {
  const { user } = useSession();
  const location = useLocation();
  const current = location.pathname.split('/')[1] || '';
  const items = [
    ['', 'home', 'Khám phá'],
    ['favorites', 'heart', 'Đã lưu'],
    ['chat', 'chat', 'Tin nhắn'],
    ['orders', 'orders', 'Đơn mua'],
    [user ? 'profile' : 'login', 'user', 'Tài khoản'],
  ];
  return (
    <nav id="mobile-nav" aria-label="Điều hướng chính trên điện thoại">
      {items.map(([path, icon, label]) => (
        <Link
          key={path || 'home'}
          to={'/' + path}
          aria-current={current === path ? 'page' : undefined}
        >
          <Icon name={icon} />
          <span>{label}</span>
        </Link>
      ))}
    </nav>
  );
}
