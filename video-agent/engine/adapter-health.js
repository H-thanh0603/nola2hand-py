/**
 * ADAPTER HEALTH — kiểm Muse adapter (`engine/muse-page.js`) còn khớp với UI Muse không.
 *
 * Vì sao cần: adapter bám vào nội bộ React của Muse (`__reactFiber`, `memoizedProps.value.sendMessage`,
 * `__hatchEarlyGatewayRuntimeState.activeRuntime`, `sessions.list`, `chat.history`, `fs.raw`).
 * Muse cập nhật là gãy. Trước đây gãy bị báo chung chung "not_ready (/thread/x)" khiến người dùng
 * tưởng lỗi mạng hoặc tài khoản. Ở đây phân biệt rõ từng mảnh gãy và nói việc phải làm.
 *
 * Không phụ thuộc Electron / trình duyệt: `page` chỉ cần `.call(name, ...)` để test bằng trang giả.
 */

// Các mảnh adapter và mã gãy tương ứng
const PARTS = {
  chat: 'adapter.chat', // tìm được object chat (sendMessage) trong cây React
  runtime: 'adapter.runtime', // __hatchEarlyGatewayRuntimeState.activeRuntime.sendRequest
  login: 'adapter.login', // /api/session + client chat
  send: 'adapter.send', // gọi được sendMessage()
  history: 'adapter.history', // chat.history
  quota: 'adapter.quota' // server action fetchSubscriptionAction
};

const HINTS = {
  [PARTS.chat]: 'Muse đổi cấu trúc cây React (không còn object chat có sendMessage) → cần cập nhật engine/muse-page.js',
  [PARTS.runtime]: 'Muse đổi tên cổng runtime (__hatchEarlyGatewayRuntimeState) → cần cập nhật engine/muse-page.js',
  [PARTS.login]: 'Không thấy client chat sau khi tải Muse (hoặc /api/session lỗi). Trang chưa dựng xong → thử lại; lặp lại cả ngày thì Muse đổi giao diện → cần cập nhật engine/muse-page.js',
  [PARTS.send]: 'Muse không nhận lệnh từ adapter → cần cập nhật engine/muse-page.js',
  [PARTS.history]: 'Muse đổi cách đọc lịch sử chat (chat.history) → cần cập nhật engine/muse-page.js',
  [PARTS.quota]: 'Không đọc được hạn mức (fetchSubscriptionAction) — chỉ ảnh hưởng hiển thị hạn mức, không chặn render'
};

// Lỗi "gãy adapter" từ trang Muse → mã + lời khuyên. null nếu là lỗi thường (mạng, chưa đăng nhập...).
function classify(err) {
  const msg = String((err && err.message) || err || '');
  if (/not_ready/i.test(msg)) return { code: PARTS.chat, hint: HINTS[PARTS.chat], detail: msg };
  if (/__hatchEarlyGatewayRuntimeState|activeRuntime|sendRequest/i.test(msg)) return { code: PARTS.runtime, hint: HINTS[PARTS.runtime], detail: msg };
  if (/fetchSubscriptionAction/i.test(msg)) return { code: PARTS.quota, hint: HINTS[PARTS.quota], detail: msg };
  if (/chat\.history/i.test(msg)) return { code: PARTS.history, hint: HINTS[PARTS.history], detail: msg };
  return null;
}

// Kết quả kiểm thành công: liệt kê mảnh nào sống, mảnh nào gãy. `ok` = adapter đủ dùng để render video.
async function check(page) {
  const misses = [];
  const add = (part, detail) => misses.push({ code: part, hint: HINTS[part], detail });

  // 1) Trang trả lời không? (lỗi CDP/Chrome đóng là lỗi môi trường, không phải adapter)
  const login = await page.call('login').catch(e => ({ __err: e }));
  if (login && login.__err) {
    const c = classify(login.__err);
    if (c) add(c.code, c.detail);
    return { ok: false, misses, environment: !c, checkedAt: Date.now() };
  }
  // 2) Đã đăng nhập + có client chat?
  if (!login || login.loggedIn !== true) add(PARTS.login, `login() trả http=${login?.http ?? '?'}, có chat=${Boolean(login?.loggedIn)}`);

  // 3) Lịch sử chat gọi được? Dùng 1 sessionId vô danh: lỗi "không tìm thấy" vẫn chứng minh RPC sống.
  const hist = await page.call('result', '__healthcheck__').catch(e => ({ __err: e }));
  if (hist && hist.__err) {
    const c = classify(hist.__err);
    // Không phân loại được + không giống lỗi mạng → vẫn là lỗi adapter lịch sử
    if (c) add(c.code, c.detail);
    else if (!/Chrome đã đóng|Timeout|ENOTFOUND|ECONN/i.test(String(hist.__err.message))) add(PARTS.history, String(hist.__err.message));
  } else if (hist === null) {
    add(PARTS.history, 'chat.history trả null thay vì danh sách');
  }

  // 4) Hạn mức: không có thì chỉ cảnh báo (render vẫn được)
  const quota = await page.call('quota').catch(e => ({ __err: e, ok: false, reason: e.message }));
  const quotaOk = Boolean(quota && quota.ok !== false && quota.subscription);
  if (!quotaOk) add(PARTS.quota, (quota && (quota.reason || quota.__err?.message)) || 'không có subscription');

  // đủ dùng để render = có chat; quota không tính là chặn
  const blocking = misses.filter(m => m.code !== PARTS.quota);
  return { ok: blocking.length === 0, misses, quotaOk, checkedAt: Date.now() };
}

// Mô tả ngắn để đưa vào lỗi task / log
function describe(result) {
  if (!result || result.ok) return '';
  const parts = result.misses.map(m => `${m.code}: ${String(m.detail).slice(0, 160)}`);
  const hint = result.misses.find(m => m.code !== PARTS.quota)?.hint || HINTS[PARTS.quota];
  return `Muse adapter gãy — ${parts.join(' | ')}. ${hint}`;
}

module.exports = { PARTS, HINTS, check, classify, describe };
