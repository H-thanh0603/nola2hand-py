/**
 * QUALITY GATE — kiểm tra video sau khi tải về / ghép bằng ffprobe, để lỗi hiện ra rõ
 * thay vì "đủ 3 cảnh nhưng video chỉ có 1 cảnh", "video không phát", "không có lời".
 *
 * Kiểm: file tồn tại + > 0 byte, có luồng video, thời lượng ≥ minSecs, codec/độ phân giải
 * (khi yêu cầu), có tiếng (khi yêu cầu). Thuần: `probe` truyền vào để test bằng ffprobe giả.
 */

const fs = require('fs');
const { execFile } = require('child_process');

// Hạn mức mặc định — dự án ghi ho "4-6s" thì 4.2s vẫn tính là đạt
const NEED = { codec: '', height: 0, audio: false, minSecs: 1 };

// ffprobe bất đồng bộ: trả { streams, format } hoặc null khi không đọc được
function ffprobeInfo(file, ffprobe) {
  return new Promise(resolve => {
    if (!ffprobe) return resolve(null);
    execFile(ffprobe, ['-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', file],
      { maxBuffer: 8 << 20, timeout: 30000 }, (err, out) => {
        if (err) return resolve(null);
        try { resolve(JSON.parse(out)); } catch { resolve(null); }
      });
  });
}

// Thông tin cần cho việc kiểm; `info` = kết quả ffprobe. Không đọc được → null.
function summarize(info, stat) {
  if (!info) return null;
  const streams = Array.isArray(info.streams) ? info.streams : [];
  const v = streams.find(s => s.codec_type === 'video' && !s.disposition?.attached_pic);
  const a = streams.find(s => s.codec_type === 'audio');
  return {
    size: stat?.size ?? 0,
    secs: Number(info.format?.duration) || Number(v?.duration) || 0,
    codec: v?.codec_name || '',
    width: Number(v?.width) || 0,
    height: Number(v?.height) || 0,
    hasVideo: Boolean(v),
    hasAudio: Boolean(a),
    audioCodec: a?.codec_name || ''
  };
}

/**
 * check({ file, ffprobe, need }) → { ok, problems[], info }
 * need: { minSecs, codec, height, audio } — chỉ kiểm mục nào có trong need.
 */
async function check({ file, ffprobe, need = {}, probe = ffprobeInfo }) {
  const n = { ...NEED, ...need };
  const problems = [];
  const stat = fs.existsSync(file) ? fs.statSync(file) : null;
  if (!stat) return { ok: false, problems: [`Không thấy file ${file}`], info: null };
  if (!stat.size) return { ok: false, problems: ['File rỗng (0 byte)'], info: null };

  const info = summarize(await probe(file, ffprobe), stat);
  if (!info) return { ok: false, problems: ['Không đọc được video (file hỏng hoặc thiếu ffprobe)'], info: null };

  if (!info.hasVideo) problems.push('Không có luồng video (chỉ thấy tiếng)');
  else {
    if (n.minSecs > 0 && info.secs > 0 && info.secs < n.minSecs) problems.push(`Video quá ngắn: ${info.secs.toFixed(1)}s (cần ≥ ${n.minSecs}s)`);
    const allowed = String(n.codec).split(/[|,]/).map(c => c.trim().toLowerCase()).filter(Boolean);
    if (allowed.length && info.codec && !allowed.includes(info.codec.toLowerCase())) problems.push(`Codec ${info.codec} khác yêu cầu ${allowed.join('/')}`);
    if (n.height > 0 && info.height > 0 && info.height < n.height) problems.push(`Độ phân giải thấp: ${info.width}×${info.height} (cần cao ≥ ${n.height})`);
  }
  if (n.audio && !info.hasAudio) problems.push('Không có tiếng (lời thoại/nhạc bị mất)');

  return { ok: problems.length === 0, problems, info };
}

// Nhiều file (các cảnh) → kiểm từng cái, gom lỗi ghi rõ cảnh nào
async function checkMany(files, opts = {}) {
  const out = [];
  for (const [i, file] of files.entries()) {
    const r = await check({ ...opts, file });
    out.push({ ...r, file, index: i, problems: r.problems.map(p => (files.length > 1 ? `Cảnh ${i + 1}: ${p}` : p)) });
  }
  const problems = out.flatMap(r => r.problems);
  return { ok: problems.length === 0, problems, results: out };
}

// Hạn mức cho việc ghép nhiều cảnh: video ra phải dài ≈ tổng các cảnh (dung sai 8% + 2s)
function mergeNeed(inputSecs, { audio = false } = {}) {
  const total = inputSecs.reduce((s, x) => s + (Number(x) || 0), 0);
  return { minSecs: Math.max(0, total * 0.92 - 2), audio };
}

module.exports = { check, checkMany, summarize, ffprobeInfo, mergeNeed, NEED };
