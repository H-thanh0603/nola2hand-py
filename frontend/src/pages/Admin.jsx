import { Fragment, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import Chart from 'chart.js/auto';
import { api } from '../api';
import { useSession } from '../session';
import {
  Icon,
  Avatar,
  StatusPill,
  WorkflowBadge,
  Pagination,
  Loading,
  useAsync,
  EvidenceGrid,
  useToast,
  useModal,
} from '../ui';
import { fmtVND, fmtDate, img, onImgError, cleanLabel } from '../utils';
import {
  ORDER_ST,
  USER_STATUS_NAMES,
  LISTING_STATUS_NAMES,
  DISPUTE_STATUS_NAMES,
  DISPUTE_DECISIONS,
  REPORT_STATUS_NAMES,
  AUDIT_ACTIONS,
  FEE_KIND_NAMES,
  PROMO_STATUS_NAMES,
  WORKFLOW_LABELS,
  ROLE_NAMES,
  TXN_TYPE_NAMES,
  lbl,
} from '../constants';

const ADMIN_TABS = {
  content: [
    ['dashboard', '📊 Tổng quan'],
    ['pending', '📝 Tin chờ duyệt'],
    ['reports', '🚩 Báo cáo'],
    ['promos', '🎟️ Khuyến mãi'],
    ['banners', '🖼️ Banner'],
    ['users', '👥 Người dùng'],
    ['reviews', '⭐ Đánh giá'],
    ['audit', '📋 Nhật ký quản trị'],
  ],
  finance: [
    ['overview', '📊 Tổng quan'],
    ['charts', '📈 Thống kê'],
    ['orders', '🧾 Đơn hàng'],
    ['transactions', '💳 Giao dịch'],
    ['disputes', '⚖️ Tranh chấp'],
    ['fees', '💰 Phí dịch vụ'],
    ['withdrawals', '💸 Yêu cầu rút tiền'],
    ['permissions', '🔐 Phân quyền'],
    ['returns', '↩️ Trả hàng'],
    ['audit', '📋 Nhật ký quản trị'],
    ['reviews', '⭐ Đánh giá'],
  ],
};

const TAB_ICONS = {
  dashboard: 'grid',
  overview: 'grid',
  charts: 'chart',
  pending: 'box',
  orders: 'orders',
  transactions: 'wallet',
  withdrawals: 'wallet',
  disputes: 'shield',
  fees: 'chart',
  audit: 'orders',
  reviews: 'star',
  reports: 'shield',
  promos: 'gift',
  banners: 'grid',
  users: 'user',
  permissions: 'shield',
  returns: 'return',
};

const STATUS_NAMES = {
  ...REPORT_STATUS_NAMES,
  ...DISPUTE_STATUS_NAMES,
  ...LISTING_STATUS_NAMES,
  ...USER_STATUS_NAMES,
  ...WORKFLOW_LABELS,
};

const today = () => new Date().toISOString().slice(0, 10);
const daysFromNow = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);

function queryString(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null) query.set(key, String(value));
  });
  return query.toString();
}

function LoadError({ error }) {
  return (
    <p role="alert" style={{ color: 'var(--red)' }}>
      ⚠️ {error?.message || 'Đã có lỗi xảy ra'}
    </p>
  );
}

/* ---------------- audit detail ---------------- */
function AuditDetail({ detail }) {
  const d = detail || {};
  const rows = [];
  if (d.refundAmount != null) rows.push(['Hoàn vào ví', fmtVND(d.refundAmount)]);
  if (d.codAmount) rows.push(['COD hoàn ngoài ví', fmtVND(d.codAmount)]);
  if (d.amount != null) rows.push(['Số tiền', fmtVND(d.amount)]);
  if (d.fee != null) rows.push(['Phí', fmtVND(d.fee)]);
  if (d.decision) rows.push(['Quyết định', DISPUTE_DECISIONS[d.decision] || d.decision]);
  if (d.action) {
    rows.push([
      'Hành động',
      { APPROVE: 'Đã duyệt', REJECT: 'Từ chối', DELETE: 'Đã xóa' }[d.action] || d.action,
    ]);
  }
  if (Array.isArray(d.roles)) {
    rows.push(['Vai trò', d.roles.map((role) => ROLE_NAMES[role] || role).join(', ')]);
  }
  if (d.reportId != null) rows.push(['Báo cáo', '#' + d.reportId]);
  if (d.resolution) rows.push(['Ghi chú xử lý', d.resolution]);
  if (d.transferReference) rows.push(['Chứng từ', d.transferReference]);
  if (d.reason) rows.push(['Lý do', d.reason]);
  if (d.note) rows.push(['Ghi chú', d.note]);
  return rows.length ? (
    <dl className="audit-list">
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  ) : (
    <p className="muted">Không có chi tiết.</p>
  );
}

