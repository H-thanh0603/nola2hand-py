import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import {
  Avatar,
  ErrorState,
  Loading,
  useAsync,
  useModal,
  useToast,
} from '../ui';

export default function Profile() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <ProfileView />;
}

function ProfileView() {
  const { clearSession } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const { openModal } = useModal();
  const state = useAsync(() => api('/users/me/profile'), []);
  const [resending, setResending] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  if (state.loading) {
    return (
      <div className="wrap">
        <Loading label="Đang tải hồ sơ..." />
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

  const me = state.data;
  const addresses = me.addresses || [];

  async function resendVerification() {
    if (resending) return;
    setResending(true);
    try {
      const result = await api('/auth/resend-verification', {
        method: 'POST',
        auth: false,
        body: { email: me.email },
      });
      toast(result.message, 'ok');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setResending(false);
    }
  }

  async function deleteAddress(id) {
    if (!window.confirm('Xoá địa chỉ này?')) return;
    try {
      await api('/users/me/addresses/' + id, { method: 'DELETE' });
      toast('Đã xoá địa chỉ', 'ok');
      state.reload();
    } catch (error) {
      toast(error.message, 'err');
    }
  }

  async function logoutAll() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await api('/auth/logout', { method: 'POST' });
    } catch (error) {
      if (error.status !== 401) {
        toast(error.message, 'err');
        setLoggingOut(false);
        return;
      }
    }
    clearSession();
    toast('Đã đăng xuất và thu hồi các phiên đăng nhập.', 'ok');
    navigate('/login');
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 16 }}>👤 Hồ sơ cá nhân</h1>
      <div className="row2" style={{ alignItems: 'start' }}>
        <div className="sect">
          <h2>Thông tin cá nhân</h2>
          <div
            style={{
              display: 'flex',
              gap: 14,
              alignItems: 'center',
              marginBottom: 16,
            }}
          >
            <Avatar user={me} size={64} />
            <div>
              <b style={{ fontSize: 17 }}>{me.fullName}</b>
              <div className="muted" style={{ fontSize: 12 }}>
                {me.email}
              </div>
              {!me.emailVerifiedAt && (
                <button
                  className="btn btn-line btn-sm"
                  onClick={resendVerification}
                  disabled={resending}
                >
                  {resending ? 'Đang gửi...' : 'Gửi lại xác nhận email'}
                </button>
              )}
              {me.emailVerifiedAt && <span className="badge b-blue">✓ Email đã xác nhận</span>}{' '}
              {me.idVerified && (
                <span className="badge b-green">✓ Danh tính đã duyệt</span>
              )}
            </div>
          </div>
          <ProfileForm me={me} onSaved={state.reload} />
          {!me.roles?.includes('SELLER') && (
            <div
              style={{
                marginTop: 18,
                paddingTop: 16,
                borderTop: '1px solid var(--line)',
              }}
            >
              <button
                className="btn btn-line"
                onClick={() =>
                  openModal(
                    <BecomeSellerModal me={me} onDone={state.reload} />,
                  )
                }
              >
                🏪 Mở kênh người bán
              </button>
            </div>
          )}
        </div>

        <div className="sect">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 12,
            }}
          >
            <h2>📍 Sổ địa chỉ</h2>
            <button
              className="btn btn-line btn-sm"
              onClick={() =>
                openModal(<AddressModal me={me} onDone={state.reload} />)
              }
            >
              + Thêm
            </button>
          </div>
          {addresses.length ? (
            addresses.map((address) => (
              <div
                className="card"
                key={address.id}
                style={{ padding: '12px 14px', marginBottom: 8, boxShadow: 'none' }}
              >
                <b style={{ fontSize: 13 }}>{address.receiver}</b> · {address.phone}{' '}
                {address.isDefault && <span className="badge b-blue">Mặc định</span>}
                <div className="muted" style={{ fontSize: 12 }}>
                  {[address.street, address.ward, address.district, address.city]
                    .filter(Boolean)
                    .join(', ')}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <span className="badge b-gray">{address.label}</span>
                  <button
                    className="btn btn-line btn-sm"
                    onClick={() => deleteAddress(address.id)}
                  >
                    Xoá
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="muted">Chưa có địa chỉ.</p>
          )}
        </div>
      </div>

      <section className="sect">
        <h2>Bảo mật tài khoản</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <button
            className="btn btn-line"
            onClick={() => openModal(<PasswordModal />)}
          >
            Đổi mật khẩu và đăng xuất mọi thiết bị
          </button>
          <button className="btn btn-line" onClick={logoutAll} disabled={loggingOut}>
            {loggingOut ? 'Đang đăng xuất...' : 'Đăng xuất mọi thiết bị'}
          </button>
        </div>
      </section>
    </div>
  );
}

