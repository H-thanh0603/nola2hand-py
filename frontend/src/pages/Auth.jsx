import { useEffect, useRef, useState } from 'react';
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import { useToast } from '../ui';

const GOOGLE_CLIENT_ID_ENV = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function AuthCard({ children, maxWidth = 480 }) {
  return (
    <div className="auth-wrap">
      <div className="auth-form" style={{ gridColumn: '1/-1', maxWidth }}>
        {children}
      </div>
    </div>
  );
}

function PasswordInput({ id, label, value, onChange, autoComplete = 'new-password', hint }) {
  const [show, setShow] = useState(false);
  return (
    <div className="form-row">
      <label className="lbl" htmlFor={id}>
        {label}
      </label>
      <div className="pass-wrap">
        <input
          className="input"
          id={id}
          type={show ? 'text' : 'password'}
          required
          minLength={6}
          maxLength={72}
          autoComplete={autoComplete}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        <button
          type="button"
          className="pass-toggle"
          aria-label={show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
          onClick={() => setShow((current) => !current)}
        >
          {show ? '🙈' : '👁'}
        </button>
      </div>
      {hint && (
        <p className="muted" style={{ fontSize: 12 }}>
          {hint}
        </p>
      )}
    </div>
  );
}

function FieldError({ message }) {
  return (
    <p className="field-err" style={{ display: message ? 'block' : 'none' }}>
      {message}
    </p>
  );
}

/* ---------------- login ---------------- */
export function Login() {
  const { loggedIn, signIn } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('buyer@nola2hand.vn');
  const [password, setPassword] = useState('123456');
  const [busy, setBusy] = useState(false);
  const [googleClientId, setGoogleClientId] = useState(GOOGLE_CLIENT_ID_ENV);
  const googleBox = useRef(null);
  const googleStarted = useRef(false);
  const nextParam = params.get('next') || '/';
  const next = nextParam.startsWith('#') ? nextParam.slice(1) : nextParam;

  async function complete(result, message) {
    signIn(result.token, result.user);
    toast(message, 'ok');
    const admin = (result.user?.roles || []).some((role) =>
      ['ADMIN_FINANCE', 'ADMIN_CONTENT'].includes(role),
    );
    navigate(next !== '/' ? next : admin ? '/admin' : '/');
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const result = await api('/auth/login', {
        method: 'POST',
        auth: false,
        body: { email: email.trim(), password },
      });
      await complete(result, 'Đăng nhập thành công!');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (GOOGLE_CLIENT_ID_ENV) return undefined;
    let live = true;
    api('/auth/config', { auth: false })
      .then((result) => {
        if (live) setGoogleClientId(result.googleClientId || '');
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (!googleClientId || googleStarted.current) return undefined;
    let cancelled = false;
    let timer;
    const init = () => {
      if (cancelled) return;
      if (!window.google?.accounts?.id) {
        timer = setTimeout(init, 500);
        return;
      }
      googleStarted.current = true;
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async (response) => {
          try {
            const result = await api('/auth/google', {
              method: 'POST',
              auth: false,
              body: { idToken: response.credential },
            });
            await complete(result, 'Đăng nhập Google thành công! 👋');
          } catch (error) {
            toast(error.message, 'err');
          }
        },
      });
      if (googleBox.current) {
        window.google.accounts.id.renderButton(googleBox.current, {
          theme: 'outline',
          size: 'large',
          width: 300,
          text: 'signin_with',
        });
      }
    };
    init();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [googleClientId]);

  if (loggedIn) return <Navigate to="/" replace />;

  return (
    <div className="auth-wrap">
      <div className="auth-side">
        <div
          className="logo"
          style={{ color: '#fff', fontSize: 27, marginBottom: 24 }}
        >
          <span style={{ color: '#7ee787' }}>NOLA</span>2HAND
        </div>
        <h1 style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.2 }}>
          Chào mừng
          <br />
          trở lại 👋
        </h1>
        <p style={{ marginTop: 12, opacity: 0.88 }}>
          Đăng nhập để săn đồ cũ chất lượng, giá tốt.
        </p>
      </div>
      <div className="auth-form">
        <h2 style={{ fontSize: 26, fontWeight: 800, marginBottom: 20 }}>Đăng nhập</h2>
        <form onSubmit={submit}>
          <div className="form-row">
            <label className="lbl" htmlFor="li-email">
              Email
            </label>
            <input
              className="input"
              id="li-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="form-row">
            <label className="lbl" htmlFor="li-pass">
              Mật khẩu
            </label>
            <input
              className="input"
              id="li-pass"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
            {busy ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
        {googleClientId && (
          <div
            id="google-btn"
            ref={googleBox}
            style={{ marginTop: 14, display: 'flex', justifyContent: 'center' }}
          />
        )}
        <p style={{ textAlign: 'right', marginTop: 10 }}>
          <Link to="/forgot" style={{ color: 'var(--blue)', fontSize: 13 }}>
            Quên mật khẩu?
          </Link>
        </p>
        <p className="muted" style={{ textAlign: 'center', marginTop: 18, fontSize: 13.5 }}>
          Chưa có tài khoản?{' '}
          <Link to="/register" style={{ color: 'var(--blue)', fontWeight: 600 }}>
            Đăng ký
          </Link>
        </p>
        <p
          className="muted"
          style={{
            fontSize: 12,
            marginTop: 12,
            background: 'var(--green-softer)',
            padding: '10px 14px',
            borderRadius: 10,
          }}
        >
          Demo: buyer@nola2hand.vn · seller@nola2hand.vn · finance@nola2hand.vn ·
          content@nola2hand.vn
          <br />
          Mật khẩu: <b>123456</b>
        </p>
      </div>
    </div>
  );
}

