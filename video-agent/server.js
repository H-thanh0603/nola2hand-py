/**
 * VIDEO AGENT — HTTP nội bộ cho backend nola2hand, điều khiển Muse qua Chrome CDP.
 *
 * Chỉ nghe 127.0.0.1. Mỗi lần chạy 1 job (Muse không hợp chạy song song trên 1 tài khoản).
 * Engine chép từ HaoHao (Horizon LLC, "Proprietary") — dùng cho đồ án học tập, không phát hành thương mại.
 *
 *   POST /jobs      {prompt, images:[{mimeType,dataBase64}], outputDir?}  → {id}
 *   GET  /jobs/:id  → {id, status, error, file}
 *   POST /jobs/:id/cancel
 *   GET  /health    → {ok, chrome, museLogin, error}
 */
const http = require('http');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const { Chrome } = require('./engine/chrome');
const { MusePage } = require('./engine/muse-page');
const { runTask, ensureLogin } = require('./engine/muse-runner');
const verifier = require('./engine/verify');

const PORT = Number(process.env.VIDEO_AGENT_PORT) || 48910;
const HOST = '127.0.0.1';
const PROFILE_DIR = process.env.VIDEO_AGENT_PROFILE || path.join(__dirname, '.profile');
const OUTPUT_ROOT = path.join(__dirname, '.output');
const MAX_BODY = 40 * 1024 * 1024; // 3 ảnh base64 + prompt, dư rộng
const MIN_VIDEO_SECS = 2;

const jobs = new Map(); // id → job
let queue = Promise.resolve(); // chạy tuần tự
let page = null;

// ffprobe: ưu tiên PATH, sau đó các vị trí phổ biến (snap/flatpak trên Linux)
function ffprobePath() {
  const candidates = [
    process.env.FFPROBE_PATH,
    '/usr/bin/ffprobe',
    '/usr/local/bin/ffprobe',
    '/snap/bin/ffprobe',
  ].filter(Boolean);
  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch (e) {}
  }
  return 'ffprobe'; // để execFile tự báo lỗi nếu không có
}

function getPage() {
  if (!page) page = new MusePage(new Chrome({ profileDir: PROFILE_DIR, url: 'https://muse.ai' }));
  return page;
}

// Muse là SPA: mở Chrome xong trang còn đang tải, `login()` hỏi ngay sẽ trả loggedIn:false
// dù cookie hợp lệ. Hỏi lại tới khi trang dựng xong client chat (tối đa `waitMs`).
async function waitForLogin(pg, waitMs = 30e3) {
  const start = Date.now();
  let last = { loggedIn: false };
  for (;;) {
    last = await pg.login().catch((e) => ({ loggedIn: false, error: e.message }));
    if (last.loggedIn) return last;
    if (Date.now() - start >= waitMs) return last;
    await new Promise((r) => setTimeout(r, 2000));
  }
}

