import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, store } from './api';
import { fmtDate, fmtVND, img, IMG_PH, onImgError } from './utils';
import { CONDITION_NAMES, WORKFLOW_LABELS } from './constants';
import { useSession } from './session';
import { toggleComparison, useComparison } from './compare';

/* ---------------- icons ---------------- */
const ICON_PATHS = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  heart:
    '<path d="M20.8 5.8a5.4 5.4 0 0 0-7.6 0L12 7l-1.2-1.2a5.4 5.4 0 0 0-7.6 7.6L12 22l8.8-8.6a5.4 5.4 0 0 0 0-7.6Z"/>',
  chat:
    '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H5l-3 2V11.5A8.5 8.5 0 0 1 10.5 3h2a8.5 8.5 0 0 1 8.5 8.5Z"/><path d="M7 11h10M7 15h6"/>',
  cart:
    '<path d="M2 3h3l3 12h11l3-9H6"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/>',
  bell:
    '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/>',
  user:
    '<circle cx="12" cy="7" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>',
  home: '<path d="m3 10 9-8 9 8v11h-6v-7H9v7H3Z"/>',
  shop:
    '<path d="M3 9V4h18v5l-2 4-4-2-3 2-3-2-4 2ZM4 13v8h16v-8M9 21v-5h6v5"/>',
  grid:
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  shield:
    '<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Z"/><path d="m8 12 3 3 5-6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  cycle:
    '<path d="m17 3 4 4-4 4M21 7H9a6 6 0 0 0-6 6m4 8-4-4 4-4m-4 4h12a6 6 0 0 0 6-6"/>',
  pin:
    '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  box:
    '<path d="m12 2 9 5v10l-9 5-9-5V7Zm0 10 9-5M3 7l9 5v10M7.5 4.5l9 5v4"/>',
  wallet:
    '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 9V5l14-3v3M16 12h5v5h-5Z"/>',
  chart: '<path d="M4 3v18h18M8 16v-5m5 5V7m5 9V4"/>',
  orders:
    '<path d="M6 3h12v19l-3-2-3 2-3-2-3 2ZM9 7h6M9 11h6M9 15h4"/>',
  return: '<path d="m7 3-5 5 5 5M2 8h12a7 7 0 0 1 0 14H8"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  compare:
    '<path d="M8 3v18M16 3v18M3 8h10m-4-4 4 4-4 4m12 4H11m4-4-4 4 4 4"/>',
  star: '<path d="m12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1Z"/>',
  phone:
    '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M10 18h4M10 5h4"/>',
  sofa:
    '<path d="M5 10V6a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v4M5 10a3 3 0 0 0-3 3v6h20v-6a3 3 0 0 0-6 0v2H8v-2a3 3 0 0 0-3-3ZM5 19v3m14-3v3"/>',
  kitchen:
    '<rect x="3" y="5" width="18" height="15" rx="2"/><circle cx="12" cy="13" r="4"/><path d="M6 2v3m12-3v3M6 8h1"/>',
  shirt:
    '<path d="m8 3-6 4 3 5 3-2v12h8V10l3 2 3-5-6-4a4 4 0 0 1-8 0Z"/>',
  bike:
    '<circle cx="5" cy="17" r="4"/><circle cx="19" cy="17" r="4"/><path d="m5 17 5-9 5 9H5m5-9h6l3 9M8 5h4m3-1h3l1 4"/>',
  gift:
    '<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v9h14v-9M12 8v14M12 8C3 9 5-1 10 3l2 5c9 1 7-9 2-5Z"/>',
  filter: '<path d="M3 6h18M6 12h12M9 18h6"/>',
  eye:
    '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
};

export function Icon({ name = 'grid', className = '' }) {
  const path = ICON_PATHS[name] || ICON_PATHS.grid;
  return (
    <svg
      className={'ui-icon ' + className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: path }}
    />
  );
}

const CATEGORY_ICONS = {
  'dien-tu-cu': 'phone',
  'noi-that': 'sofa',
  'do-gia-dung': 'kitchen',
  'thoi-trang-2hand': 'shirt',
  'xe-co': 'bike',
  'cho-tang-0d': 'gift',
};
export const categoryIcon = (slug) => CATEGORY_ICONS[slug] || 'box';

/* ---------------- toast ---------------- */
const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);
  const timer = useRef();

  const show = useCallback((message, type = '') => {
    setToast({ message, type });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 3200);
  }, []);

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div id="toast-root" aria-live="polite">
        {toast && <div className={'toast ' + toast.type}>{toast.message}</div>}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

