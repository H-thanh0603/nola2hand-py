/**
 * Kiểm tra Muse đã đăng nhập trong profile của agent chưa, và mở cửa sổ cho người dùng đăng nhập.
 *
 *   node login.js          → mở Chrome + tới muse.ai (đăng nhập xong, Ctrl+C)
 *   node login.js --check  → chỉ hỏi trạng thái rồi thoát
 *
 * Vì sao cần: agent chạy Chrome ẩn ngoài màn hình (window-position -32000) và trang about:blank,
 * nên đăng nhập ở cửa sổ Chrome khác (profile khác) không có tác dụng.
 */
const path = require('path');
const { Chrome } = require('./engine/chrome');
const { MusePage } = require('./engine/muse-page');

const PROFILE_DIR = process.env.VIDEO_AGENT_PROFILE || path.join(__dirname, '.profile');

(async () => {
  const checkOnly = process.argv.includes('--check');
  const page = new MusePage(new Chrome({ profileDir: PROFILE_DIR, url: 'https://muse.ai' }));

  try {
    if (!checkOnly) {
      await page.show();
      console.log('Đã mở cửa sổ Chrome. Đăng nhập muse.ai rồi quay lại đây bấm Ctrl+C.');
    }
    const result = await page.login();
    console.log('login():', JSON.stringify(result));
    if (!checkOnly) {
      // Chờ tới khi đăng nhập xong để in kết quả cuối
      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        const now = await page.login().catch(() => null);
        if (now?.loggedIn) {
          console.log('✅ Đã đăng nhập Muse. Có thể đóng cửa sổ này.');
          break;
        }
      }
    }
  } catch (e) {
    console.error('Lỗi:', e.message);
    process.exitCode = 1;
  } finally {
    if (checkOnly) await page.chrome.close().catch(() => {});
  }
})();