/* ---------------- shared list ---------------- */
function AdminList({ title, url, statuses, render, action }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [status, setStatus] = useState('');
  const { data, loading, error, reload } = useAsync(
    () => api(url + '?' + queryString({ page, limit: 10, q: appliedQ, status })),
    [url, page, appliedQ, status],
  );

  function submit(event) {
    event.preventDefault();
    setPage(1);
    setAppliedQ(q.trim());
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0 }}>{title}</h2>
        {action}
      </div>
      <form className="toolbar" onSubmit={submit}>
        <label className="lbl" htmlFor="admin-search">
          Tìm kiếm
        </label>
        <input
          className="input"
          id="admin-search"
          maxLength={150}
          placeholder="Nhập từ khóa"
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        {statuses && (
          <select
            className="input"
            aria-label="Trạng thái"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả trạng thái</option>
            {statuses.map((item) => (
              <option key={item} value={item}>
                {lbl(STATUS_NAMES, item)}
              </option>
            ))}
          </select>
        )}
        <button className="btn btn-green">Tìm</button>
      </form>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          {(data?.data || []).map((item) => (
            <Fragment key={item.id}>{render(item, reload)}</Fragment>
          ))}
          {!data?.data?.length && <div className="empty">Không có kết quả phù hợp.</div>}
          <Pagination meta={data?.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- moderation cards ---------------- */
function PendingCard({ listing, onChanged }) {
  const toast = useToast();
  const [busy, setBusy] = useState('');

  async function moderate(action) {
    let reason;
    if (action === 'REJECT') {
      reason = window.prompt('Lý do từ chối:');
      if (reason === null) return;
    }
    setBusy(action);
    try {
      await api(`/listings/admin/${listing.id}/moderate`, {
        method: 'PATCH',
        body: { action, reason: reason || undefined },
      });
      toast('Đã xử lý', 'ok');
      onChanged();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  return (
    <article className="sect">
      <div style={{ display: 'flex', gap: 14 }}>
        <EvidenceGrid urls={(listing.images || []).map((image) => image.url)} />
        <div style={{ flex: 1 }}>
          <b>{listing.title}</b>
          <div className="muted" style={{ fontSize: 12 }}>
            {listing.seller?.fullName || ''} · {fmtVND(listing.price)} ·{' '}
            {fmtDate(listing.createdAt)}
          </div>
          <p style={{ fontSize: 13, marginTop: 6 }}>
            {(listing.description || '').slice(0, 200)}...
          </p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => moderate('APPROVE')}>
          ✅ Duyệt
        </button>
        <button
          className="btn btn-line btn-sm"
          style={{ color: 'var(--red)' }}
          disabled={!!busy}
          onClick={() => moderate('REJECT')}
        >
          ❌ Từ chối
        </button>
      </div>
    </article>
  );
}

function ReportCard({ report, onChanged }) {
  const toast = useToast();
  const [busy, setBusy] = useState('');

  async function handle(status) {
    setBusy(status);
    try {
      await api(`/reports/admin/${report.id}`, {
        method: 'PATCH',
        body: {
          status,
          resolution: status === 'RESOLVED' ? 'Đã xử lý' : 'Không vi phạm',
        },
      });
      toast('Đã cập nhật', 'ok');
      onChanged();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  const open = ['NEW', 'REVIEWING'].includes(report.status);
  return (
    <article className="sect">
      <b>{report.reason}</b>{' '}
      <span className="pill p-bad">{lbl(REPORT_STATUS_NAMES, report.status)}</span>
      <p style={{ fontSize: 13, margin: '8px 0' }}>{report.description || ''}</p>
      <p className="muted" style={{ fontSize: 12 }}>
        Người báo cáo: {report.reporter?.fullName || ''} · {fmtDate(report.createdAt)}
      </p>
      {open ? (
        <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
          <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => handle('RESOLVED')}>
            Đã xử lý
          </button>
          <button className="btn btn-line btn-sm" disabled={!!busy} onClick={() => handle('DISMISSED')}>
            Bỏ qua
          </button>
        </div>
      ) : (
        <p>{report.resolution || ''}</p>
      )}
    </article>
  );
}

function DisputeCard({ dispute, onChanged }) {
  const toast = useToast();
  const [busy, setBusy] = useState('');

  async function resolve(decision) {
    const resolution = window.prompt('Ghi lý do và bằng chứng cho quyết định xử lý:');
    if (!resolution?.trim()) return;
    setBusy(decision);
    try {
      await api(`/disputes/admin/${dispute.id}/resolve`, {
        method: 'PATCH',
        body: { decision, resolution: resolution.trim() },
      });
      toast('Đã xử lý tranh chấp', 'ok');
      onChanged();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  const open = ['OPEN', 'REVIEWING'].includes(dispute.status);
  return (
    <article className="sect">
      <h3>
        {dispute.code} · Đơn {dispute.order?.code}
      </h3>
      <p>
        <b>{dispute.reason}</b> · {lbl(DISPUTE_STATUS_NAMES, dispute.status)}
      </p>
      <p className="preview-description">{dispute.description}</p>
      <p className="muted">
        Người mua: {dispute.buyer?.fullName || ''} · Người bán: {dispute.seller?.fullName || ''}
      </p>
      <EvidenceGrid urls={(dispute.evidences || []).map((evidence) => evidence.url)} />
      {open ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => resolve('BUYER_WINS')}>
            Hoàn tiền người mua
          </button>
          <button className="btn btn-dark btn-sm" disabled={!!busy} onClick={() => resolve('SELLER_WINS')}>
            Giải ngân người bán
          </button>
          <button className="btn btn-line btn-sm" disabled={!!busy} onClick={() => resolve('SPLIT')}>
            Chia đôi
          </button>
          <button className="btn btn-line btn-sm" disabled={!!busy} onClick={() => resolve('REJECT')}>
            Bác khiếu nại
          </button>
        </div>
      ) : (
        <p>{dispute.resolution || ''}</p>
      )}
    </article>
  );
}

function WithdrawalCard({ withdrawal: w, onChanged }) {
  const toast = useToast();
  const { user } = useSession();
  const [busy, setBusy] = useState('');
  const canHandle = w.userId !== user?.id;

  async function act(action) {
    const resolution = window.prompt('Lý do / ghi chú xử lý:');
    if (!resolution?.trim()) return;
    let transferReference;
    if (action === 'PAY') {
      transferReference = window.prompt('Mã chứng từ chuyển khoản thực tế:');
      if (!transferReference?.trim()) return;
    }
    setBusy(action);
    try {
      await api(`/admin/finance/withdrawals/${w.id}`, {
        method: 'PATCH',
        body: { action, resolution: resolution.trim(), transferReference },
      });
      toast('Đã cập nhật yêu cầu', 'ok');
      onChanged();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  return (
    <article className="workflow-card">
      <h3>{w.user?.fullName || w.reference}</h3>
      <WorkflowBadge status={w.status} />
      <p>
        Rút {fmtVND(w.amount)} · phí {fmtVND(w.fee)}
      </p>
      <p>
        {w.bankName} · {w.accountNumber} · {w.accountName}
      </p>
      <p className="muted">
        {fmtDate(w.createdAt)}
        {w.paidAt ? ' · chuyển ' + fmtDate(w.paidAt) : ''}
      </p>
      {w.resolution && <p>{w.resolution}</p>}
      {w.transferReference && <p>Chứng từ: {w.transferReference}</p>}
      <div className="workflow-actions">
        {canHandle && w.status === 'PENDING' && (
          <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => act('APPROVE')}>
            Duyệt
          </button>
        )}
        {canHandle && w.status === 'APPROVED' && (
          <>
            <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => act('PAY')}>
              Ghi nhận đã chuyển
            </button>
            <button className="btn btn-line btn-sm" disabled={!!busy} onClick={() => act('FAIL')}>
              Chuyển thất bại
            </button>
          </>
        )}
        {canHandle && ['PENDING', 'APPROVED'].includes(w.status) && (
          <button className="btn btn-line btn-sm" disabled={!!busy} onClick={() => act('REJECT')}>
            Từ chối và hoàn giữ
          </button>
        )}
      </div>
    </article>
  );
}

function ReturnCard({ request: r, onChanged }) {
  const toast = useToast();
  const [busy, setBusy] = useState('');
  const order = r.order || {};

  async function act(action) {
    const promptText =
      action === 'RECEIVE'
        ? 'Ghi nhận tình trạng hàng đã nhận lại:'
        : action === 'REFUND'
          ? 'Ghi lý do hoàn tiền SafePay:'
          : action === 'APPROVE'
            ? 'Ghi chú duyệt trả hàng:'
            : 'Lý do từ chối trả hàng:';
    const note = window.prompt(promptText);
    if (!note?.trim()) return;
    setBusy(action);
    try {
      await api(`/returns/${r.id}`, { method: 'PATCH', body: { action, note: note.trim() } });
      toast('Đã cập nhật tiến trình trả hàng', 'ok');
      onChanged();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  return (
    <article className="workflow-card">
      <h3>
        <Link to={`/orders/${order.id}`}>Đơn {order.code}</Link> · {order.listing?.title || ''}
      </h3>
      <WorkflowBadge status={r.status} />
      <ol className="return-progress">
        {['REQUESTED', 'APPROVED', 'SHIPPED', 'RECEIVED', 'REFUNDED'].map((status) => (
          <li key={status} className={status === r.status ? 'on' : ''}>
            {WORKFLOW_LABELS[status]}
          </li>
        ))}
      </ol>
      <p>{r.reason}</p>
      <p>
        Hoàn vào ví: <b>{fmtVND(r.refundAmount)}</b>
        {r.codAmount ? <> · COD hoàn ngoài ví: <b>{fmtVND(r.codAmount)}</b></> : null}
      </p>
      <p className="muted">
        Người mua: {order.buyer?.fullName || ''} · Người bán: {order.seller?.fullName || ''} ·{' '}
        {fmtDate(r.requestedAt)}
      </p>
      {r.trackingCode && <p>Gửi trả: {r.trackingCode}</p>}
      {r.receivedNote && <p>Nhận lại: {r.receivedNote}</p>}
      {r.codReference && (
        <p>
          Chứng từ COD: {r.codReference} ·{' '}
          {r.codConfirmedAt ? 'buyer đã xác nhận' : 'chờ buyer xác nhận'}
        </p>
      )}
      {r.resolution && <p>Ghi chú: {r.resolution}</p>}
      <EvidenceGrid urls={r.evidences || []} />
      <div className="workflow-actions">
        {r.status === 'REQUESTED' && (
          <>
            <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => act('APPROVE')}>
              Duyệt trả hàng
            </button>
            <button className="btn btn-line btn-sm" disabled={!!busy} onClick={() => act('REJECT')}>
              Từ chối
            </button>
          </>
        )}
        {r.status === 'SHIPPED' && (
          <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => act('RECEIVE')}>
            Xác nhận đã nhận hàng trả
          </button>
        )}
        {r.status === 'RECEIVED' && (
          <button className="btn btn-green btn-sm" disabled={!!busy} onClick={() => act('REFUND')}>
            Hoàn tiền SafePay
          </button>
        )}
      </div>
    </article>
  );
}

/* ---------------- content views ---------------- */
function ContentOverview() {
  const { data, loading, error } = useAsync(
    () =>
      Promise.all([
        api('/admin/users/stats'),
        api('/reports/admin/stats'),
        api('/listings/admin/pending?limit=1'),
      ]),
    [],
  );
  if (loading) return <Loading />;
  if (error) return <LoadError error={error} />;
  const [users, reports, pending] = data;
  return (
    <>
      <h2 style={{ marginBottom: 16 }}>📊 Tổng quan nội dung</h2>
      <div className="stat-grid">
        <div className="stat">
          <div className="t">Tổng người dùng</div>
          <div className="v">{users.total || 0}</div>
        </div>
        <div className="stat">
          <div className="t">Đang hoạt động</div>
          <div className="v" style={{ color: 'var(--green-dark)' }}>{users.active || 0}</div>
        </div>
        <div className="stat">
          <div className="t">Tin chờ duyệt</div>
          <div className="v" style={{ color: 'var(--amber)' }}>{pending.meta?.total || 0}</div>
        </div>
        <div className="stat">
          <div className="t">Báo cáo mới</div>
          <div className="v" style={{ color: 'var(--red)' }}>{reports.new || 0}</div>
        </div>
      </div>
      <div className="row2" style={{ alignItems: 'start' }}>
        <div className="sect">
          <h2>📝 Cần xử lý</h2>
          <p className="muted">
            {pending.meta?.total || 0} tin chờ duyệt · {reports.new || 0} báo cáo mới ·{' '}
            {reports.reviewing || 0} báo cáo đang xem xét.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Link className="btn btn-green btn-sm" to="/admin/pending">Duyệt tin</Link>
            <Link className="btn btn-line btn-sm" to="/admin/reports">Xem báo cáo</Link>
            <Link className="btn btn-line btn-sm" to="/admin/users">Quản lý người dùng</Link>
          </div>
        </div>
        <div className="sect">
          <h2>👥 Tài khoản</h2>
          <p className="muted">
            {users.pendingVerification || 0} chờ xác minh · {users.banned || 0} đã khóa.
          </p>
          <Link className="btn btn-line btn-sm" to="/admin/users">Mở danh sách</Link>
        </div>
      </div>
    </>
  );
}

function PendingView() {
  return (
    <AdminList
      title="📝 Tin chờ duyệt"
      url="/listings/admin/pending"
      render={(listing, reload) => <PendingCard listing={listing} onChanged={reload} />}
    />
  );
}

function ReportsView() {
  return (
    <AdminList
      title="🚩 Báo cáo vi phạm"
      url="/reports/admin/all"
      statuses={['NEW', 'REVIEWING', 'RESOLVED', 'DISMISSED']}
      render={(report, reload) => <ReportCard report={report} onChanged={reload} />}
    />
  );
}

function AuditView() {
  return (
    <AdminList
      title="📋 Nhật ký quản trị"
      url="/admin/audit"
      render={(entry) => (
        <article className="sect">
          <h3>
            {lbl(AUDIT_ACTIONS, entry.action)} · {entry.target}
          </h3>
          <p>
            {entry.admin?.fullName || ''} · {fmtDate(entry.createdAt)}
          </p>
          <AuditDetail detail={entry.detail} />
        </article>
      )}
    />
  );
}

function ReviewsView() {
  const { data, loading, error } = useAsync(() => api('/reviews/insights'), []);
  if (loading) return <Loading />;
  if (error) return <LoadError error={error} />;
  return (
    <section className="sect">
      <h2>⭐ Phân tích đánh giá</h2>
      <p className="muted">
        Tối đa 500 đánh giá mới nhất; nhãn ước lượng không thay thế nội dung gốc.
      </p>
      <div className="stat-grid">
        {data.sentiments.map((item) => (
          <div className="stat" key={item.sentiment}>
            <div className="t">
              {{ POSITIVE: 'Tích cực', NEUTRAL: 'Trung lập', NEGATIVE: 'Tiêu cực' }[
                item.sentiment
              ] || item.sentiment}
            </div>
            <div className="v">{item.count}</div>
          </div>
        ))}
      </div>
      <p>
        Điểm trung bình {Number(data.averageRating || 0).toFixed(1)}/5 · {data.sampleSize} đánh
        giá · {data.sources.ai} nhãn AI, {data.sources.local} nhãn cục bộ.
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

/* ---------------- users ---------------- */
function UsersView() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState('');
  const stats = useAsync(() => api('/admin/users/stats'), []);
  const list = useAsync(
    () => api('/admin/users?' + queryString({ page, limit: 10, q: appliedQ, status })),
    [page, appliedQ, status],
  );
  const reload = () => {
    list.reload();
    stats.reload();
  };

  async function lockUser(target, action) {
    let reason = 'Mở khoá bởi admin';
    if (action === 'lock') {
      reason = window.prompt('Lý do khoá tài khoản:');
      if (!reason) return;
    }
    setBusy(`${target.id}:${action}`);
    try {
      await api(`/admin/users/${target.id}/${action}`, { method: 'PATCH', body: { reason } });
      toast('Đã cập nhật', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  async function verifyUser(target) {
    setBusy(`${target.id}:verify`);
    try {
      await api(`/admin/users/${target.id}/verify`, { method: 'PATCH' });
      toast('Đã duyệt xác minh', 'ok');
      reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy('');
    }
  }

  function submit(event) {
    event.preventDefault();
    setPage(1);
    setAppliedQ(q.trim());
  }

  return (
    <>
      <h2 style={{ marginBottom: 16 }}>👥 Người dùng</h2>
      <div className="stat-grid">
        <div className="stat">
          <div className="t">Tổng người dùng</div>
          <div className="v">{stats.data?.total ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="t">Đang hoạt động</div>
          <div className="v" style={{ color: 'var(--green-dark)' }}>{stats.data?.active ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="t">Chờ xác minh</div>
          <div className="v" style={{ color: 'var(--amber)' }}>{stats.data?.pendingVerification ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="t">Đã khóa</div>
          <div className="v" style={{ color: 'var(--red)' }}>{stats.data?.banned ?? '—'}</div>
        </div>
      </div>
      <form className="toolbar" onSubmit={submit}>
        <input
          className="input"
          placeholder="Tên, email hoặc số điện thoại"
          value={q}
          maxLength={150}
          onChange={(event) => setQ(event.target.value)}
        />
        <select
          className="input"
          aria-label="Trạng thái"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Tất cả trạng thái</option>
          {Object.keys(USER_STATUS_NAMES).map((item) => (
            <option key={item} value={item}>{USER_STATUS_NAMES[item]}</option>
          ))}
        </select>
        <button className="btn btn-green">Tìm</button>
      </form>
      {list.loading ? (
        <Loading />
      ) : list.error ? (
        <LoadError error={list.error} />
      ) : (
        <>
          <div className="tblwrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Người dùng</th>
                  <th>Email</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th>Xác minh</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data?.data || []).map((target) => (
                  <tr key={target.id}>
                    <td>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        <Avatar user={target} size={32} />
                        <b>{target.fullName}</b>
                      </div>
                    </td>
                    <td className="muted">{target.email}</td>
                    <td>
                      {(target.roles || []).map((role) => (
                        <span className="pill p-info" style={{ marginRight: 4 }} key={role}>
                          {ROLE_NAMES[role] || role}
                        </span>
                      ))}
                    </td>
                    <td>
                      {target.status === 'BANNED' ? (
                        <span className="pill p-bad">Đã khoá</span>
                      ) : (
                        <span className={`pill ${target.status === 'ACTIVE' ? 'p-ok' : 'p-warn'}`}>
                          {USER_STATUS_NAMES[target.status] || target.status}
                        </span>
                      )}
                    </td>
                    <td>
                      {target.idVerified ? (
                        <span className="pill p-ok">Đã xác minh</span>
                      ) : (
                        <button
                          className="btn btn-line btn-sm"
                          disabled={busy === `${target.id}:verify`}
                          onClick={() => verifyUser(target)}
                        >
                          Duyệt xác minh
                        </button>
                      )}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {target.status === 'BANNED' ? (
                        <button
                          className="btn btn-green btn-sm"
                          disabled={busy === `${target.id}:unlock`}
                          onClick={() => lockUser(target, 'unlock')}
                        >
                          Mở khoá
                        </button>
                      ) : (
                        <button
                          className="btn btn-line btn-sm"
                          style={{ color: 'var(--red)' }}
                          disabled={busy === `${target.id}:lock`}
                          onClick={() => lockUser(target, 'lock')}
                        >
                          Khoá
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!list.data?.data?.length && <div className="empty">Không có người dùng phù hợp.</div>}
          <Pagination meta={list.data?.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- promos ---------------- */
function PromoForm({ promo, onSaved, close }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    code: promo?.code || '',
    name: promo?.name || '',
    type: promo?.type || 'VOUCHER',
    discountType: promo?.discountType || 'AMOUNT',
    discountValue: promo?.discountValue ?? 10000,
    minOrder: promo?.minOrder ?? 0,
    from: promo?.startsAt ? new Date(promo.startsAt).toISOString().slice(0, 10) : today(),
    to: promo?.endsAt ? new Date(promo.endsAt).toISOString().slice(0, 10) : daysFromNow(30),
    status: promo?.status || 'ACTIVE',
  });
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const body = {
        code: form.code || undefined,
        name: form.name,
        type: form.type,
        discountType: form.discountType,
        discountValue: Number(form.discountValue),
        minOrder: Number(form.minOrder) || 0,
        startsAt: new Date(form.from).toISOString(),
        endsAt: new Date(form.to).toISOString(),
        status: form.status,
      };
      if (promo) {
        await api(`/promos/admin/${promo.id}`, { method: 'PATCH', body });
      } else {
        await api('/promos/admin', { method: 'POST', body });
      }
      toast(promo ? 'Đã cập nhật khuyến mãi' : 'Đã tạo khuyến mãi', 'ok');
      close();
      onSaved();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>🎟️ {promo ? 'Sửa khuyến mãi' : 'Tạo khuyến mãi'}</h3>
      <div className="form-row">
        <label className="lbl">Mã *</label>
        <input className="input" value={form.code} onChange={set('code')} placeholder="VD: GIAM10K" />
      </div>
      <div className="form-row">
        <label className="lbl">Tên *</label>
        <input className="input" value={form.name} onChange={set('name')} required />
      </div>
      <div className="row2">
        <div className="form-row">
          <label className="lbl">Loại KM</label>
          <select className="input" value={form.type} onChange={set('type')}>
            <option value="VOUCHER">Voucher giảm giá</option>
            <option value="FREESHIP">Miễn phí ship</option>
            <option value="PLATFORM_FEE_DISCOUNT">Giảm phí sàn</option>
            <option value="BOOST">Đẩy tin</option>
          </select>
        </div>
        <div className="form-row">
          <label className="lbl">Kiểu giảm</label>
          <select className="input" value={form.discountType} onChange={set('discountType')}>
            <option value="AMOUNT">Giảm tiền (đ)</option>
            <option value="PERCENT">Giảm %</option>
          </select>
        </div>
      </div>
      <div className="row2">
        <div className="form-row">
          <label className="lbl">Giá trị *</label>
          <input className="input" type="number" value={form.discountValue} onChange={set('discountValue')} required />
        </div>
        <div className="form-row">
          <label className="lbl">Đơn tối thiểu (đ)</label>
          <input className="input" type="number" value={form.minOrder} onChange={set('minOrder')} />
        </div>
      </div>
      <div className="row2">
        <div className="form-row">
          <label className="lbl">Từ ngày</label>
          <input className="input" type="date" value={form.from} onChange={set('from')} />
        </div>
        <div className="form-row">
          <label className="lbl">Đến ngày</label>
          <input className="input" type="date" value={form.to} onChange={set('to')} />
        </div>
      </div>
      <div className="form-row">
        <label className="lbl">Trạng thái</label>
        <select className="input" value={form.status} onChange={set('status')}>
          {Object.keys(PROMO_STATUS_NAMES).map((status) => (
            <option key={status} value={status}>{PROMO_STATUS_NAMES[status]}</option>
          ))}
        </select>
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {promo ? 'Lưu thay đổi' : 'Tạo & kích hoạt'}
      </button>
    </form>
  );
}

function PromosView() {
  const toast = useToast();
  const { openModal, closeModal } = useModal();
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState(null);
  const { data, loading, error, reload } = useAsync(
    () => api(`/promos/admin/all?page=${page}&limit=20`),
    [page],
  );
  const promos = data?.data || [];

  async function remove(promo) {
    if (!window.confirm('Xoá?')) return;
    setDeleting(promo.id);
    try {
      await api('/promos/admin/' + promo.id, { method: 'DELETE' });
      toast('Đã xoá', 'ok');
      reload();
    } catch (caught) {
      toast(caught.message, 'err');
    } finally {
      setDeleting(null);
    }
  }

  function edit(promo) {
    openModal(<PromoForm promo={promo} close={closeModal} onSaved={reload} />);
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h2>🎟️ Khuyến mãi</h2>
        <button className="btn btn-green btn-sm" onClick={() => edit(null)}>+ Tạo mới</button>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          <div className="tblwrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Tên</th>
                  <th>Giảm</th>
                  <th>Hiệu lực</th>
                  <th>Trạng thái</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {promos.map((promo) => (
                  <tr key={promo.id}>
                    <td><b style={{ fontFamily: 'monospace' }}>{promo.code}</b></td>
                    <td>{promo.name}</td>
                    <td>
                      <b>
                        {promo.discountType === 'PERCENT'
                          ? promo.discountValue + '%'
                          : fmtVND(promo.discountValue)}
                      </b>
                    </td>
                    <td className="muted" style={{ fontSize: 11.5 }}>
                      {fmtDate(promo.startsAt)} → {fmtDate(promo.endsAt)}
                    </td>
                    <td>
                      {promo.status === 'ACTIVE' ? (
                        <span className="pill p-ok">Đang chạy</span>
                      ) : (
                        <span className="pill p-mut">
                          {PROMO_STATUS_NAMES[promo.status] || promo.status}
                        </span>
                      )}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn btn-line btn-sm" onClick={() => edit(promo)}>Sửa</button>{' '}
                      <button
                        className="btn btn-line btn-sm"
                        style={{ color: 'var(--red)' }}
                        disabled={deleting === promo.id}
                        onClick={() => remove(promo)}
                      >
                        Xoá
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!promos.length && <div className="empty">Chưa có khuyến mãi.</div>}
          <Pagination meta={data?.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- banners ---------------- */
function BannerForm({ banner, onSaved, close }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: banner?.title || '',
    imageUrl: banner?.imageUrl || '',
    position: banner?.position || 'HOME_HERO',
    from: banner?.startsAt ? new Date(banner.startsAt).toISOString().slice(0, 10) : today(),
    to: banner?.endsAt ? new Date(banner.endsAt).toISOString().slice(0, 10) : daysFromNow(30),
    status: banner?.status || 'ACTIVE',
  });
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const body = {
        title: form.title,
        imageUrl: form.imageUrl,
        position: form.position,
        startsAt: new Date(form.from).toISOString(),
        endsAt: new Date(form.to).toISOString(),
        status: form.status,
      };
      if (banner) {
        await api(`/banners/admin/${banner.id}`, { method: 'PATCH', body });
      } else {
        await api('/banners/admin', { method: 'POST', body });
      }
      toast(banner ? 'Đã cập nhật banner' : 'Đã tạo banner', 'ok');
      close();
      onSaved();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>🖼️ {banner ? 'Sửa banner' : 'Tạo banner'}</h3>
      <div className="form-row">
        <label className="lbl">Tiêu đề *</label>
        <input className="input" value={form.title} onChange={set('title')} required />
      </div>
      <div className="form-row">
        <label className="lbl">URL ảnh *</label>
        <input className="input" value={form.imageUrl} onChange={set('imageUrl')} placeholder="https://..." required />
      </div>
      <div className="form-row">
        <label className="lbl">Vị trí</label>
        <select className="input" value={form.position} onChange={set('position')}>
          <option value="HOME_HERO">Trang chủ (hero)</option>
          <option value="HOME_SECONDARY">Trang chủ (phụ)</option>
          <option value="CATEGORY">Đầu trang danh mục</option>
        </select>
      </div>
      <div className="row2">
        <div className="form-row">
          <label className="lbl">Từ ngày</label>
          <input className="input" type="date" value={form.from} onChange={set('from')} />
        </div>
        <div className="form-row">
          <label className="lbl">Đến ngày</label>
          <input className="input" type="date" value={form.to} onChange={set('to')} />
        </div>
      </div>
      <div className="form-row">
        <label className="lbl">Trạng thái</label>
        <select className="input" value={form.status} onChange={set('status')}>
          {Object.keys(PROMO_STATUS_NAMES).map((status) => (
            <option key={status} value={status}>{PROMO_STATUS_NAMES[status]}</option>
          ))}
        </select>
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {banner ? 'Lưu thay đổi' : 'Tạo & kích hoạt'}
      </button>
    </form>
  );
}

function BannersView() {
  const toast = useToast();
  const { openModal, closeModal } = useModal();
  const [page, setPage] = useState(1);
  const [deleting, setDeleting] = useState(null);
  const { data, loading, error, reload } = useAsync(
    () => api(`/banners/admin/all?page=${page}&limit=20`),
    [page],
  );
  const banners = data?.data || [];

  async function remove(banner) {
    if (!window.confirm('Xoá?')) return;
    setDeleting(banner.id);
    try {
      await api('/banners/admin/' + banner.id, { method: 'DELETE' });
      toast('Đã xoá', 'ok');
      reload();
    } catch (caught) {
      toast(caught.message, 'err');
    } finally {
      setDeleting(null);
    }
  }

  function edit(banner) {
    openModal(<BannerForm banner={banner} close={closeModal} onSaved={reload} />);
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h2>🖼️ Banner</h2>
        <button className="btn btn-green btn-sm" onClick={() => edit(null)}>+ Tạo mới</button>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          {banners.map((banner) => (
            <div
              className="sect"
              style={{ display: 'flex', gap: 14, alignItems: 'center' }}
              key={banner.id}
            >
              <img
                src={img(banner.imageUrl)}
                alt={banner.title}
                onError={onImgError}
                style={{ width: 160, height: 70, objectFit: 'cover', borderRadius: 8 }}
              />
              <div style={{ flex: 1 }}>
                <b>{banner.title}</b>
                <div className="muted" style={{ fontSize: 12 }}>
                  {banner.position} · {banner.status === 'ACTIVE' ? 'Đang hiển thị' : banner.status}
                </div>
              </div>
              <button className="btn btn-line btn-sm" onClick={() => edit(banner)}>Sửa</button>
              <button
                className="btn btn-line btn-sm"
                style={{ color: 'var(--red)' }}
                disabled={deleting === banner.id}
                onClick={() => remove(banner)}
              >
                Xoá
              </button>
            </div>
          ))}
          {!banners.length && <div className="empty">Chưa có banner.</div>}
          <Pagination meta={data?.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- finance overview ---------------- */
function FinanceOverview() {
  const navigate = useNavigate();
  const { data, loading, error } = useAsync(() => api('/admin/finance/overview'), []);
  if (loading) return <Loading />;
  if (error) return <LoadError error={error} />;
  const k = data.kpis || {};
  return (
    <>
      <h2 style={{ marginBottom: 16 }}>📊 Tổng quan tài chính</h2>
      <div className="stat-grid">
        <div className="stat">
          <div className="t">Doanh thu tháng này</div>
          <div className="v" style={{ color: 'var(--green-dark)' }}>{fmtVND(k.monthlyRevenue)}</div>
        </div>
        <div className="stat">
          <div className="t">Tổng giao dịch ví</div>
          <div className="v">{k.totalTransactions || 0}</div>
        </div>
        <div className="stat">
          <div className="t">Hoàn tiền chờ duyệt</div>
          <div className="v" style={{ color: 'var(--amber)' }}>{k.pendingRefunds || 0}</div>
        </div>
        <div className="stat">
          <div className="t">Tranh chấp đang mở</div>
          <div className="v" style={{ color: 'var(--red)' }}>{k.openDisputes || 0}</div>
        </div>
      </div>
      <div className="row2" style={{ alignItems: 'start' }}>
        <div className="sect">
          <h2>💳 Giao dịch gần đây</h2>
          {(data.recentTransactions || []).slice(0, 5).map((txn) => (
            <div
              key={txn.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '8px 0',
                borderBottom: '1px solid #f0f3f1',
                fontSize: 13,
              }}
            >
              <span>
                <b>{TXN_TYPE_NAMES[txn.type] || txn.type}</b>{' '}
                <span className="muted">#{txn.id}</span>
              </span>
              <b style={{ color: txn.amount >= 0 ? 'var(--green-dark)' : 'var(--red)' }}>
                {fmtVND(txn.amount)}
              </b>
            </div>
          ))}
          {!data.recentTransactions?.length && <p className="muted">Chưa có.</p>}
          <Link className="btn btn-line btn-sm" to="/admin/transactions">Xem tất cả</Link>
        </div>
        <div className="sect">
          <h2>⚖️ Tranh chấp gần đây</h2>
          {(data.recentDisputes || []).slice(0, 5).map((dispute) => (
            <button
              type="button"
              key={dispute.id}
              onClick={() => navigate('/admin/disputes')}
              style={{
                display: 'flex',
                width: '100%',
                justifyContent: 'space-between',
                gap: 10,
                padding: '8px 0',
                border: 0,
                borderBottom: '1px solid #f0f3f1',
                background: 'none',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: 13,
              }}
            >
              <span>
                <b>{dispute.code}</b> {dispute.reason || ''}
              </span>
              <span className="pill p-bad">
                {DISPUTE_STATUS_NAMES[dispute.status] || dispute.status}
              </span>
            </button>
          ))}
          {!data.recentDisputes?.length && <p className="muted">Không có.</p>}
        </div>
      </div>
    </>
  );
}

/* ---------------- charts ---------------- */
function ChartsView() {
  const [draft, setDraft] = useState({
    from: new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10),
    to: today(),
  });
  const [range, setRange] = useState(draft);
  const barRef = useRef(null);
  const pieRef = useRef(null);
  const { data, loading, error } = useAsync(
    () =>
      Promise.all([
        api(`/admin/finance/charts/revenue?from=${range.from}&to=${range.to}`),
        api('/admin/finance/charts/order-status'),
      ]),
    [range.from, range.to],
  );
  const revenue = data?.[0]?.data || [];
  const statuses = data?.[1] || [];
  const totalRevenue = revenue.reduce((sum, row) => sum + row.revenue, 0);
  const totalOrders = revenue.reduce((sum, row) => sum + row.orders, 0);

  useEffect(() => {
    if (!data || !barRef.current || !pieRef.current) return undefined;
    Chart.defaults.font.family = "'Be Vietnam Pro', system-ui, sans-serif";
    Chart.defaults.color = '#718178';
    const bar = new Chart(barRef.current, {
      type: 'bar',
      data: {
        labels: revenue.map((row) => row.date.slice(5)),
        datasets: [
          {
            label: 'Doanh thu (đ)',
            data: revenue.map((row) => row.revenue),
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
            suggestedMax: revenue.some((row) => row.revenue > 0) ? undefined : 100000,
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
    const pie = new Chart(pieRef.current, {
      type: 'pie',
      data: {
        labels: statuses.map((row) => (ORDER_ST[row.status] || [row.status])[0]),
        datasets: [
          {
            data: statuses.map((row) => row.count),
            backgroundColor: ['#087f5b', '#4a80b5', '#d8ad4e', '#c86469', '#8a75b4', '#8b9d92', '#66b3b6'],
          },
        ],
      },
      options: { responsive: true, plugins: { legend: { position: 'right' } } },
    });
    return () => {
      bar.destroy();
      pie.destroy();
    };
  }, [data]);

  return (
    <>
      <h2 style={{ marginBottom: 16 }}>📈 Thống kê doanh thu</h2>
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          setRange(draft);
        }}
      >
        <label className="muted" style={{ alignSelf: 'center', fontSize: 13 }}>Từ ngày</label>
        <input
          type="date"
          className="input"
          value={draft.from}
          onChange={(event) => setDraft({ ...draft, from: event.target.value })}
        />
        <label className="muted" style={{ alignSelf: 'center', fontSize: 13 }}>đến</label>
        <input
          type="date"
          className="input"
          value={draft.to}
          onChange={(event) => setDraft({ ...draft, to: event.target.value })}
        />
        <button className="btn btn-green btn-sm">
          <Icon name="chart" /> Xem
        </button>
      </form>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          <div className="row2" style={{ gridTemplateColumns: '1.6fr 1fr', alignItems: 'start' }}>
            <div className="sect">
              <h2>📊 Doanh thu theo ngày</h2>
              <canvas ref={barRef} height={120} />
            </div>
            <div className="sect">
              <h2>🥧 Đơn hàng theo trạng thái</h2>
              <canvas ref={pieRef} height={160} />
            </div>
          </div>
          <div className="sect">
            <h2>📋 Số liệu chi tiết</h2>
            <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
              <div className="stat">
                <div className="t">Tổng doanh thu ({range.from} → {range.to})</div>
                <div className="v" style={{ color: 'var(--green-dark)' }}>{fmtVND(totalRevenue)}</div>
              </div>
              <div className="stat">
                <div className="t">Tổng đơn hàng</div>
                <div className="v">{totalOrders}</div>
              </div>
              <div className="stat">
                <div className="t">Phí thu / đơn phát sinh</div>
                <div className="v">
                  {totalOrders ? fmtVND(Math.round(totalRevenue / totalOrders)) : '—'}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}

/* ---------------- orders ---------------- */
function OrdersView() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const { data, loading, error } = useAsync(
    () =>
      api('/orders/admin/all?' + queryString({ page, limit: 30, status, q: appliedQ })),
    [page, status, appliedQ],
  );

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        <h2>🧾 Quản lý đơn hàng ({data?.meta?.total ?? 0})</h2>
        <form
          className="toolbar"
          style={{ margin: 0 }}
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedQ(q.trim());
          }}
        >
          <select
            className="input"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Tất cả trạng thái</option>
            {Object.keys(ORDER_ST).map((item) => (
              <option key={item} value={item}>{ORDER_ST[item][0]}</option>
            ))}
          </select>
          <input
            className="input"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Tìm mã đơn..."
            style={{ minWidth: 150 }}
          />
          <button className="btn btn-line btn-sm">Tìm</button>
        </form>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          <div className="tblwrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Mã đơn</th>
                  <th>Sản phẩm</th>
                  <th>Người mua</th>
                  <th>Người bán</th>
                  <th>Tổng tiền</th>
                  <th>Trạng thái</th>
                  <th>Ngày tạo</th>
                </tr>
              </thead>
              <tbody>
                {(data?.data || []).map((order) => (
                  <tr
                    key={order.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/orders/${order.id}`)}
                  >
                    <td><b>#{order.code}</b></td>
                    <td>{(order.listing?.title || '').slice(0, 35)}</td>
                    <td>{order.buyer?.fullName}</td>
                    <td>{order.seller?.fullName}</td>
                    <td><b>{fmtVND(order.totalAmount)}</b></td>
                    <td><StatusPill map={ORDER_ST} status={order.status} /></td>
                    <td className="muted">{fmtDate(order.createdAt)}</td>
                  </tr>
                ))}
                {!data?.data?.length && (
                  <tr>
                    <td colSpan={7} className="muted">Không có đơn nào.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={data?.meta} onPage={setPage} />
          <p className="muted">Bấm vào dòng để xem chi tiết.</p>
        </>
      )}
    </>
  );
}

/* ---------------- transactions ---------------- */
function TransactionsView() {
  const [page, setPage] = useState(1);
  const [form, setForm] = useState({ type: '', q: '', from: '', to: '' });
  const [filters, setFilters] = useState(form);
  const { data, loading, error } = useAsync(
    () => api('/admin/finance/transactions?' + queryString({ ...filters, page, limit: 30 })),
    [page, filters.type, filters.q, filters.from, filters.to],
  );
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  return (
    <>
      <h2 style={{ marginBottom: 16 }}>💳 Giao dịch ví</h2>
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setFilters({ ...form, q: form.q.trim() });
        }}
      >
        <select className="input" value={form.type} onChange={set('type')}>
          <option value="">Tất cả loại</option>
          {Object.keys(TXN_TYPE_NAMES).map((type) => (
            <option key={type} value={type}>{TXN_TYPE_NAMES[type]}</option>
          ))}
        </select>
        <input
          className="input"
          placeholder="Mã tham chiếu, ghi chú, người dùng"
          value={form.q}
          onChange={set('q')}
        />
        <input className="input" type="date" aria-label="Từ ngày" value={form.from} onChange={set('from')} />
        <input className="input" type="date" aria-label="Đến ngày" value={form.to} onChange={set('to')} />
        <button className="btn btn-green btn-sm">Tìm</button>
      </form>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          <div className="tblwrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Người dùng</th>
                  <th>Loại</th>
                  <th>Số tiền</th>
                  <th>Tham chiếu</th>
                  <th>Ghi chú</th>
                  <th>Ngày</th>
                </tr>
              </thead>
              <tbody>
                {(data?.data || []).map((txn) => (
                  <tr key={txn.id}>
                    <td className="muted">#{txn.id}</td>
                    <td>{txn.wallet?.user?.fullName || '—'}</td>
                    <td><b>{TXN_TYPE_NAMES[txn.type] || txn.type}</b></td>
                    <td
                      style={{
                        fontWeight: 700,
                        color: txn.amount >= 0 ? 'var(--green-dark)' : 'var(--red)',
                      }}
                    >
                      {fmtVND(txn.amount)}
                    </td>
                    <td className="muted">{txn.reference || ''}</td>
                    <td className="muted">{txn.note || ''}</td>
                    <td className="muted">{fmtDate(txn.createdAt)}</td>
                  </tr>
                ))}
                {!data?.data?.length && (
                  <tr>
                    <td colSpan={7} className="muted">Không có giao dịch phù hợp.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <Pagination meta={data?.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- withdrawals / disputes / returns ---------------- */
function WithdrawalsView() {
  return (
    <AdminList
      title="💸 Yêu cầu rút tiền"
      url="/admin/finance/withdrawals"
      statuses={['PENDING', 'APPROVED', 'PAID', 'REJECTED', 'FAILED', 'CANCELLED']}
      render={(withdrawal, reload) => (
        <WithdrawalCard withdrawal={withdrawal} onChanged={reload} />
      )}
    />
  );
}

function DisputesView() {
  return (
    <AdminList
      title="⚖️ Tranh chấp"
      url="/disputes/admin/all"
      statuses={['OPEN', 'REVIEWING', 'CLOSED', 'REFUNDED', 'REJECTED']}
      render={(dispute, reload) => <DisputeCard dispute={dispute} onChanged={reload} />}
    />
  );
}

function ReturnsView() {
  return (
    <AdminList
      title="↩️ Tiến trình trả hàng"
      url="/returns/admin"
      statuses={['REQUESTED', 'APPROVED', 'SHIPPED', 'RECEIVED', 'REFUNDED', 'REJECTED', 'CANCELLED']}
      render={(request, reload) => <ReturnCard request={request} onChanged={reload} />}
    />
  );
}

/* ---------------- permissions ---------------- */
function RolesForm({ target, onSaved, close }) {
  const toast = useToast();
  const [roles, setRoles] = useState(target.roles || []);
  const [busy, setBusy] = useState(false);

  function toggle(role) {
    setRoles((current) =>
      current.includes(role) ? current.filter((item) => item !== role) : [...current, role],
    );
  }

  async function submit(event) {
    event.preventDefault();
    if (!roles.length) {
      toast('Chọn ít nhất một vai trò', 'err');
      return;
    }
    setBusy(true);
    try {
      await api(`/admin/users/${target.id}/roles`, { method: 'PATCH', body: { roles } });
      toast('Đã đổi quyền và thu hồi phiên cũ', 'ok');
      close();
      onSaved();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h2>Chọn vai trò</h2>
      <p className="muted">Chọn đầy đủ các vai trò cần giữ cho tài khoản.</p>
      {Object.entries(ROLE_NAMES).map(([role, label]) => (
        <label className="role-option" key={role}>
          <input
            type="checkbox"
            value={role}
            checked={roles.includes(role)}
            onChange={() => toggle(role)}
          />{' '}
          {label}
        </label>
      ))}
      <button className="btn btn-green" disabled={busy}>Lưu vai trò</button>
    </form>
  );
}

function PermissionsView() {
  const { user } = useSession();
  const toast = useToast();
  const { openModal, closeModal } = useModal();
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useAsync(
    () => api(`/admin/users?page=${page}&limit=10`),
    [page],
  );

  if (!user?.canManageRoles) {
    return <div className="empty"><div className="e">🔒</div>Cần quyền quản lý phân quyền riêng</div>;
  }

  function edit(target) {
    if (target.id === user.id) {
      toast('Không được thay đổi vai trò của chính mình', 'err');
      return;
    }
    openModal(<RolesForm target={target} close={closeModal} onSaved={reload} />);
  }

  return (
    <>
      <h2>Phân quyền tài khoản</h2>
      <p className="muted">
        Không được đổi quyền của chính mình. Đổi role thu hồi phiên của tài khoản được sửa.
      </p>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          {(data?.data || []).map((target) => (
            <article className="workflow-card" key={target.id}>
              <b>{target.fullName}</b>
              <p>
                {target.email} · {(target.roles || []).join(', ')}
              </p>
              <button
                className="btn btn-line btn-sm"
                disabled={target.id === user.id}
                onClick={() => edit(target)}
              >
                Đổi vai trò
              </button>
            </article>
          ))}
          <Pagination meta={data?.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}

/* ---------------- fees ---------------- */
function FeeForm({ fee, onSaved, close }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    kind: fee?.kind || 'PLATFORM_TXN',
    name: fee?.name || '',
    percent: fee?.percent ?? '',
    amount: fee?.amount ?? '',
    minAmount: fee?.minAmount ?? '',
    condition: fee?.condition || '',
    isActive: fee?.isActive ?? true,
  });
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const body = {
        kind: form.kind,
        name: form.name,
        percent: form.percent === '' ? null : Number(form.percent),
        amount: form.amount === '' ? null : Number(form.amount),
        minAmount: form.minAmount === '' ? null : Number(form.minAmount),
        condition: form.condition || null,
        isActive: Boolean(form.isActive),
      };
      if (fee) {
        await api(`/admin/finance/fees/${fee.id}`, { method: 'PATCH', body });
      } else {
        await api('/admin/finance/fees', { method: 'POST', body });
      }
      toast(fee ? 'Đã cập nhật phí' : 'Đã tạo phí', 'ok');
      close();
      onSaved();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>💰 {fee ? 'Sửa phí' : 'Tạo phí'}</h3>
      <div className="row2">
        <div className="form-row">
          <label className="lbl">Loại phí</label>
          <select className="input" value={form.kind} onChange={set('kind')}>
            {Object.keys(FEE_KIND_NAMES).map((kind) => (
              <option key={kind} value={kind}>{FEE_KIND_NAMES[kind]}</option>
            ))}
          </select>
        </div>
        <div className="form-row">
          <label className="lbl">Tên phí *</label>
          <input className="input" value={form.name} onChange={set('name')} required />
        </div>
      </div>
      <div className="row2">
        <div className="form-row">
          <label className="lbl">Phần trăm (%)</label>
          <input className="input" type="number" step="0.01" value={form.percent} onChange={set('percent')} />
        </div>
        <div className="form-row">
          <label className="lbl">Số tiền (đ)</label>
          <input className="input" type="number" value={form.amount} onChange={set('amount')} />
        </div>
      </div>
      <div className="form-row">
        <label className="lbl">Tối thiểu (đ)</label>
        <input className="input" type="number" value={form.minAmount} onChange={set('minAmount')} />
      </div>
      <div className="form-row">
        <label className="lbl">Mô tả / điều kiện</label>
        <input className="input" value={form.condition} onChange={set('condition')} />
      </div>
      <label className="role-option">
        <input
          type="checkbox"
          checked={Boolean(form.isActive)}
          onChange={(event) => setForm({ ...form, isActive: event.target.checked })}
        />{' '}
        Đang áp dụng
      </label>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {fee ? 'Lưu thay đổi' : 'Tạo phí'}
      </button>
    </form>
  );
}

function FeesView() {
  const toast = useToast();
  const { openModal, closeModal } = useModal();
  const [deleting, setDeleting] = useState(null);
  const { data, loading, error, reload } = useAsync(() => api('/admin/finance/fees'), []);
  const fees = Array.isArray(data) ? data : [];

  async function remove(fee) {
    if (!window.confirm('Xoá cấu hình phí?')) return;
    setDeleting(fee.id);
    try {
      await api(`/admin/finance/fees/${fee.id}`, { method: 'DELETE' });
      toast('Đã xoá cấu hình phí', 'ok');
      reload();
    } catch (caught) {
      toast(caught.message, 'err');
    } finally {
      setDeleting(null);
    }
  }

  function edit(fee) {
    openModal(<FeeForm fee={fee} close={closeModal} onSaved={reload} />);
  }

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
        }}
      >
        <h2>💰 Phí dịch vụ</h2>
        <button className="btn btn-green btn-sm" onClick={() => edit(null)}>+ Tạo phí</button>
      </div>
      {loading ? (
        <Loading />
      ) : error ? (
        <LoadError error={error} />
      ) : (
        <>
          <div className="tblwrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Tên phí</th>
                  <th>Giá trị</th>
                  <th>Mô tả</th>
                  <th>Trạng thái</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {fees.map((fee) => (
                  <tr key={fee.id}>
                    <td>
                      <b>{fee.name}</b>
                      <div className="muted" style={{ fontSize: 11 }}>
                        {FEE_KIND_NAMES[fee.kind] || fee.kind}
                      </div>
                    </td>
                    <td>
                      <b>{fee.percent != null ? fee.percent + '%' : fmtVND(fee.amount)}</b>
                      {fee.minAmount != null && (
                        <div className="muted" style={{ fontSize: 11 }}>
                          Tối thiểu {fmtVND(fee.minAmount)}
                        </div>
                      )}
                    </td>
                    <td className="muted">{fee.condition || ''}</td>
                    <td>
                      {fee.isActive ? (
                        <span className="pill p-ok">Đang áp dụng</span>
                      ) : (
                        <span className="pill p-mut">Tắt</span>
                      )}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn btn-line btn-sm" onClick={() => edit(fee)}>Sửa</button>{' '}
                      <button
                        className="btn btn-line btn-sm"
                        style={{ color: 'var(--red)' }}
                        disabled={deleting === fee.id}
                        onClick={() => remove(fee)}
                      >
                        Xoá
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!fees.length && <div className="empty">Chưa có cấu hình phí.</div>}
        </>
      )}
    </>
  );
}

/* ---------------- shell ---------------- */
function AdminArea() {
  const { tab } = useParams();
  const navigate = useNavigate();
  const { user, hasRole, clearSession } = useSession();
  const isFin = hasRole('ADMIN_FINANCE');
  const isCon = hasRole('ADMIN_CONTENT');
  const role = isCon && ADMIN_TABS.content.some(([key]) => key === tab)
    ? 'content'
    : isFin
      ? 'finance'
      : 'content';
  const tabs = ADMIN_TABS[role].filter(
    ([key]) => key !== 'permissions' || user?.canManageRoles,
  );
  const current = tabs.some(([key]) => key === tab) ? tab : tabs[0][0];
  const title = cleanLabel(tabs.find(([key]) => key === current)[1]);
  const roleName = role === 'finance' ? 'Tài chính' : 'Nội dung';

  useEffect(() => {
    document.title = `${title} — Quản trị Nola2Hand`;
  }, [title]);

  function logout() {
    clearSession();
    navigate('/');
  }

  function view() {
    const key = `${role}:${current}`;
    switch (key) {
      case 'content:dashboard':
        return <ContentOverview />;
      case 'content:pending':
        return <PendingView />;
      case 'content:reports':
        return <ReportsView />;
      case 'content:promos':
        return <PromosView />;
      case 'content:banners':
        return <BannersView />;
      case 'content:users':
        return <UsersView />;
      case 'content:reviews':
      case 'finance:reviews':
        return <ReviewsView />;
      case 'content:audit':
      case 'finance:audit':
        return <AuditView />;
      case 'finance:overview':
        return <FinanceOverview />;
      case 'finance:charts':
        return <ChartsView />;
      case 'finance:orders':
        return <OrdersView />;
      case 'finance:transactions':
        return <TransactionsView />;
      case 'finance:disputes':
        return <DisputesView />;
      case 'finance:fees':
        return <FeesView />;
      case 'finance:withdrawals':
        return <WithdrawalsView />;
      case 'finance:permissions':
        return <PermissionsView />;
      case 'finance:returns':
        return <ReturnsView />;
      default:
        return <ContentOverview />;
    }
  }

  return (
    <div className="alayout">
      <aside className="aside">
        <Link className="logo admin-logo" to="/admin">
          <span className="brand-mark"><Icon name="cycle" /></span>
          <span><span className="g">nola</span>2hand</span>
        </Link>
        <span className={`arole ${role}`}>
          {role === 'finance' ? 'Quản trị tài chính' : 'Quản trị nội dung'}
        </span>
        <div className="admin-nav-label">Không gian làm việc</div>
        <nav aria-label={`Quản trị ${roleName}`}>
          {tabs.map(([key, label]) => (
            <Link
              key={key}
              className={`anav ${current === key ? 'on' : ''}`}
              to={`/admin/${key}`}
              aria-current={current === key ? 'page' : undefined}
            >
              <Icon name={TAB_ICONS[key]} />
              <span>{cleanLabel(label)}</span>
            </Link>
          ))}
        </nav>
        <div className="admin-nav-label">Tài khoản</div>
        <Link className="anav" to="/profile"><Icon name="user" /> Hồ sơ của tôi</Link>
        <Link className="anav" to="/"><Icon name="home" /> Về trang mua sắm</Link>
        <div className="admin-usercard">
          <Avatar user={user} size={36} />
          <div>
            <b>{user?.fullName}</b>
            <span>Quản trị {roleName.toLocaleLowerCase('vi')}</span>
          </div>
          <button onClick={logout} aria-label="Đăng xuất" title="Đăng xuất">↪</button>
        </div>
      </aside>
      <div className="admin-main">
        <header className="admin-topbar">
          <div>
            <p>Không gian quản trị / {roleName}</p>
            <h1>{title}</h1>
          </div>
          <div className="admin-top-actions">
            {isFin && isCon && (
              <nav className="admin-role-switch" aria-label="Chọn vai trò quản trị">
                <Link className={role === 'finance' ? 'on' : ''} to="/admin/overview">
                  Tài chính
                </Link>
                <Link className={role === 'content' ? 'on' : ''} to="/admin/pending">
                  Nội dung
                </Link>
              </nav>
            )}
            <Link className="hact" to="/notifications" aria-label="Thông báo">
              <Icon name="bell" />
            </Link>
            <Link to="/profile" aria-label="Hồ sơ cá nhân">
              <Avatar user={user} size={36} />
            </Link>
          </div>
        </header>
        <div className="abody">{view()}</div>
      </div>
    </div>
  );
}

export default function Admin() {
  const { loggedIn, hasRole } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  if (!hasRole('ADMIN_FINANCE', 'ADMIN_CONTENT')) {
    return (
      <div className="wrap">
        <div className="empty">
          <div className="e">🔒</div>
          <p>Bạn không có quyền truy cập khu vực quản trị.</p>
          <br />
          <Link className="btn btn-green" to="/">Về trang mua sắm</Link>
        </div>
      </div>
    );
  }
  return <AdminArea />;
}
