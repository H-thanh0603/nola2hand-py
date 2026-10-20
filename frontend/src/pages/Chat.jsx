import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { useSession } from '../session';
import { Avatar, Loading, useAsync, useToast } from '../ui';
import { fmtDate } from '../utils';

export default function Chat() {
  const { loggedIn } = useSession();
  if (!loggedIn) return <Navigate to="/login" replace />;
  return <ChatView />;
}

function ChatView() {
  const { user: me } = useSession();
  const { userId } = useParams();
  const [params] = useSearchParams();
  const listingId = params.get('listingId');
  const navigate = useNavigate();
  const toast = useToast();
  const [refresh, setRefresh] = useState(0);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [blocking, setBlocking] = useState(false);
  const bodyRef = useRef(null);

  const conversations = useAsync(() => api('/chat/conversations'), [refresh]);
  const thread = useAsync(
    () =>
      userId
        ? api(
            '/chat/with/' +
              userId +
              (listingId ? '?listingId=' + encodeURIComponent(listingId) : ''),
          )
        : Promise.resolve(null),
    [userId, listingId, refresh],
  );
  const blocks = useAsync(() => api('/chat/blocks'), []);

  useEffect(() => {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }, [thread.data]);

  const other = conversations.data?.find(
    (conversation) =>
      String(conversation.user?.id) === String(userId) &&
      (!listingId || String(conversation.listingId || '') === String(listingId)),
  ) ||
    conversations.data?.find(
      (conversation) => String(conversation.user?.id) === String(userId),
    );
  const blocked = Boolean(
    blocks.data?.some((blockedUser) => String(blockedUser.id) === String(userId)),
  );

  async function send(event) {
    event?.preventDefault();
    const body = draft.trim();
    if (!body || !userId || sending) return;
    setSending(true);
    try {
      await api('/chat/messages', {
        method: 'POST',
        body: {
          receiverId: +userId,
          body,
          listingId: listingId ? +listingId : undefined,
        },
      });
      setDraft('');
      setRefresh((value) => value + 1);
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setSending(false);
    }
  }

  async function blockUser() {
    if (!window.confirm('Chặn gửi/nhận tin nhắn với tài khoản này?')) return;
    if (blocking) return;
    setBlocking(true);
    try {
      await api('/chat/blocks/' + userId, { method: 'POST' });
      toast('Đã chặn liên lạc', 'ok');
      blocks.reload();
      navigate('/chat');
    } catch (error) {
      toast(error.message, 'err');
    } finally {
      setBlocking(false);
    }
  }

  async function unblockUser(id) {
    try {
      await api('/chat/blocks/' + id, { method: 'DELETE' });
      toast('Đã bỏ chặn', 'ok');
      blocks.reload();
      setRefresh((value) => value + 1);
    } catch (error) {
      toast(error.message, 'err');
    }
  }

  return (
    <div className="wrap">
      <h1 style={{ fontSize: 23, marginBottom: 16 }}>💬 Tin nhắn</h1>
      <div
        className="row2"
        style={{ gridTemplateColumns: '320px 1fr', alignItems: 'start' }}
      >
        <div className="sect" style={{ padding: 12 }}>
          {conversations.loading && <Loading label="Đang tải hội thoại..." />}
          {conversations.error && (
            <p style={{ color: 'var(--red)' }}>{conversations.error.message}</p>
          )}
          {conversations.data?.map((conversation) => {
            if (!conversation.user) return null;
            const target =
              '/chat/' +
              conversation.user?.id +
              (conversation.listingId
                ? '?listingId=' + conversation.listingId
                : '');
            const active =
              String(conversation.user?.id) === String(userId) &&
              (!listingId ||
                String(conversation.listingId || '') === String(listingId));
            return (
              <Link
                className="card"
                key={
                  (conversation.user?.id || '?') +
                  ':' +
                  (conversation.listingId || 0)
                }
                to={target}
                style={{
                  padding: 12,
                  marginBottom: 8,
                  boxShadow: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  gap: 10,
                  alignItems: 'center',
                  borderColor: active ? 'var(--green)' : undefined,
                }}
              >
                <Avatar user={conversation.user} size={40} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b style={{ fontSize: 13 }}>
                    {conversation.user?.fullName || 'Người dùng'}
                  </b>
                  <div
                    className="muted"
                    style={{
                      fontSize: 12,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {conversation.lastMessage}
                  </div>
                </div>
                {conversation.unread > 0 && (
                  <span className="badge b-red">{conversation.unread}</span>
                )}
              </Link>
            );
          })}
          {conversations.data && !conversations.data.length && (
            <p className="muted" style={{ padding: 12 }}>
              Chưa có hội thoại.
            </p>
          )}
        </div>

        <div className="sect" id="thread">
          {!userId && <p className="muted">Chọn một hội thoại để xem.</p>}
          {userId && (
            <>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                <b>{other?.user?.fullName || 'Hội thoại'}</b>
                <button
                  className="btn btn-line btn-sm"
                  onClick={blockUser}
                  disabled={blocking || blocked}
                >
                  {blocked ? 'Đã chặn' : 'Chặn liên lạc'}
                </button>
              </div>
              {thread.loading && <Loading label="Đang tải tin nhắn..." />}
              {thread.error && (
                <p style={{ color: 'var(--red)' }}>{thread.error.message}</p>
              )}
              {!thread.loading && !thread.error && thread.data && (
                <>
                  <div
                    id="thread-body"
                    ref={bodyRef}
                    style={{
                      maxHeight: 380,
                      overflowY: 'auto',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                      marginBottom: 12,
                    }}
                  >
                    {thread.data.map((message) => {
                      const mine = message.senderId === me?.id;
                      return (
                        <div
                          key={message.id}
                          style={{
                            alignSelf: mine ? 'flex-end' : 'flex-start',
                            maxWidth: '75%',
                            background: mine ? 'var(--green)' : '#f1f3f1',
                            color: mine ? '#fff' : 'var(--ink)',
                            padding: '9px 14px',
                            borderRadius: 14,
                            fontSize: 13,
                          }}
                        >
                          {message.body}
                          <div style={{ fontSize: 10, opacity: 0.7, marginTop: 2 }}>
                            {fmtDate(message.createdAt)}
                          </div>
                        </div>
                      );
                    })}
                    {!thread.data.length && (
                      <p className="muted">Chưa có tin nhắn. Hãy chào nhau đi! 👋</p>
                    )}
                  </div>
                  <form onSubmit={send} style={{ display: 'flex', gap: 8 }}>
                    <input
                      className="input"
                      id="chat-in"
                      placeholder="Nhập tin nhắn..."
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          send();
                        }
                      }}
                    />
                    <button
                      className="btn btn-green"
                      disabled={sending || !draft.trim() || blocked}
                    >
                      {sending ? 'Đang gửi...' : 'Gửi'}
                    </button>
                  </form>
                </>
              )}
            </>
          )}
        </div>
      </div>

      <section className="sect">
        <h2>Đã chặn liên lạc</h2>
        {blocks.loading && <Loading label="Đang tải danh sách chặn..." />}
        {blocks.data?.map((blockedUser) => (
          <p key={blockedUser.id}>
            {blockedUser.fullName}{' '}
            <button
              className="btn btn-line btn-sm"
              onClick={() => unblockUser(blockedUser.id)}
            >
              Bỏ chặn
            </button>
          </p>
        ))}
        {blocks.data && !blocks.data.length && (
          <p className="muted">Chưa chặn tài khoản nào.</p>
        )}
      </section>
    </div>
  );
}