/* ---------------- modal ---------------- */
const ModalContext = createContext({ openModal: () => {}, closeModal: () => {} });

export function ModalProvider({ children }) {
  const [content, setContent] = useState(null);
  const modalRef = useRef(null);
  const triggerRef = useRef(null);

  const openModal = useCallback((node) => {
    triggerRef.current = document.activeElement;
    setContent(node);
  }, []);

  const closeModal = useCallback(() => {
    setContent(null);
    if (triggerRef.current?.isConnected) triggerRef.current.focus();
    triggerRef.current = null;
  }, []);

  useEffect(() => {
    if (!content) return undefined;
    const node = modalRef.current;
    (node?.querySelector('input:not([type=hidden]),textarea,select') || node)?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeModal();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [content, closeModal]);

  const value = useMemo(() => ({ openModal, closeModal }), [openModal, closeModal]);

  return (
    <ModalContext.Provider value={value}>
      {children}
      <div id="modal-root">
        {content && (
          <div
            className="modal-bg"
            onClick={(event) => {
              if (event.target === event.currentTarget) closeModal();
            }}
          >
            <div
              className="modal"
              role="dialog"
              aria-modal="true"
              aria-label="Hộp thoại Nola2Hand"
              tabIndex={-1}
              ref={modalRef}
            >
              <button
                type="button"
                className="modal-close"
                aria-label="Đóng hộp thoại"
                onClick={closeModal}
              >
                ×
              </button>
              {content}
            </div>
          </div>
        )}
      </div>
    </ModalContext.Provider>
  );
}

export const useModal = () => useContext(ModalContext);

/* ---------------- small pieces ---------------- */
export function Avatar({ user, size = 32 }) {
  if (user?.avatarUrl) {
    return (
      <img
        src={img(user.avatarUrl)}
        alt=""
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          objectFit: 'cover',
        }}
      />
    );
  }
  const char = (user?.fullName || '?').trim().charAt(0).toUpperCase();
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'var(--green)',
        color: '#fff',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 700,
        fontSize: size * 0.45,
        flexShrink: 0,
      }}
    >
      {char}
    </span>
  );
}

export function StatusPill({ map, status }) {
  const [label, cls] = map[status] || [status, 'p-mut'];
  return <span className={'pill ' + cls}>{label}</span>;
}

export function WorkflowBadge({ status }) {
  const cls = ['PAID', 'REFUNDED'].includes(status)
    ? 'b-green'
    : ['REJECTED', 'FAILED', 'CANCELLED'].includes(status)
      ? 'b-gray'
      : 'b-amber';
  return <span className={'badge ' + cls}>{WORKFLOW_LABELS[status] || status}</span>;
}

export function Pagination({ meta, onPage }) {
  if (!meta) return null;
  const page = meta.page;
  const last = Math.max(1, meta.totalPages);
  return (
    <nav className="catalog-pagination" aria-label="Phân trang">
      <button
        className="btn btn-line btn-sm"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        ← Trước
      </button>
      <span>
        Trang {page}/{last} · {meta.total} kết quả
      </span>
      <button
        className="btn btn-line btn-sm"
        disabled={page >= last}
        onClick={() => onPage(page + 1)}
      >
        Sau →
      </button>
    </nav>
  );
}