function safeOutputDir(requested) {
  const dir = requested ? path.resolve(OUTPUT_ROOT, path.basename(String(requested))) : path.join(OUTPUT_ROOT, 'default');
  if (!dir.startsWith(OUTPUT_ROOT + path.sep) && dir !== OUTPUT_ROOT) throw new Error('outputDir không hợp lệ');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

async function runJob(job) {
  job.status = 'running';
  try {
    const p = getPage();
    if (!(await ensureLogin(p, { waitMs: 5 * 60e3 }))) throw new Error('Chưa đăng nhập Muse — chạy "node login.js" trong video-agent để đăng nhập');
    const saved = await runTask(
      {
        kind: 'video',
        ratio: '9:16',
        prompt: job.prompt,
        images: new Map(job.images.map((img, i) => [i, img])),
        timeoutMin: 15,
        attempts: 0,
        startedAt: Date.now(),
      },
      {
        page: p,
        outputDir: job.outputDir,
        loadImage: async (img) => ({ mimeType: img.mimeType, dataBase64: img.dataBase64 }),
        update: (patch) => Object.assign(job, patch, { step: patch.step || job.step }),
        isLive: () => job.status === 'running',
        limits: { image: 5, video: 15 },
      },
    );
    if (!saved || !saved.length) throw new Error('Không nhận được file video');
    const file = saved[0];
    // Quality gate: file phải có luồng video và dài tối thiểu 2 giây
    const check = await verifier.check({ file, ffprobe: ffprobePath(), need: { minSecs: MIN_VIDEO_SECS } });
    if (!check.ok) throw new Error('Video không đạt: ' + check.problems.join('; '));
    job.file = file;
    job.status = 'done';
  } catch (e) {
    job.error = e.message;
    job.status = 'failed';
  } finally {
    job.finishedAt = Date.now();
  }
}

function enqueue(job) {
  jobs.set(job.id, job);
  queue = queue.then(() => runJob(job)).catch(() => {});
  return job.id;
}

function send(res, code, body) {
  const data = JSON.stringify(body);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(data) });
  res.end(data);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new Error('Payload quá lớn'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => {
      try {
        resolve(chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {});
      } catch (e) {
        reject(new Error('JSON không hợp lệ'));
      }
    });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${HOST}`);
  const p = url.pathname;

  try {
    if (req.method === 'GET' && p === '/health') {
      const pg = getPage();
      let login = false;
      let error = '';
      try {
        login = Boolean((await waitForLogin(pg)).loggedIn);
      } catch (e) {
        error = e.message;
      }
      return send(res, 200, { ok: !error, chrome: Boolean(pg.chrome?.running), museLogin: login, error });
    }

    // Trang chủ: agent không có UI, trả chỉ dẫn thay vì 404 khó hiểu.
    if (req.method === 'GET' && p === '/') {
      return send(res, 200, {
        service: 'nola-video-agent',
        endpoints: ['GET /health', 'POST /jobs', 'GET /jobs/:id', 'POST /jobs/:id/cancel'],
        hint: 'Đăng nhập Muse: node login.js (mở cửa sổ Chrome). Backend bật VIDEO_AGENT_ENABLED=true.',
      });
    }

    if (req.method === 'POST' && p === '/jobs') {
      const body = await readBody(req);
      const prompt = String(body.prompt || '').trim();
      const images = Array.isArray(body.images) ? body.images : [];
      if (!prompt) return send(res, 400, { error: 'prompt rỗng' });
      if (!images.length) return send(res, 400, { error: 'cần ít nhất 1 ảnh' });
      if (images.length > 3) return send(res, 400, { error: 'tối đa 3 ảnh' });
      const job = {
        id: 'job_' + crypto.randomBytes(8).toString('hex'),
        status: 'queued',
        prompt,
        images,
        outputDir: safeOutputDir(body.outputDir),
        error: null,
        file: null,
        createdAt: Date.now(),
      };
      return send(res, 201, { id: enqueue(job) });
    }

    const m = /^\/jobs\/(job_[0-9a-f]+)(\/cancel)?$/.exec(p);
    if (m && jobs.has(m[1])) {
      const job = jobs.get(m[1]);
      if (req.method === 'GET' && !m[2]) {
        return send(res, 200, { id: job.id, status: job.status, error: job.error, file: job.file, step: job.step || '' });
      }
      if (req.method === 'POST' && m[2]) {
        if (job.status === 'queued' || job.status === 'running') {
          job.status = 'cancelled';
          job.error = 'Người dùng huỷ';
        }
        return send(res, 200, { ok: true });
      }
    }

    send(res, 404, { error: 'Endpoint không tồn tại' });
  } catch (e) {
    send(res, 400, { error: e.message });
  }
});

if (require.main === module) {
  fs.mkdirSync(OUTPUT_ROOT, { recursive: true });
  server.listen(PORT, HOST, () => {
    console.log(`video-agent nghe http://${HOST}:${PORT} — profile: ${PROFILE_DIR}`);
  });
}

module.exports = { server, jobs, safeOutputDir };
