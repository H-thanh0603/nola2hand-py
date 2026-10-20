import { useState } from 'react';
import { api } from '../api';
import { ErrorState, ListingCard, useToast } from '../ui';

export default function Assistant() {
  const toast = useToast();
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const answer = await api('/assistant', {
        method: 'POST',
        auth: false,
        body: { message },
      });
      setResult(answer);
    } catch (requestError) {
      setError(requestError.message);
      toast(requestError.message, 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap">
      <section className="sect assistant-panel">
        <span className="eyebrow">TÌM MÓN ĐỒ PHÙ HỢP</span>
        <h1>✨ Trợ lý tìm đồ</h1>
        <p className="muted">
          Mô tả món đồ và ngân sách. Kết quả luôn lấy từ tin đang bán.
        </p>
        <form onSubmit={submit}>
          <label className="lbl" htmlFor="assistant-question">
            Bạn đang cần gì?
          </label>
          <textarea
            className="input"
            id="assistant-question"
            maxLength="500"
            required
            minLength="2"
            placeholder="Ví dụ: laptop dưới 6 triệu tại TP. Hồ Chí Minh"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
          <button className="btn btn-green" id="assistant-submit" disabled={busy}>
            {busy ? 'Đang tìm...' : 'Tìm sản phẩm'}
          </button>
        </form>

        <div id="assistant-answer" aria-live="polite">
          {error && (
            <p className="filter-error" role="alert">
              {error}
            </p>
          )}
          {result && (
            <>
              <span
                className={
                  'badge ' + (result.mode === 'AI' ? 'b-green' : 'b-amber')
                }
              >
                {result.mode === 'AI'
                  ? 'AI hỗ trợ bộ lọc'
                  : 'Tìm kiếm từ khóa'}
              </span>
              <p>{result.message}</p>
              <p className="muted">{result.note}</p>
              <div className="pgrid">
                {result.items?.map((listing) => (
                  <ListingCard key={listing.id} listing={listing} />
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
