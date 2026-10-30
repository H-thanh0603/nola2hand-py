// buildMessage không được tự thêm mốc thời gian nào ngoài prompt đã được FastAPI làm sạch.
const test = require('node:test');
const assert = require('node:assert');
const { buildMessage } = require('../engine/muse-runner');

test('buildMessage giữ nguyên prompt đã ép 10 giây', () => {
  const msg = buildMessage({ kind: 'video', ratio: '9:16', prompt: 'Tạo video 10 giây\ncận cảnh tai nghe' });
  assert.strictEqual(msg, 'Tạo video · tỷ lệ 9:16 dọc\nTạo video 10 giây\ncận cảnh tai nghe');
});

test('buildMessage không tự thêm mốc thời gian khác', () => {
  const msg = buildMessage({ kind: 'video', ratio: '9:16', prompt: 'x' });
  assert.ok(!/\b(?:15|20|30)\b/.test(msg));
});