/* ---------------- register ---------------- */
export function Register() {
  const { signIn } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const name = fullName.trim();
    const mail = email.trim();
    const nextErrors = {};
    if (name.length < 2) nextErrors.fullName = 'Họ tên tối thiểu 2 ký tự';
    else if (name.length > 100) nextErrors.fullName = 'Họ tên tối đa 100 ký tự';
    if (!EMAIL_RE.test(mail)) nextErrors.email = 'Email chưa đúng định dạng';
    if (password.length < 6) nextErrors.password = 'Mật khẩu tối thiểu 6 ký tự';
    else if (password.length > 72) nextErrors.password = 'Mật khẩu tối đa 72 ký tự';
    if (password !== password2) nextErrors.password2 = 'Mật khẩu nhập lại không khớp';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setBusy(true);
    try {
      const result = await api('/auth/register', {
        method: 'POST',
        auth: false,
        body: { fullName: name, email: mail, password },
      });
      signIn(result.token, { ...result.user, roles: ['BUYER'] });
      toast(result.message, 'ok');
      navigate('/verify-otp?email=' + encodeURIComponent(mail), {
        state: { email: mail },
      });
    } catch (error) {
      if (error.status === 409) setErrors({ email: error.message });
      else toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard>
      <h2 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }}>Tạo tài khoản</h2>
      <p className="muted" style={{ marginBottom: 20 }}>
        Khám phá đồ cũ chất lượng, giá tốt.
      </p>
      <form onSubmit={submit} noValidate>
        <div className="form-row">
          <label className="lbl" htmlFor="rg-name">
            Họ và tên
          </label>
          <input
            className="input"
            id="rg-name"
            required
            minLength={2}
            maxLength={100}
            autoComplete="name"
            placeholder="VD: Nguyễn Văn A"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
          <FieldError message={errors.fullName} />
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="rg-email">
            Email
          </label>
          <input
            className="input"
            id="rg-email"
            type="email"
            required
            autoComplete="email"
            placeholder="ban@email.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <FieldError message={errors.email} />
        </div>
        <PasswordInput
          id="rg-pass"
          label="Mật khẩu (≥6 ký tự)"
          value={password}
          onChange={setPassword}
          hint="Mật khẩu cần có cả chữ và số. Mật khẩu mạnh nên dài ≥8 ký tự, có chữ hoa hoặc ký tự đặc biệt."
        />
        <FieldError message={errors.password} />
        <PasswordInput
          id="rg-pass2"
          label="Nhập lại mật khẩu"
          value={password2}
          onChange={setPassword2}
        />
        <FieldError message={errors.password2} />
        <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Đang tạo tài khoản...' : 'Đăng ký'}
        </button>
      </form>
      <p className="muted" style={{ textAlign: 'center', marginTop: 18, fontSize: 13.5 }}>
        Đã có tài khoản?{' '}
        <Link to="/login" style={{ color: 'var(--blue)', fontWeight: 600 }}>
          Đăng nhập
        </Link>
      </p>
    </AuthCard>
  );
}