export function Loading({ label = 'Đang tải nội dung...' }) {
  return (
    <div className="loading-state" role="status">
      <span className="loading-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ error }) {
  const message = error?.message || 'Đã có lỗi xảy ra';
  const login = message.includes('đăng nhập') || message.includes('Token');
  return (
    <div className="empty">
      <div className="e">{login ? '🔒' : '⚠️'}</div>
      <p>{message}</p>
      <br />
      {login ? (
        <Link className="btn btn-green" to="/login">
          Đăng nhập
        </Link>
      ) : (
        <button className="btn btn-line" onClick={() => window.history.back()}>
          Quay lại
        </button>
      )}
    </div>
  );
}

export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    Promise.resolve()
      .then(fn)
      .then((data) => live && setState({ loading: false, data, error: null }))
      .catch((error) => live && setState({ loading: false, data: null, error }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((value) => value + 1) };
}

/* ---------------- listing card ---------------- */
export function ListingCard({ listing }) {
  const navigate = useNavigate();
  const toast = useToast();
  const { loggedIn } = useSession();
  const compareIds = useComparison();
  const [saved, setSaved] = useState(false);
  const thumb = listing.images?.[0]?.url || null;
  const compared = compareIds.includes(listing.id);

  async function toggleFav() {
    if (!loggedIn) {
      navigate('/login');
      return;
    }
    try {
      const result = await api('/listings/' + listing.id + '/favorite', {
        method: 'POST',
      });
      setSaved(result.favorited);
      toast(result.favorited ? 'Đã lưu tin 🤍' : 'Đã bỏ lưu', 'ok');
    } catch (error) {
      toast(error.message, 'err');
    }
  }

  function toggleCompare() {
    const result = toggleComparison(listing.id);
    if (result.limit) {
      toast('Chỉ so sánh tối đa 3 sản phẩm. Bỏ chọn một món trước.', 'err');
      return;
    }
    toast(result.added ? 'Đã thêm vào so sánh' : 'Đã bỏ khỏi so sánh', 'ok');
  }

  return (
    <article className="pcard">
      <Link className="product-image" to={'/listing/' + listing.id}>
        <img
          className="ph"
          src={img(thumb)}
          alt={listing.title}
          loading="lazy"
          onError={onImgError}
        />
      </Link>
      <button
        className={'fav' + (saved ? ' is-saved' : '')}
        onClick={(event) => {
          event.stopPropagation();
          toggleFav();
        }}
        aria-label={'Lưu tin ' + listing.title}
        aria-pressed={saved}
        title="Lưu tin"
      >
        <Icon name="heart" />
      </button>
      <div className="pb">
        <div className="product-category">
          {listing.category?.name || 'Đồ đã qua sử dụng'}
        </div>
        <Link className="product-title" to={'/listing/' + listing.id}>
          {listing.title}
        </Link>
        <div className="product-price">
          {listing.isFree ? 'Cho tặng 0đ' : fmtVND(listing.price)}
        </div>
        {CONDITION_NAMES[listing.condition] && (
          <span className="badge b-gray">
            <span className="condition-dot" />
            {CONDITION_NAMES[listing.condition]}
          </span>
        )}
        <div className="product-meta muted">
          <span>
            <Icon name="pin" />
            {listing.city || 'Liên hệ người bán'}
          </span>
          <span>
            <Icon name="eye" />
            {listing.views || 0}
          </span>
        </div>
      </div>
      <button
        className={'btn btn-line btn-sm compare-button' + (compared ? ' is-saved' : '')}
        onClick={toggleCompare}
      >
        ⇄ So sánh
      </button>
    </article>
  );
}

/* ---------------- evidence ---------------- */
export function isPrivateEvidence(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    return (
      parsed.origin === window.location.origin &&
      parsed.pathname.startsWith('/api/v1/upload/evidence/')
    );
  } catch {
    return false;
  }
}

export function useEvidenceUrl(url) {
  const [src, setSrc] = useState(() =>
    isPrivateEvidence(url) ? null : img(url),
  );

  useEffect(() => {
    let objectUrl;
    let live = true;
    if (isPrivateEvidence(url)) {
      setSrc(null);
      if (!store.token) return undefined;
      fetch(url, { headers: { Authorization: 'Bearer ' + store.token } })
        .then((response) => {
          if (!response.ok) throw new Error('Không tải được bằng chứng riêng');
          return response.blob();
        })
        .then((blob) => {
          if (!live) return;
          objectUrl = URL.createObjectURL(blob);
          setSrc(objectUrl);
        })
        .catch(() => live && setSrc(null));
    } else {
      setSrc(img(url));
    }
    return () => {
      live = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  return src;
}

export function EvidenceImage({ url, alt = 'Ảnh bằng chứng' }) {
  const src = useEvidenceUrl(url);
  return (
    <a href={src || '#'} target="_blank" rel="noopener" onClick={(e) => !src && e.preventDefault()}>
      <img src={src || IMG_PH} alt={src ? alt : 'Đang tải bằng chứng riêng'} />
    </a>
  );
}

export function EvidenceGrid({ urls = [] }) {
  if (!urls?.length) return null;
  return (
    <div className="evidence-grid">
      {urls.map((url) => (
        <EvidenceImage key={url} url={url} />
      ))}
    </div>
  );
}

export function Money({ value }) {
  return <>{fmtVND(value)}</>;
}

export function DateText({ value }) {
  return <>{fmtDate(value)}</>;
}
