/**
 * MUSE PAGE — script nạp vào trang muse.ai (window.__mss) + lớp Node gọi nó qua Chrome.
 * Gửi lệnh bằng chính client React của Muse (sendMessage, mỗi lệnh 1 chat phụ mới), đọc phiên qua RPC
 * của Muse (sessions.list / chat.history / chat.cancel), tải file qua fs.raw từng đoạn base64.
 */

const CHUNK = 2097152; // 2MB mỗi đoạn tải file

// Chạy TRONG trang Muse (không chạy trong Node) — chuyển thành chuỗi qua toString().
function pageMain(CHUNK) {
  const rt = () => window.__hatchEarlyGatewayRuntimeState.activeRuntime.getSnapshot();
  // Object chat của Muse: tìm trong cây React (memoizedProps.value có sendMessage + ensureActiveChatSendReady)
  const chat = () => {
    if (!document.body) return null; // vừa chuyển trang, trang mới chưa dựng xong
    let root;
    for (const el of [document.body, ...document.querySelectorAll('body *')].slice(0, 80)) {
      const k = Object.keys(el).find(k => k.startsWith('__reactContainer') || k.startsWith('__reactFiber'));
      if (k) { root = el[k]; break; }
    }
    if (!root) return null;
    if (root.stateNode?.current) root = root.stateNode.current;
    const stack = [root];
    for (let n = 0; stack.length && n < 300000; n++) {
      const f = stack.pop();
      const v = f.memoizedProps?.value;
      if (v && typeof v.sendMessage === 'function' && typeof v.ensureActiveChatSendReady === 'function') return v;
      if (f.child) stack.push(f.child);
      if (f.sibling) stack.push(f.sibling);
    }
    return null;
  };
  const files = new Map();
  let fileSeq = 0;
  const b64 = u8 => {
    let s = '';
    for (let i = 0; i < u8.length; i += 32768) s += String.fromCharCode.apply(null, u8.subarray(i, i + 32768));
    return btoa(s);
  };
  return (window.__mss = {
    async login() {
      try {
        const r = await fetch('/api/session', { credentials: 'include' });
        const j = await r.json().catch(() => ({}));
        return { loggedIn: r.status === 200 && Boolean(chat()), http: r.status, status: j.status || null, vm: j.vm_state || null };
      } catch (e) {
        return { loggedIn: false, http: 0, status: null, vm: null };
      }
    },
    // thread = sessionId chat có sẵn: gửi thẳng vào chat đó (targetRoute của Muse), không chuyển trang; không có → chat phụ mới
    async send(text, atts, thread = '') {
      // Trang đang chuyển/đang dựng lại (vd. người dùng bấm mở 1 đoạn chat) → chờ tối đa 20s cho client chat hiện lại
      let c = chat();
      for (let k = 0; !c && k < 20; k++) { await new Promise(r => setTimeout(r, 1000)); c = chat(); }
      if (!c) return { ok: false, reason: `not_ready (${location.pathname})` };
      const r = await c.sendMessage(text, atts, thread
        ? { targetRoute: { kind: 'thread', sessionId: thread }, waitForReadiness: true }
        : { createNewThread: true, waitForReadiness: true });
      return { ok: Boolean(r?.ok), sessionId: r?.sessionId || (r?.ok ? thread : ''), reason: r?.reason || r?.error || '' };
    },
    async status(sid) {
      const { sessions = [] } = await rt().sendRequest('sessions.list', {});
      return sessions.find(s => s.session_id === sid)?.status || null;
    },
    async result(sid) {
      const h = await rt().sendRequest('chat.history', { session_id: sid, limit: 50 });
      return (h.chat_events || []).filter(e => e.role === 'assistant').map(e => ({
        text: e.display_text || '', images: e.payload?.data?.images || [], videos: e.payload?.data?.videos || []
      }));
    },
    async open(path) {
      const r = await rt().sendRequest('fs.raw', { path: path.replace(/^sandbox:\/\//, '') });
      const blob = r instanceof Blob ? r : r.data;
      files.set(++fileSeq, blob);
      return { id: fileSeq, size: blob.size };
    },
    async slice(id, i) {
      return b64(new Uint8Array(await files.get(id).slice(i * CHUNK, (i + 1) * CHUNK).arrayBuffer()));
    },
    closeFile(id) {
      files.delete(id);
      return null;
    },
    async cancel(sid) {
      await rt().sendRequest('chat.cancel', { session_id: sid });
      return null;
    },
    // Hạn mức: server action Next.js "fetchSubscriptionAction" (id đổi theo bản Muse → tìm trong file JS đã tải).
    // Mọi nhánh lỗi trả cùng shape { ok:false, reason, reasonCode } — nhánh "không thấy id" trước đây trả { result:null }
    // làm parseQuota nhận sai và fail im lặng. Thành công → { ok:true, subscription }.
    // ID được cache theo "bản build" (danh sách URL script) + lưu localStorage: đổi build Muse thì tự dò lại,
    // giữ nguyên build thì mở app lần sau dùng lại ID — không phải tải lại toàn bộ JS mỗi lần hỏi hạn mức.
    async quota() {
      const buildKey = () => [...new Set(performance.getEntriesByType('resource').map(e => e.name).filter(u => /_next\/static\/.*\.js(\?|$)/.test(u)))].sort().join('|');
      let cached = null;
      try { cached = JSON.parse(localStorage.getItem('__mssQuotaCache') || 'null'); } catch (e) {}
      if (!window.__mssQuotaId && cached && cached.build === buildKey() && cached.id) window.__mssQuotaId = cached.id;

      if (!window.__mssQuotaId) {
        const re = /createServerReference\)\("([0-9a-f]{20,})",[^;]{0,120}?"fetchSubscriptionAction"\)/;
        const urls = [...new Set(performance.getEntriesByType('resource').map(e => e.name).filter(u => /\.js(\?|$)/.test(u)))];
        for (const u of urls) {
          const m = re.exec(await fetch(u).then(r => r.text()).catch(() => ''));
          // bỏ giả định thứ tự: có thể có nhiều id, lấy cái gắn với tên action
          if (m) { window.__mssQuotaId = m[1]; break; }
        }
        if (!window.__mssQuotaId) return { ok: false, reason: 'Không thấy mã fetchSubscriptionAction trong file JS của Muse (giao diện Muse có thể đã đổi). Hạn mức chỉ để hiển thị — render vẫn chạy.', reasonCode: 'no-action-id' };
        try { localStorage.setItem('__mssQuotaCache', JSON.stringify({ id: window.__mssQuotaId, build: buildKey(), at: Date.now() })); } catch (e) {}
      }
      const r = await fetch('/', {
        method: 'POST', credentials: 'include', body: JSON.stringify([{}]),
        headers: { 'Next-Action': window.__mssQuotaId, Accept: 'text/x-component', 'Content-Type': 'text/plain;charset=UTF-8' }
      });
      if (!r.ok) {
        // ID cũ (build trước) → xoá cache để lần sau dò lại từ đầu
        window.__mssQuotaId = '';
        try { localStorage.removeItem('__mssQuotaCache'); } catch (e) {}
        return { ok: false, reason: `Muse trả HTTP ${r.status} khi hỏi hạn mức (mã action có thể đã cũ, lần sau sẽ tự dò lại)`, reasonCode: 'http' };
      }
      for (const line of (await r.text()).split('\n')) {
        if (!line.includes('"success"')) continue;
        try {
          const j = JSON.parse(line.slice(line.indexOf(':') + 1));
          if (j.success && j.subscription) return { ok: true, subscription: j.subscription };
        } catch (e) {}
      }
      return { ok: false, reason: 'Muse trả lời nhưng không có dữ liệu subscription', reasonCode: 'no-subscription' };
    }
  });
}

const PAGE_SCRIPT = `(${pageMain.toString()})(${CHUNK})`;

// Sự kiện assistant [{text, images, videos}] → {files:[{path,mime,byteLen}], text}. Video trước ảnh, bỏ file missing.
function parseResult(events) {
  const pick = list => list.filter(m => !m.missing).map(m => ({ path: m.path, mime: m.mime, byteLen: m.byte_len }));
  return {
    files: [...pick(events.flatMap(e => e.videos)), ...pick(events.flatMap(e => e.images))],
    text: events.map(e => e.text).filter(Boolean).join('\n')
  };
}

// subscription của Muse → {pct, resetsAt (ms), status, tier, paid, topupLeft (0..1 | null), topupBalance, topupTotal, label, subtitle, checkedAt}
function parseQuota(sub) {
  if (!sub?.usage) return null;
  const total = Number(sub.topupTotal) || 0;
  return {
    pct: Number(sub.usage.percentUsed) || 0, resetsAt: (Number(sub.usage.resetsAt) || 0) * 1000, status: sub.usage.quotaStatus || '',
    tier: sub.tier?.name || '', paid: Boolean(sub.tier?.isPaid), topupLeft: total > 0 ? (Number(sub.topupBalance) || 0) / total : null,
    topupBalance: Number(sub.topupBalance) || 0, topupTotal: total,
    label: sub.usageRowValueLabel || '', subtitle: sub.statusSubtitle || '', checkedAt: Date.now()
  };
}

class MusePage {
  constructor(chrome) {
    this.chrome = chrome;
  }

  // Tài khoản đã xoá → không bao giờ mở lại Chrome (vòng dò đăng nhập cũ còn chạy sẽ mở Chrome mồ côi, tắt app cũng không đóng)
  async ready() {
    if (this.removed) throw new Error('Tài khoản đã bị xoá');
    if (!this.chrome.running) await this.chrome.start();
  }

  async call(name, ...args) {
    await this.ready();
    // send chờ Muse chuẩn bị máy (waitForReadiness) → cho tới 3 phút
    return this.chrome.evaluate(`(window.__mss || ${PAGE_SCRIPT})[${JSON.stringify(name)}](...${JSON.stringify(args)})`, name === 'send' ? 180e3 : undefined);
  }

  login() { return this.call('login'); }
  // Không thấy client chat → về trang chủ Muse rồi gửi lại 1 lần (trang lạ/kẹt sau khi người dùng bấm lung tung)
  // thread = sessionId chat cũ: gửi tiếp vào chat đó (không tạo chat mới, không chuyển trang)
  async send(text, atts, thread = '') {
    const r = await this.call('send', text, atts, thread);
    if (!/^not_ready/.test(r?.reason || '')) return r;
    await this.chrome.cmd('Page.navigate', { url: this.chrome.url }, this.chrome.sessionId);
    return this.call('send', text, atts, thread);
  }
  status(sid) { return this.call('status', sid); }
  async result(sid) { return parseResult(await this.call('result', sid)); }
  cancel(sid) { return this.call('cancel', sid); }
  // Chấp nhận cả shape cũ (subscription thô) và shape mới ({ok, subscription}).
  // Không đọc được → null (vẫn giữ lý do trong this.lastQuotaError để UI/log hiện).
  async quota() {
    this.lastQuotaError = '';
    const r = await this.call('quota');
    if (r && r.ok === false) { this.lastQuotaError = r.reason || 'không rõ lý do'; return null; }
    const sub = r && typeof r === 'object' && 'subscription' in r ? r.subscription : r;
    const q = parseQuota(sub);
    if (!q) this.lastQuotaError = 'Muse không trả dữ liệu subscription';
    return q;
  }

  async readFile(path) {
    const { id, size } = await this.call('open', path);
    try {
      const parts = [];
      for (let i = 0; i * CHUNK < size; i++) parts.push(Buffer.from(await this.call('slice', id, i), 'base64'));
      return Buffer.concat(parts);
    } finally {
      await this.call('closeFile', id).catch(() => {});
    }
  }

  async show() { await this.ready(); await this.chrome.show(); }
  async hide() { if (this.chrome?.running) await this.chrome.hide(); }
  async logout() { await this.ready(); await this.chrome.clearSiteData('https://muse.ai'); }
}

module.exports = { MusePage, parseResult, parseQuota, PAGE_SCRIPT, CHUNK };