/* ---------------- OTP ---------------- */
export function VerifyOtp() {
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(
    params.get('email') || location.state?.email || '',
  );
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);
  const [resending, setResending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const result = await api('/auth/verify-otp', {
        method: 'POST',
        auth: false,
        body: { email: email.trim(), otp: otp.trim() },
      });
      toast(result.message + ' 🎉', 'ok');
      navigate('/');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    if (resending) return;
    setResending(true);
    try {
      const result = await api('/auth/resend-verification', {
        method: 'POST',
        auth: false,
        body: { email: email.trim() },
      });
      toast(result.message, 'ok');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setResending(false);
    }
  }

  return (
    <AuthCard maxWidth={440}>
      <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 6 }}>✉️ Nhập mã OTP</h2>
      <p className="muted" style={{ marginBottom: 20, fontSize: 13.5 }}>
        Mã 6 số đã gửi tới email (hiệu lực 10 phút). Chưa cấu hình mail thật thì mở
        file mới nhất trong <b>.local/mail/</b>.
      </p>
      <form onSubmit={submit}>
        <div className="form-row">
          <label className="lbl" htmlFor="vo-email">
            Email
          </label>
          <input
            className="input"
            id="vo-email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="form-row">
          <label className="lbl" htmlFor="vo-otp">
            Mã OTP 6 số
          </label>
          <input
            className="input"
            id="vo-otp"
            required
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            minLength={6}
            placeholder="••••••"
            style={{ fontSize: 22, letterSpacing: 8, textAlign: 'center' }}
            value={otp}
            onChange={(event) => setOtp(event.target.value.replace(/\D/g, ''))}
          />
        </div>
        <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Đang xác nhận...' : 'Xác nhận'}
        </button>
      </form>
      <p style={{ textAlign: 'center', marginTop: 14 }}>
        <button
          type="button"
          className="btn btn-line btn-sm"
          onClick={resend}
          disabled={resending || !email.trim()}
        >
          {resending ? 'Đang gửi...' : 'Gửi lại mã'}
        </button>
      </p>
    </AuthCard>
  );
}

/* ---------------- verify email link ---------------- */
export function VerifyEmail() {
  const { token } = useParams();
  const fired = useRef(null);
  const [state, setState] = useState({ loading: true, message: '', error: null });

  useEffect(() => {
    if (fired.current === token) return;
    fired.current = token;
    if (!token) {
      setState({ loading: false, message: '', error: new Error('Thiếu mã xác nhận') });
      return;
    }
    api('/auth/verify-email', { method: 'POST', auth: false, body: { token } })
      .then((result) => setState({ loading: false, message: result.message, error: null }))
      .catch((error) => setState({ loading: false, message: '', error }));
  }, [token]);

  if (state.loading) {
    return (
      <div className="empty">
        <div className="e">✉️</div>
        <p>Đang xác nhận email...</p>
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="empty">
        <div className="e">⚠️</div>
        <h1>{state.error.message}</h1>
        <Link className="btn btn-green" to="/profile">
          Về hồ sơ
        </Link>
      </div>
    );
  }
  return (
    <div className="empty">
      <div className="e">✅</div>
      <h1>{state.message}</h1>
      <Link className="btn btn-green" to="/profile">
        Về hồ sơ
      </Link>
    </div>
  );
}