function ProfileForm({ me, onSaved }) {
  const toast = useToast();
  const [fullName, setFullName] = useState(me.fullName || '');
  const [phone, setPhone] = useState(me.phone || '');
  const [bio, setBio] = useState(me.bio || '');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await api('/users/me', {
        method: 'PATCH',
        body: {
          fullName: fullName.trim(),
          phone: phone.trim() || null,
          bio: bio.trim(),
        },
      });
      toast('Đã lưu!', 'ok');
      onSaved();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="form-row">
        <label className="lbl" htmlFor="pf-name">
          Họ và tên
        </label>
        <input
          className="input"
          id="pf-name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="pf-phone">
          Số điện thoại
        </label>
        <input
          className="input"
          id="pf-phone"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="pf-bio">
          Giới thiệu
        </label>
        <textarea
          className="input"
          id="pf-bio"
          rows={2}
          value={bio}
          onChange={(event) => setBio(event.target.value)}
        />
      </div>
      <button className="btn btn-green" disabled={busy}>
        {busy ? 'Đang lưu...' : 'Lưu thay đổi'}
      </button>
    </form>
  );
}

function AddressModal({ me, onDone }) {
  const { closeModal } = useModal();
  const toast = useToast();
  const [label, setLabel] = useState('Nhà');
  const [receiver, setReceiver] = useState(me.fullName || '');
  const [phone, setPhone] = useState(me.phone || '');
  const [street, setStreet] = useState('');
  const [city, setCity] = useState('Bình Dương');
  const [isDefault, setIsDefault] = useState(true);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await api('/users/me/addresses', {
        method: 'POST',
        body: { label, receiver, phone, street, city, isDefault },
      });
      closeModal();
      toast('Đã thêm địa chỉ', 'ok');
      onDone();
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 14 }}>📍 Thêm địa chỉ</h3>
      <div className="form-row">
        <label className="lbl" htmlFor="ad-label">
          Nhãn
        </label>
        <input
          className="input"
          id="ad-label"
          required
          value={label}
          onChange={(event) => setLabel(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="ad-name">
          Người nhận *
        </label>
        <input
          className="input"
          id="ad-name"
          required
          value={receiver}
          onChange={(event) => setReceiver(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="ad-phone">
          SĐT *
        </label>
        <input
          className="input"
          id="ad-phone"
          required
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="ad-street">
          Địa chỉ *
        </label>
        <input
          className="input"
          id="ad-street"
          required
          placeholder="Số nhà, đường"
          value={street}
          onChange={(event) => setStreet(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="ad-city">
          Tỉnh/Thành *
        </label>
        <input
          className="input"
          id="ad-city"
          required
          value={city}
          onChange={(event) => setCity(event.target.value)}
        />
      </div>
      <label className="free-filter">
        <input
          type="checkbox"
          checked={isDefault}
          onChange={(event) => setIsDefault(event.target.checked)}
        />{' '}
        Đặt làm địa chỉ mặc định
      </label>
      <button
        className="btn btn-green"
        style={{ width: '100%', marginTop: 12 }}
        disabled={busy}
      >
        {busy ? 'Đang thêm...' : 'Thêm'}
      </button>
    </form>
  );
}

function BecomeSellerModal({ me, onDone }) {
  const { closeModal } = useModal();
  const { user, setUser } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [agree, setAgree] = useState(false);
  const [done, setDone] = useState(false);
  const [shopName, setShopName] = useState('Shop ' + (me.fullName || ''));
  const [phone, setPhone] = useState(me.phone || '');
  const [city, setCity] = useState('');
  const [street, setStreet] = useState('');
  const [busy, setBusy] = useState(false);

  if (done) {
    return (
      <>
        <h2>🎉 Gian hàng đã mở!</h2>
        <p className="muted">
          {shopName} sẵn sàng đón khách. Vào Hồ sơ để xác minh email/danh tính lấy
          huy hiệu ✓, buyer sẽ tin shop hơn.
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
      </>
    );
  }

  if (step === 1) {
    return (
      <>
        <h2>🏪 Mở gian hàng</h2>
        <p className="muted">Bước 1/2 — Biết trước khi bán</p>
        <div className="stat-grid">
          <div className="stat">
            <div className="t">Đăng tin</div>
            <div className="v">Miễn phí</div>
          </div>
          <div className="stat">
            <div className="t">Phí sàn</div>
            <div className="v">Khi bán được</div>
          </div>
          <div className="stat">
            <div className="t">Tiền về</div>
            <div className="v">Ví SafePay</div>
          </div>
        </div>
        <div className="sect" style={{ margin: '12px 0' }}>
          <p>💰 Phí sàn chỉ thu khi bán được hàng, theo từng danh mục.</p>
          <p>🔒 Tiền cọc được giữ hộ tới khi người mua xác nhận nhận hàng.</p>
          <p>⚠️ Tin vi phạm bị ẩn, tái phạm bị khóa shop.</p>
        </div>
        <label className="free-filter">
          <input
            type="checkbox"
            checked={agree}
            onChange={(event) => setAgree(event.target.checked)}
          />{' '}
          Tôi đã đọc và đồng ý quy định bán hàng
        </label>
        <button
          className="btn btn-green"
          style={{ width: '100%', marginTop: 12 }}
          onClick={() => {
            if (!agree) {
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

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (shopName.trim().length < 2) {
      toast('Tên shop tối thiểu 2 ký tự', 'err');
      return;
    }
    if ((city.trim() && !street.trim()) || (!city.trim() && street.trim())) {
      toast('Nhập đủ tỉnh/thành và địa chỉ, hoặc bỏ trống cả hai', 'err');
      return;
    }
    setBusy(true);
    try {
      await api('/users/me/become-seller', {
        method: 'POST',
        body: {
          shopName: shopName.trim(),
          phone: phone.trim() || undefined,
          city: city.trim() || undefined,
          street: street.trim() || undefined,
        },
      });
      const fresh = await api('/auth/me');
      setUser({ ...user, roles: fresh.roles, phone: fresh.phone });
      toast('Mở kênh người bán thành công!', 'ok');
      onDone();
      setDone(true);
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h2>🏪 Thông tin shop</h2>
      <p className="muted">
        Bước 2/2 — Buyer tin shop có tên rõ ràng, SĐT và địa chỉ lấy hàng.
      </p>
      <div className="form-row">
        <label className="lbl" htmlFor="seller-shop">
          Tên shop *
        </label>
        <input
          className="input"
          id="seller-shop"
          required
          minLength={2}
          maxLength={100}
          value={shopName}
          onChange={(event) => setShopName(event.target.value)}
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
          maxLength={20}
          pattern="([+]84|0)(3|5|7|8|9)[0-9]{8}"
          placeholder="Để buyer và shipper liên lạc"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="seller-city">
          Tỉnh / thành phố
        </label>
        <input
          className="input"
          id="seller-city"
          maxLength={100}
          placeholder="VD: TP. Hồ Chí Minh"
          value={city}
          onChange={(event) => setCity(event.target.value)}
        />
      </div>
      <div className="form-row">
        <label className="lbl" htmlFor="seller-street">
          Địa chỉ lấy hàng
        </label>
        <input
          className="input"
          id="seller-street"
          maxLength={255}
          placeholder="Số nhà, đường..."
          value={street}
          onChange={(event) => setStreet(event.target.value)}
        />
      </div>
      <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Đang mở...' : 'Mở gian hàng'}
      </button>
    </form>
  );
}

function PasswordModal() {
  const { closeModal } = useModal();
  const { clearSession } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const result = await api('/auth/change-password', {
        method: 'POST',
        body: { currentPassword: current, newPassword: next },
      });
      closeModal();
      clearSession();
      toast(result.message, 'ok');
      navigate('/login');
    } catch (error) {
      toast(error.message, 'err');
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h2>Đổi mật khẩu</h2>
      <label className="lbl" htmlFor="current-password">
        Mật khẩu hiện tại
      </label>
      <input
        className="input"
        id="current-password"
        type="password"
        required
        autoComplete="current-password"
        value={current}
        onChange={(event) => setCurrent(event.target.value)}
      />
      <label className="lbl" htmlFor="new-password">
        Mật khẩu mới (8–72 ký tự, có cả chữ và số)
      </label>
      <input
        className="input"
        id="new-password"
        type="password"
        required
        minLength={8}
        maxLength={72}
        autoComplete="new-password"
        value={next}
        onChange={(event) => setNext(event.target.value)}
      />
      <button className="btn btn-green" disabled={busy}>
        {busy ? 'Đang lưu...' : 'Lưu và thu hồi phiên cũ'}
      </button>
    </form>
  );
}
