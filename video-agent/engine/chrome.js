/**
 * CHROME — mở Google Chrome thật của máy (không headless) với profile riêng, điều khiển qua CDP bằng pipe.
 * Pipe: fd 3 = app ghi lệnh, fd 4 = Chrome trả lời; mỗi tin là JSON kết thúc bằng \0. Không mở cổng mạng nào.
 * Chrome 136+ không cho điều khiển profile chính → mỗi tài khoản 1 thư mục profile riêng.
 *
 * Backend:
 * - 'pipe' (mặc định): remote-debugging-pipe — an toàn nhất, không có cổng TCP.
 *   Một số bản Chrome (đã gặp 155.x trên Linux) bỏ "Remote debugging pipe file descriptors are not open."
 *   dù fd 3/4 đã mở → launch() bắt stderr, phát hiện, đóng và tự nâng cấp sang backend 'ws' (mở lại 1 lần).
 * - 'ws' : remote-debugging-port=0 trên 127.0.0.1 (chỉ UDP/lấy cổng ngẫu nhiên), đọc DevToolsActivePort.
 *   Dùng làm dự phòng; vẫn chỉ nghe localhost.
 * Có thể ép backend bằng env MSS_CDP_BACKEND=pipe|ws (dùng khi test / khi Chrome bản mới bắt buộc 1 kiểu).
 */

const { spawn, execFile } = require('child_process');
const { EventEmitter } = require('events');
const fs = require('fs');
const path = require('path');

const IS_MAC = process.platform === 'darwin';
const IS_WIN = process.platform === 'win32';
// Chrome của máy: Mac trong /Applications; Windows trong Program Files hoặc AppData\Local (cài riêng 1 người dùng); Linux trong PATH/standard
const CHROME_PATH = IS_MAC ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  : IS_WIN ? [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean)
    .map(d => path.join(d, 'Google', 'Chrome', 'Application', 'chrome.exe')).find(p => fs.existsSync(p)) || 'chrome.exe'
    : ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser',
      '/snap/bin/chromium', '/var/lib/flatpak/exports/bin/com.google.Chrome']
      .find(p => fs.existsSync(p)) || 'google-chrome';
// Windows không có "ẩn app" như Mac → đẩy cửa sổ ra ngoài màn hình (vẫn chạy JS bình thường, không bị thu nhỏ)
const OFF = { left: -32000, top: -32000 };
const sleep = ms => new Promise(r => setTimeout(r, ms));
// Ẩn/hiện cả app Chrome theo PID (như Cmd+H): không cửa sổ, không thu nhỏ xuống Dock, JS vẫn chạy (đã có cờ chống throttle)
const appProc = (pid, act, done) => execFile('osascript', ['-l', 'JavaScript', '-e',
  `ObjC.import('AppKit'); const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier(${pid}); app.${act}`], done);
const appCall = (pid, act) => new Promise(r => appProc(pid, act, () => r()));
// Chạy run loop thay vì delay(): app.hidden chỉ cập nhật khi run loop chạy
const TICK = '$.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.25))';
// Chrome ẩn/thu nhỏ: trang tải mới không chạy requestAnimationFrame + báo hidden → Muse (Next.js) không dựng xong, mất client chat.
// Nạp trước mỗi trang: báo luôn "visible", rAF không chạy thì setTimeout 16ms thay.
const VISIBLE_SHIM = `(() => {
  Object.defineProperty(Document.prototype, 'visibilityState', { get: () => 'visible', configurable: true });
  Object.defineProperty(Document.prototype, 'hidden', { get: () => false, configurable: true });
  const raf = window.requestAnimationFrame.bind(window), caf = window.cancelAnimationFrame.bind(window);
  const t = new Map(); let seq = 0;
  window.requestAnimationFrame = cb => {
    const id = ++seq; let done = false;
    const run = ts => { if (done) return; done = true; t.delete(id); cb(ts); };
    t.set(id, [raf(run), setTimeout(() => run(performance.now()), 16)]);
    return id;
  };
  window.cancelAnimationFrame = id => { const v = t.get(id); if (v) { caf(v[0]); clearTimeout(v[1]); t.delete(id); } };
})();`;

