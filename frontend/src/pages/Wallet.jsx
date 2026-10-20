import { useRef, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import {
  ErrorState,
  Loading,
  Pagination,
  WorkflowBadge,
  useAsync,
  useModal,
  useToast,
} from '../ui';
import { fmtDate, fmtVND } from '../utils';
import { TXN_TYPE_NAMES } from '../constants';

export default function Wallet() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <WalletView />;
}

function WalletView() {
  const toast = useToast();
  const { openModal } = useModal();
  const [page, setPage] = useState(1);
  const [withdrawPage, setWithdrawPage] = useState(1);
  const [cancelling, setCancelling] = useState(null);

  const state = useAsync(
    async () => {
      const [wallet, transactions, banks] = await Promise.all([
        api('/wallet'),
        api('/wallet/transactions?limit=10&page=' + page),
        api('/wallet/banks'),
      ]);
      return { wallet, transactions, banks };
    },
    [page],
  );

  const withdrawals = useAsync(
    () => api('/wallet/withdrawals?page=' + withdrawPage + '&limit=10'),
    [withdrawPage],
  );

  if (state.loading) {
    return (
      <div className="wrap">
        <Loading label="Đang tải ví..." />
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="wrap">
        <ErrorState error={state.error} />
      </div>
    );
  }

  const { wallet, transactions, banks } = state.data;

  function openTopup() {
    openModal(<TopupModal onDone={state.reload} />);
  }

  function openWithdraw() {
    if (!banks.length) {
      toast('Hãy thêm tài khoản ngân hàng trước', 'err');
      return;
    }
    openModal(
      <WithdrawModal
        banks={banks}
        onDone={() => {
          state.reload();
          withdrawals.reload();
        }}
      />,
    );
  }

  function openBank() {
    openModal(<BankModal onDone={state.reload} />);
  }

  async function deleteBank(id) {
    if (!window.confirm('Xoá tài khoản ngân hàng này?')) return;
    try {
      await api('/wallet/banks/' + id, { method: 'DELETE' });
      toast('Đã xoá tài khoản ngân hàng', 'ok');
      state.reload();
    } catch (error) {
      toast(error.message, 'err');
    }
  }

  async function cancelWithdrawal(id) {
    if (!window.confirm('Hủy yêu cầu và trả tiền đang giữ về số dư khả dụng?')) return;
    if (cancelling) return;
    setCancelling(id);
    try {
      await api('/wallet/withdrawals/' + id + '/cancel', { method: 'PATCH' });
      toast('Đã hủy và hoàn tiền giữ', 'ok');
      state.reload();
      withdrawals.reload();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setCancelling(null);
    }
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 16 }}>👛 Ví SafePay</h1>

      <div
        className="card"
        style={{
          padding: 26,
          background: 'linear-gradient(120deg,#0c2413,#1c6b2c)',
          color: '#fff',
          border: 0,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 14,
          }}
        >
          <div>
            <div style={{ opacity: 0.8, fontSize: 12.5 }}>Số dư khả dụng</div>
            <div style={{ fontSize: 38, fontWeight: 800 }}>
              {fmtVND(wallet.balance)}
            </div>
            <p>Đang giữ cho rút tiền / trả hàng: {fmtVND(wallet.pendingBalance)}</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn"
              style={{ background: '#fff', color: 'var(--green-dark)' }}
              onClick={openTopup}
            >
              ＋ Nạp tiền
            </button>
            <button className="btn btn-line" onClick={openWithdraw}>
              💸 Rút tiền
            </button>
          </div>
        </div>
      </div>

      <div
        className="row2"
        style={{ gridTemplateColumns: '1.6fr 1fr', alignItems: 'start' }}
      >
        <div className="sect" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '18px 20px 0' }}>
            <h2>Lịch sử giao dịch</h2>
          </div>
          <table className="tbl" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Giao dịch</th>
                <th>Số tiền</th>
                <th>Ngày</th>
              </tr>
            </thead>
            <tbody>
              {transactions.data.map((transaction) => (
                <tr key={transaction.id}>
                  <td>
                    <b>{TXN_TYPE_NAMES[transaction.type] || transaction.type}</b>
                    <div className="muted" style={{ fontSize: 11.5 }}>
                      {transaction.note || transaction.reference || ''}
                    </div>
                  </td>
                  <td
                    style={{
                      fontWeight: 700,
                      color:
                        transaction.amount >= 0 ? 'var(--green-dark)' : 'var(--red)',
                    }}
                  >
                    {transaction.amount >= 0 ? '+' : ''}
                    {fmtVND(transaction.amount)}
                  </td>
                  <td className="muted">{fmtDate(transaction.createdAt)}</td>
                </tr>
              ))}
              {!transactions.data.length && (
                <tr>
                  <td colSpan={3} className="muted">
                    Chưa có giao dịch.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <Pagination meta={transactions.meta} onPage={setPage} />
        </div>

        <div>
          <div className="sect">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
              }}
            >
              <h2>🏦 Tài khoản ngân hàng</h2>
              <button className="btn btn-line btn-sm" onClick={openBank}>
                + Thêm
              </button>
            </div>
            {banks.length ? (
              banks.map((bank) => (
                <div
                  className="card"
                  key={bank.id}
                  style={{
                    padding: '12px 14px',
                    marginBottom: 8,
                    boxShadow: 'none',
                    display: 'flex',
                    gap: 10,
                    alignItems: 'center',
                  }}
                >
                  <span className="badge b-green">
                    {bank.bankName.slice(0, 3).toUpperCase()}
                  </span>
                  <div style={{ flex: 1 }}>
                    <b style={{ fontSize: 13 }}>{bank.bankName}</b>
                    <div className="muted" style={{ fontSize: 11 }}>
                      **** {bank.accountNumber.slice(-4)}
                    </div>
                  </div>
                  {bank.isDefault && <span className="badge b-blue">Mặc định</span>}
                  <button
                    className="btn btn-line btn-sm"
                    onClick={() => deleteBank(bank.id)}
                  >
                    Xoá
                  </button>
                </div>
              ))
            ) : (
              <p className="muted" style={{ fontSize: 13 }}>
                Chưa liên kết.
              </p>
            )}
          </div>
        </div>
      </div>

      <section className="sect">
        <h2>Yêu cầu rút tiền</h2>
        <p className="muted">
          Tiền được giữ tới khi admin chuyển khoản hoặc từ chối. Chưa chuyển tiền sẽ
          chưa ghi giao dịch thành công.
        </p>
        {withdrawals.loading && <Loading label="Đang tải yêu cầu rút..." />}
        {withdrawals.error && (
          <p style={{ color: 'var(--red)' }}>{withdrawals.error.message}</p>
        )}
        {withdrawals.data?.data.map((request) => (
          <WithdrawalCard
            key={request.id}
            request={request}
            busy={cancelling === request.id}
            onCancel={cancelWithdrawal}
          />
        ))}
        {withdrawals.data && !withdrawals.data.data.length && (
          <p className="muted">Chưa có yêu cầu.</p>
        )}
        {withdrawals.data && (
          <Pagination meta={withdrawals.data.meta} onPage={setWithdrawPage} />
        )}
      </section>
    </div>
  );
}