/* ---------------- forgot ---------------- */
export function Forgot() {
  const toast = useToast();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [sent, setSent] = useState(false);
  const [otp, setOtp] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [busy, setBusy] = useState(false);

  async function send(event) {
    event?.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const result = await api('/auth/forgot-password', {
        method: 'POST',
        auth: false,
        body: { email: email.trim() },
      });
      setMessage(result.message);
      setSent(true);
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  async function resetOtp(event) {
    event.preventDefault();
    if (password !== password2) {
      toast('Mật khẩu nhập lại không khớp', 'err');
      return;
    }
    if (password.length < 6 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      toast('Mật khẩu tối thiểu 6 ký tự, có cả chữ và số', 'err');
      return;
    }
    setBusy(true);
    try {
      const result = await api('/auth/reset-password-otp', {
        method: 'POST',
        auth: false,
        body: { email: email.trim(), otp: otp.trim(), newPassword: password },
      });
      toast(result.message + ' — hãy đăng nhập lại', 'ok');
      navigate('/login');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard maxWidth={440}>
      <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 6 }}>🔑 Quên mật khẩu</h2>
      <p className="muted" style={{ marginBottom: 20, fontSize: 13.5 }}>
        Nhập email đăng ký, chúng tôi sẽ gửi mã OTP 6 số.
      </p>
      <form onSubmit={send}>
        <div className="form-row">
          <label className="lbl" htmlFor="fg-email">
            Email
          </label>
          <input
            className="input"
            id="fg-email"
            type="email"
            required
            placeholder="ban@email.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Đang gửi...' : 'Gửi mã OTP'}
        </button>
      </form>
      {sent && (
        <div
          className="card"
          style={{
            marginTop: 16,
            padding: 16,
            background: 'var(--amber-soft)',
            borderColor: '#f5d9a8',
            boxShadow: 'none',
          }}
        >
          <p className="muted" style={{ fontSize: 13 }}>
            {message}
          </p>
          <form onSubmit={resetOtp}>
            <div className="form-row">
              <label className="lbl" htmlFor="fg-otp">
                Mã OTP 6 số
              </label>
              <input
                className="input"
                id="fg-otp"
                required
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                minLength={6}
                placeholder="••••••"
                style={{ fontSize: 22, letterSpacing: 8, textAlign: 'center' }}
                value={otp}
                onChange={(event) => setOtp(event.target.value.replace(/\D/g, ''))}
              />
            </div>
            <PasswordInput
              id="fg-pass"
              label="Mật khẩu mới (≥6 ký tự, có cả chữ và số)"
              value={password}
              onChange={setPassword}
            />
            <PasswordInput
              id="fg-pass2"
              label="Nhập lại mật khẩu"
              value={password2}
              onChange={setPassword2}
            />
            <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
              {busy ? 'Đang đổi...' : 'Đổi mật khẩu'}
            </button>
          </form>
          <p style={{ textAlign: 'center', marginTop: 10 }}>
            <button
              type="button"
              className="btn btn-line btn-sm"
              onClick={send}
              disabled={busy}
            >
              Gửi lại mã
            </button>
          </p>
        </div>
      )}
      <p style={{ textAlign: 'center', marginTop: 16 }}>
        <Link to="/login" style={{ color: 'var(--blue)', fontSize: 13 }}>
          ← Quay lại đăng nhập
        </Link>
      </p>
    </AuthCard>
  );
}

/* ---------------- reset by link ---------------- */
export function Reset() {
  const { token } = useParams();
  const toast = useToast();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [busy, setBusy] = useState(false);

  if (!token) return <Navigate to="/forgot" replace />;

  async function submit(event) {
    event.preventDefault();
    if (password !== password2) {
      toast('Mật khẩu nhập lại không khớp', 'err');
      return;
    }
    if (password.length < 6 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
      toast('Mật khẩu tối thiểu 6 ký tự, có cả chữ và số', 'err');
      return;
    }
    setBusy(true);
    try {
      const result = await api('/auth/reset-password', {
        method: 'POST',
        auth: false,
        body: { resetToken: token, newPassword: password },
      });
      toast(result.message + ' — hãy đăng nhập lại', 'ok');
      navigate('/login');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard maxWidth={440}>
      <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 6 }}>
        🔑 Đặt lại mật khẩu
      </h2>
      <p className="muted" style={{ marginBottom: 20, fontSize: 13.5 }}>
        Nhập mật khẩu mới cho tài khoản của bạn.
      </p>
      <form onSubmit={submit}>
        <PasswordInput
          id="rs-pass"
          label="Mật khẩu mới (≥6 ký tự, có cả chữ và số)"
          value={password}
          onChange={setPassword}
        />
        <PasswordInput
          id="rs-pass2"
          label="Nhập lại mật khẩu"
          value={password2}
          onChange={setPassword2}
        />
        <button className="btn btn-green" style={{ width: '100%' }} disabled={busy}>
          {busy ? 'Đang đổi...' : 'Đổi mật khẩu'}
        </button>
      </form>
    </AuthCard>
  );
}
