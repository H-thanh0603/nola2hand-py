import { useState } from 'react';
import { api } from '../api';
import { ListingCard, useToast } from '../ui';

const SUGGESTIONS = [
  "Laptop dưới 5 triệu tại Hà Nội",
  "Tủ lạnh cũ giá rẻ",
  "Điện thoại iPhone 99%",
  "Bàn làm việc gỗ ở TP.HCM"
];

export default function Assistant() {
  const toast = useToast();
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(query) {
    const text = query || message;
    if (!text.trim()) return;
    
    setBusy(true);
    setError('');
    setResult(null);
    setMessage(text);

    try {
      const answer = await api('/assistant', {
        method: 'POST',
        auth: false,
        body: { message: text },
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
      <section className="sect" style={{ maxWidth: 900, margin: '40px auto', padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: '70vh', background: '#fff' }}>
        
        {/* Header */}
        <div style={{ padding: '24px 32px', borderBottom: '1px solid var(--line)', background: 'var(--green-soft)' }}>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 24, margin: 0 }}>
            <span style={{ fontSize: 32 }}>🤖</span> Trợ lý AI Nola2Hand
          </h1>
          <p style={{ color: 'var(--green-deep)', marginTop: 8, marginBottom: 0, fontSize: 14 }}>
            Chào bạn! Hãy nói cho mình biết bạn đang muốn tìm món đồ gì, ngân sách bao nhiêu, mình sẽ tìm giúp bạn nhé.
          </p>
        </div>

        {/* Chat Area */}
        <div style={{ flex: 1, padding: 32, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Default state: Suggestions */}
          {!result && !busy && !error && (
            <div style={{ margin: 'auto 0', textAlign: 'center' }}>
              <div style={{ fontSize: 40, marginBottom: 16 }}>✨</div>
              <h2 style={{ fontSize: 18, marginBottom: 20 }}>Bạn muốn tìm gì hôm nay?</h2>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                {SUGGESTIONS.map((s, i) => (
                  <button 
                    key={i} 
                    className="btn btn-line" 
                    style={{ borderRadius: 20, fontSize: 13 }}
                    onClick={() => submit(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Loading state */}
          {busy && (
            <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--green)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🤖</div>
              <div style={{ background: '#f4f7f5', padding: '14px 20px', borderRadius: '4px 16px 16px 16px', color: 'var(--mut)', fontSize: 14 }}>
                <span className="loading-spinner" style={{ width: 14, height: 14, display: 'inline-block', marginRight: 8, borderWidth: 2, verticalAlign: 'middle' }} />
                Đang phân tích câu nói của bạn...
              </div>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div style={{ padding: 16, background: '#fee2e2', color: '#b91c1c', borderRadius: 8, fontSize: 14 }}>
              ⚠️ {error}
            </div>
          )}

          {/* Result state */}
          {result && (
            <>
              {/* User bubble */}
              <div style={{ alignSelf: 'flex-end', background: 'var(--ink)', color: '#fff', padding: '12px 20px', borderRadius: '16px 16px 4px 16px', maxWidth: '80%', fontSize: 14 }}>
                {message}
              </div>

              {/* AI bubble */}
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--green)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>🤖</div>
                <div style={{ background: '#f4f7f5', padding: '16px 20px', borderRadius: '4px 16px 16px 16px', fontSize: 14.5, lineHeight: 1.6, maxWidth: '85%' }}>
                  {result.message.split('**').map((part, i) => 
                    i % 2 === 1 ? <b key={i} style={{ color: 'var(--green-dark)' }}>{part}</b> : <span key={i}>{part}</span>
                  )}
                </div>
              </div>

              {/* Product Results */}
              {result.items && result.items.length > 0 && (
                <div style={{ marginTop: 10, paddingLeft: 50 }}>
                  <div className="pgrid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
                    {result.items.map((listing) => (
                      <ListingCard key={listing.id} listing={listing} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Input Area */}
        <div style={{ padding: 24, borderTop: '1px solid var(--line)', background: '#fff' }}>
          <form onSubmit={(e) => { e.preventDefault(); submit(); }} style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <input
              className="input"
              placeholder="Nhập câu hỏi của bạn (VD: Tìm laptop dưới 5 triệu...)"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              style={{ flex: 1, minHeight: 52, borderRadius: 26, padding: '0 24px', background: '#f8faf9' }}
              disabled={busy}
            />
            <button 
              type="submit" 
              className="btn btn-green" 
              disabled={busy || !message.trim()}
              style={{ minHeight: 52, minWidth: 52, borderRadius: 26, padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </form>
          <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--mut)', marginTop: 12 }}>
            Trợ lý AI có thể mắc lỗi. Vui lòng kiểm tra lại thông tin sản phẩm.
          </div>
        </div>

      </section>
    </div>
  );
}