function WithdrawalCard({ request, busy, onCancel }) {
  return (
    <article className="workflow-card">
      <h3>{request.user?.fullName || request.reference}</h3>
      <WorkflowBadge status={request.status} />
      <p>
        Rút {fmtVND(request.amount)} · phí {fmtVND(request.fee)}
      </p>
      <p>
        {request.bankName} · ****{String(request.accountNumber || '').slice(-4)} ·{' '}
        {request.accountName}
      </p>
      <p className="muted">
        {fmtDate(request.createdAt)}
        {request.paidAt ? ' · chuyển ' + fmtDate(request.paidAt) : ''}
      </p>
      {request.resolution && <p>{request.resolution}</p>}
      {request.transferReference && <p>Chứng từ: {request.transferReference}</p>}
      <div className="workflow-actions">
        {request.status === 'PENDING' && (
          <button
            className="btn btn-line btn-sm"
            onClick={() => onCancel(request.id)}
            disabled={busy}
          >
            {busy ? 'Đang hủy...' : 'Hủy yêu cầu'}
          </button>
        )}
      </div>
    </article>
  );
}

function TopupModal({ onDone }) {
  const { closeModal } = useModal();
  const toast = useToast();
  const [amount, setAmount] = useState(100000);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const result = await api('/wallet/topup', {
        method: 'POST',
        body: { amount: +amount, method: 'MOMO_QR' },
      });
      closeModal();
      toast(result.message, 'ok');
      onDone();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>＋ Nạp tiền vào ví</h3>
      <div className="form-row">
        <label className="lbl" htmlFor="tp-amt">
          Số tiền (đ, tối thiểu 10.000)
        </label>
        <input
          className="input"
          id="tp-amt"
          type="number"
          min={10000}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang nạp...' : 'Nạp tiền'}
      </button>
      <p className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
        Demo: tiền được cộng ngay. Thực tế sẽ qua cổng thanh toán.
      </p>
    </form>
  );
}