class Chrome extends EventEmitter {
  // proxy = { server: 'http://ip:port' | 'socks5://ip:port', username, password } — có user/pass thì trả lời đăng nhập proxy qua CDP Fetch
  // resolveProxy = async () => proxy | null: hỏi lại mỗi lần mở Chrome (đổi proxy chỉ cần đóng Chrome, lần sau tự mở với proxy mới)
  // backend = 'pipe' | 'ws' — 'auto' (mặc định): thử pipe, gặp Chrome không hỗ trợ thì chuyển ws
  constructor({ profileDir, url, chromePath = CHROME_PATH, proxy = null, resolveProxy = null, backend }) {
    super();
    Object.assign(this, { profileDir, url, chromePath, proxy, resolveProxy });
    this.backend = backend || process.env.MSS_CDP_BACKEND || 'auto';
    this.proc = null;
    this.sessionId = '';
    this.seq = 0;
    this.pending = new Map();
  }

  // Sẵn sàng = Chrome chạy VÀ đang gắn vào 1 tab. Mac: đóng cửa sổ thì Chrome vẫn chạy nhưng mất tab.
  get running() {
    return Boolean(this.proc && this.sessionId);
  }

  // Gọi chồng nhau (lúc khởi động) → dùng chung 1 lần mở
  start() {
    return (this.starting ||= this.launch().finally(() => { this.starting = null; }));
  }

  // Thông điệp Chrome chết ngay vì sandbox không đúng → thử lại với --no-sandbox (chỉ khi MSS_CHROME_SANDBOX != 1)
  static SANDBOX_BROKEN = /SUID sandbox helper binary|No usable sandbox|--no-sandbox|Failed to move to new namespace|namespace sandbox/i;

  async launch() {
    if (this.proc) return this.attach();
    if (!fs.existsSync(this.chromePath)) throw new Error('Không tìm thấy Google Chrome — cài Google Chrome rồi mở lại app');
    fs.mkdirSync(this.profileDir, { recursive: true });
    if (this.resolveProxy) this.proxy = await this.resolveProxy();
    // auto: lần trước đã biết pipe hỏng (ví dụ Chrome 155 trên Linux) → đi thẳng ws
    const mode = this.backend === 'auto' ? (this.pipeUnsupported ? 'ws' : 'pipe') : this.backend;
    try {
      await this._spawn(mode);
    } catch (e) {
      // Ưu tiên xử lý nguyên nhân GỐC trước khi retry profile bận:
      // - sandbox hỏng → bật --no-sandbox rồi thử lại
      // - pipe hỏng → chuyển ws
      // Chỉ khi không phải 2 lỗi trên mới coi là "profile vừa bị Chrome cũ giữ" và retry.
      // (Trước đây retry profile bắt nhầm lỗi sandbox và lặp 2 lần với sandbox → vẫn chết.)
      if (!this.noSandbox && process.env.MSS_CHROME_SANDBOX !== '1' && Chrome.SANDBOX_BROKEN.test(e.message)) {
        this.noSandbox = true;
        await this.close();
        return this.launch();
      }
      if (mode === 'pipe' && /pipe_unavailable/.test(e.message)) {
        this.pipeUnsupported = true;
        await this.close();
        return this.launch(); // đi lại từ đầu theo backend mới
      }
      // Chrome lần trước của CÙNG profile vừa đóng nhưng tiến trình con chưa thoát → Chrome mới thoát ngay.
      // Chờ rồi thử lại (tối đa 2 lần) trước khi báo lỗi.
      if (/DevToolsActivePort|SingletonLock|đang được dùng/i.test(e.message) && (this.launchRetries = (this.launchRetries || 0) + 1) <= 2) {
        await this.close();
        await new Promise(r => setTimeout(r, 800));
        return this.launch();
      }
      this.launchRetries = 0;
      throw e;
    }
  }