function WithdrawModal({ banks, onDone }) {
  const { closeModal } = useModal();
  const toast = useToast();
  const [amount, setAmount] = useState(100000);
  const [bankId, setBankId] = useState(String(banks[0]?.id || ''));
  const [requestKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);

  async function submit(event) {
    event.preventDefault();
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const result = await api('/wallet/withdraw', {
        method: 'POST',
        body: {
          amount: +amount,
          bankAccountId: +bankId,
          requestKey,
        },
      });
      closeModal();
      toast(result.message, 'ok');
      onDone();
    } catch (error) {
      toast(error.message, 'err');
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>💸 Rút tiền</h3>
      <div className="form-row">
        <label className="lbl" htmlFor="wd-amt">
          Số tiền (đ, tối thiểu 50.000)
        </label>
        <input
          className="input"
          id="wd-amt"
          type="number"
          min={50000}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="wd-bank">
          Về tài khoản
        </label>
        <select
          className="input"
          id="wd-bank"
          value={bankId}
          onChange={(event) => setBankId(event.target.value)}
        >
          {banks.map((bank) => (
            <option key={bank.id} value={bank.id}>
              {bank.bankName} ****{bank.accountNumber.slice(-4)}
            </option>
          ))}
        </select>
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang gửi...' : 'Gửi yêu cầu rút'}
      </button>
    </form>
  );
}

function BankModal({ onDone }) {
  const { closeModal } = useModal();
  const toast = useToast();
  const [bankName, setBankName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [accountName, setAccountName] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await api('/wallet/banks', {
        method: 'POST',
        body: { bankName, accountNumber, accountName, isDefault: true },
      });
      closeModal();
      toast('Đã thêm tài khoản', 'ok');
      onDone();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>🏦 Thêm tài khoản ngân hàng</h3>
      <div className="form-row">
        <label className="lbl" htmlFor="bk-name">
          Ngân hàng *
        </label>
        <input
          className="input"
          id="bk-name"
          required
          placeholder="VD: Techcombank"
          value={bankName}
          onChange={(event) => setBankName(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="bk-num">
          Số tài khoản *
        </label>
        <input
          className="input"
          id="bk-num"
          required
          minLength={6}
          maxLength={30}
          value={accountNumber}
          onChange={(event) => setAccountNumber(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="bk-holder">
          Tên chủ tài khoản *
        </label>
        <input
          className="input"
          id="bk-holder"
          required
          value={accountName}
          onChange={(event) => setAccountName(event.target.value)}
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang thêm...' : 'Thêm'}
      </button>
    </form>
  );
}