  // Tạo tiến trình Chrome + kênh CDP (pipe hoặc websocket localhost)
  async _spawn(mode) {
    const isPipe = mode === 'pipe';
    this.mode = mode;
    const proc = spawn(this.chromePath, [
      `--user-data-dir=${this.profileDir}`,
      // 'ws': cổng ngẫu nhiên trên 127.0.0.1; trình duyệt ghi cổng thật vào DevToolsActivePort
      isPipe ? '--remote-debugging-pipe' : '--remote-debugging-port=0',
      '--no-first-run',
      '--no-default-browser-check',
      // Chrome thu nhỏ vẫn phải chạy JS bình thường để dò phiên Muse
      '--disable-background-timer-throttling',
      '--disable-renderer-backgrounding',
      '--disable-backgrounding-occluded-windows',
      ...(this.proxy ? [`--proxy-server=${this.proxy.server}`] : []),
      // Ubuntu 24.04 chặn unprivileged user namespace và chrome-sandbox thường không đúng mode 4755
      // → Chrome con chết ngay ("The SUID sandbox helper binary ... is not configured correctly").
      // Chỉ tắt sandbox khi tiến trình THỰC SỰ không dùng được (MSS_CHROME_SANDBOX=1 để ép bật lại).
      ...(this.noSandbox ? ['--no-sandbox'] : []),
      // Linux/Wayland bỏ qua toạ độ cửa sổ → ép XWayland để ẩn Chrome ra ngoài màn hình được
      ...(process.platform === 'linux' && process.env.DISPLAY ? ['--ozone-platform=x11'] : []),
      ...(IS_MAC ? [] : [`--window-position=${OFF.left},${OFF.top}`]), // mở sẵn ngoài màn hình, không nháy
      'about:blank' // mở trang trắng, gắn VISIBLE_SHIM rồi mới vào Muse
    ], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] });
    this.proc = proc;
    let stderr = '';
    // fd 2 phải là 'pipe' thì proc.stdio[2] mới có stream (khi là 'ignore' thì là null)
    proc.stdio[2].on('data', c => { stderr = (stderr + c).slice(-4096); });
    let buf = '';
    const onMsg = msg => {
      // Tab Muse bị đóng → bỏ phiên tab, lần gọi sau start() gắn lại
      if (msg.method === 'Target.detachedFromTarget' && msg.params.sessionId === this.sessionId) this.sessionId = '';
      if (msg.method?.startsWith('Fetch.')) this.onFetch(msg);
      const p = this.pending.get(msg.id);
      if (!p) return;
      this.pending.delete(msg.id);
      msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
    };
    // pipe: tin đến qua fd 4 (\0 phân cách). ws: tin đến qua websocket (gắn ở connectWs), fd 4 không dùng.
    proc.stdio[3].on('error', () => {});
    (isPipe ? proc.stdio[4] : null)?.on('data', chunk => {
      buf += chunk.toString('utf8');
      let i;
      while ((i = buf.indexOf('\0')) >= 0) {
        onMsg(JSON.parse(buf.slice(0, i)));
        buf = buf.slice(i + 1);
      }
    });
    proc.once('exit', () => this.onExit(proc));
    this.wsChannel = !isPipe;
    this.stderrTail = () => stderr;
    // ws: nhận tin qua websocket; pipe: nhận qua fd 4 (đã gắn ở trên)
    this.wsOnMsg = onMsg;

    try {
      if (!isPipe) await this.connectWs(proc, () => stderr, onMsg);
      // Proxy có mật khẩu: bắt yêu cầu đăng nhập proxy ở cấp trình duyệt (mọi tab) rồi trả user/pass
      if (this.proxy?.username) await this.cmd('Fetch.enable', { handleAuthRequests: true, patterns: [{ urlPattern: '*' }] });
      await this.attach();
      await this.hide(); // mở xong ẩn ngay; cần đăng nhập thì show()
      // Chrome mới mở đôi khi tự hiện lại ~1–2s sau (dựng cửa sổ đầu) → canh 10s, hiện lại thì ẩn lại; show() dừng canh
      if (IS_MAC) this.guard = appProc(proc.pid, `hide; for (let i = 0; i < 40; i++) { ${TICK}; if (!app.hidden) app.hide; }`, () => {});
      await this.cmd('Page.navigate', { url: this.url }, this.sessionId);
    } catch (e) {
      const msg = String(e?.message || e);
      // Sandbox chết (SUID helper sai owner/mode, user-namespace bị chặn) — Chrome tự thoát ngay.
      // Phải xét TRƯỚC pipeBroken: Chrome chết vì sandbox cũng khiến exitCode !== null → nếu xét sau,
      // code tưởng pipe hỏng, chuyển sang ws (vẫn chết vì sandbox) rồi fail với thông báo sai.
      const sandboxDead = Chrome.SANDBOX_BROKEN.test(stderr);
      await this.close();
      if (sandboxDead) {
        const line = stderr.split('\n').reverse().find(l => Chrome.SANDBOX_BROKEN.test(l)) || msg;
        throw new Error(`Chrome không khởi động được vì sandbox: ${line.trim()}`);
      }
      // Chrome bỏ qua --remote-debugging-pipe (một số bản 155.x Linux) → báo pipe_unavailable để launch() chuyển ws.
      const pipeBroken = isPipe && (proc.exitCode !== null || /Chrome đã đóng|Remote debugging pipe file descriptors are not open/.test(stderr + ' ' + msg));
      if (pipeBroken) throw Object.assign(new Error(`pipe_unavailable: ${(stderr.trim().split('\n')[0] || msg) || 'Chrome không dùng được remote-debugging-pipe'}`), { pipe: true });
      throw e;
    }
  }

  // Backend ws: đọc DevToolsActivePort (dòng 1 = cổng, dòng 2 = path ws), mở websocket tới 127.0.0.1.
  // Chỉ chấp nhận địa chỉ loopback: DevToolsActivePort là file trên đĩa, không được tin để mở kết nối ra ngoài.
  async connectWs(proc, stderrFn, onMsg) {
    const portFile = path.join(this.profileDir, 'DevToolsActivePort');
    let port = 0, wsPath = '';
    for (let k = 0; k < 300 && proc.exitCode === null; k++) {
      try {
        const [p, w] = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
        if (p && w) { port = Number(p); wsPath = w; break; }
      } catch (e) {}
      await sleep(100);
    }
    // Chrome 155 ghi path kiểu /devtools/browser/<uuid>; một số bản cũ là /ws/browser/<uuid>.
    // Không đúng hình dạng → từ chối (tránh dùng file bị sửa tay để trỏ sang websocket lạ).
    if (!Number.isInteger(port) || port < 1 || port > 65535 || !/^\/(devtools|ws)\/browser\/[0-9a-f-]{8,}$/i.test(wsPath)) {
      const tail = stderrFn ? String(stderrFn() || '').trim().split('\n')[0] : '';
      throw new Error(`Không đọc được DevToolsActivePort hợp lệ (Chrome có thể không cho mở cổng debug localhost)${tail ? ' — ' + tail : ''}`);
    }
    await new Promise((resolve, reject) => {
      // Luôn là 127.0.0.1 cứng, không lấy từ file → không thể trỏ ra máy khác
      const ws = new WebSocket(`ws://127.0.0.1:${port}${wsPath}`);
      this.ws = ws;
      const timer = setTimeout(() => { try { ws.close(); } catch (e) {} reject(new Error('Hết giờ kết nối websocket CDP')); }, 15e3);
      ws.onopen = () => { clearTimeout(timer); resolve(); };
      ws.onerror = e => { clearTimeout(timer); reject(new Error(`Lỗi websocket CDP: ${e.message || e.type || 'unknown'}`)); };
      // Đóng kênh (Chrome chết hoặc close() chủ động) → dọn pending như pipe exit
      ws.onclose = () => this.onExit(proc);
      ws.onmessage = m => {
        let msg;
        try { msg = JSON.parse(String(m.data)); } catch (e) { return; }
        onMsg(msg);
      };
    });
  }

  // Gắn vào tab muse.ai (hoặc tab đầu tiên); không còn tab nào → mở tab mới
  async attach() {
    let target;
    for (let k = 0; k < 10 && !target; k++) {
      const { targetInfos } = await this.cmd('Target.getTargets');
      const pages = targetInfos.filter(t => t.type === 'page');
      target = pages.find(t => t.url.includes('muse.ai')) || pages[0];
      if (!target) await sleep(200);
    }
    const targetId = target ? target.targetId : (await this.cmd('Target.createTarget', { url: this.url })).targetId;
    const { sessionId } = await this.cmd('Target.attachToTarget', { targetId, flatten: true });
    await this.cmd('Page.enable', {}, sessionId); // thiếu Page.enable thì script nạp trước không chạy
    await this.cmd('Page.addScriptToEvaluateOnNewDocument', { source: VISIBLE_SHIM }, sessionId);
    Object.assign(this, { targetId, sessionId });
  }

  onFetch({ method, params, sessionId }) {
    const { requestId } = params;
    const reply = method === 'Fetch.authRequired'
      ? this.cmd('Fetch.continueWithAuth', { requestId, authChallengeResponse: params.authChallenge.source === 'Proxy'
        ? { response: 'ProvideCredentials', username: this.proxy.username, password: this.proxy.password || '' }
        : { response: 'Default' } }, sessionId)
      : this.cmd('Fetch.continueRequest', { requestId }, sessionId);
    reply.catch(() => {});
  }

  onExit(proc) {
    if (this.proc !== proc) return;
    this.proc = null;
    this.sessionId = '';
    try { this.ws?.close(); } catch (e) {}
    this.ws = null;
    // Reject mọi lệnh đang chờ. Lệnh nội bộ (Page.navigate lúc launch, Fetch.continueRequest…) không ai await
    // → gắn .catch() rỗng trên chính promise đó để không sinh unhandledRejection (làm chết tiến trình test).
    for (const p of this.pending.values()) {
      p.promise?.catch(() => {});
      p.reject(new Error('Chrome đã đóng'));
    }
    this.pending.clear();
    this.emit('exit');
  }

  // Lệnh CDP; sessionId = lệnh cho tab Muse, không có = lệnh cho cả trình duyệt
  // Quá timeoutMs không trả lời (trang treo) → lỗi, không chờ mãi
  cmd(method, params = {}, sessionId, timeoutMs = 60e3) {
    if (!this.proc) return Promise.reject(new Error('Chrome đã đóng'));
    const id = ++this.seq;
    let entry = null;
    const promise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Chrome không trả lời ${method} (quá ${timeoutMs / 1000}s)`));
      }, timeoutMs);
      const done = f => v => { clearTimeout(timer); f(v); };
      // promise chưa gán được ở đây (TDZ); onExit gắn .catch() qua entry.promise sau khi cmd() trả về
      entry = { resolve: done(resolve), reject: done(reject) };
      this.pending.set(id, entry);
      const payload = JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) });
      if (this.wsChannel) {
        // ws: mỗi tin là 1 frame JSON (không có phân cách \0 như pipe)
        if (this.ws?.readyState !== 1) {
          this.pending.delete(id);
          clearTimeout(timer);
          return reject(new Error('Chrome đã đóng'));
        }
        this.ws.send(payload);
      } else {
        this.proc.stdio[3].write(payload + '\0');
      }
    });
    entry.promise = promise;
    return promise;
  }

  async evaluate(expression, timeoutMs) {
    if (this.proc && !this.sessionId) throw new Error('Chrome mất tab Muse');
    const r = await this.cmd('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, this.sessionId, timeoutMs);
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  }

  // Về cửa sổ thường rồi mới đặt vị trí (Chrome không cho đổi vị trí khi đang thu nhỏ/phóng to)
  async setWindow(bounds) {
    const { windowId } = await this.cmd('Browser.getWindowForTarget', { targetId: this.targetId });
    await this.cmd('Browser.setWindowBounds', { windowId, bounds: { windowState: 'normal' } });
    if (bounds) await this.cmd('Browser.setWindowBounds', { windowId, bounds });
  }

  async show() {
    this.guard?.kill();
    if (IS_MAC) await appCall(this.proc.pid, 'unhide');
    await this.setWindow(IS_MAC ? null : { left: 80, top: 40, width: 1200, height: 860 });
    await this.cmd('Target.activateTarget', { targetId: this.targetId });
    if (IS_MAC) await appCall(this.proc.pid, 'activateWithOptions(2)'); // 2 = bỏ qua app khác, đưa Chrome lên trước
  }

  // Mac: Chrome vừa mở chưa khởi động xong thì lệnh hide bị bỏ qua → thử lại tới khi ẩn được (tối đa ~10s)
  hide() {
    if (!this.proc) return Promise.resolve();
    if (!IS_MAC) return this.setWindow(OFF);
    return appCall(this.proc.pid, `hide; for (let i = 0; i < 40 && !app.hidden; i++) { ${TICK}; app.hide; }`);
  }

  async clearSiteData(origin) {
    await this.cmd('Storage.clearDataForOrigin', { origin, storageTypes: 'all' });
    await this.cmd('Page.navigate', { url: this.url }, this.sessionId);
  }

  async close() {
    const proc = this.proc;
    if (!proc) { try { this.ws?.close(); } catch (e) {} return; }
    const exited = new Promise(r => proc.once('exit', r));
    this.cmd('Browser.close').catch(() => {});
    const timer = setTimeout(() => proc.kill(), 3000);
    await exited; // 'exit' nghĩa là tiến trình cha đã thoát, các tiến trình con ghi profile có thể vẫn đang chạy
    clearTimeout(timer);
    try { this.ws?.close(); } catch (e) {}
    this.ws = null;
    // Chờ hẳn tiến trình CON của Chrome (zygote/renderer) thoát: mở lại CÙNG profileDir ngay lập tức
    // sẽ bị Chrome từ chối ("profile đang được dùng") và tiến trình mới chết → test chập chờn, app không mở được tài khoản.
    await this.waitProcessTreeGone(proc.pid);
  }

  // Đợi mọi tiến trình còn giữ profileDir thoát (tối đa 3s). Linux: quét /proc/<pid>/cmdline.
  // Nền tảng khác: chờ ngắn cố định (Mac/Windows không quét được bằng cách này).
  async waitProcessTreeGone() {
    const needle = this.profileDir;
    const gone = () => {
      try {
        for (const d of fs.readdirSync('/proc')) {
          if (!/^\d+$/.test(d)) continue;
          try { if (fs.readFileSync(`/proc/${d}/cmdline`, 'utf8').includes(needle)) return false; } catch (e) {}
        }
      } catch (e) { return true; } // không phải Linux
      return true;
    };
    for (let k = 0; k < 30; k++) {
      if (gone()) return;
      await new Promise(r => setTimeout(r, 100));
    }
  }
}

module.exports = { Chrome, CHROME_PATH };
