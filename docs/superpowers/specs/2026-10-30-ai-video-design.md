# Thiết kế: Tạo video quảng bá 10 giây bằng Muse (tích hợp HaoHao)

Ngày: 2026-10-30
Nhánh: `AI_make_video`

## 1. Mục tiêu

Người bán có một mục riêng trong nola2hand để tạo video quảng bá sản phẩm, tương tự mục
video của Shopee. Video do Muse sinh ra, chạy hoàn toàn trên hạ tầng của chủ sàn, không gọi
API AI bên ngoài từ backend.

Ràng buộc bắt buộc:

- Chỉ tạo **video 10 giây**. UI báo trước khi người dùng bắt đầu.
- Tối đa **3 ảnh** đầu vào cho một video.
- Prompt người dùng nhập được **làm sạch** (bỏ mọi mốc 15s/20s/30s…) và **luôn** kết thúc bằng
  yêu cầu 10 giây.
- Prompt được **cải thiện tự động** trước khi gửi Muse (rule-based, không gọi API).

## 2. Kiến trúc

```
React (trang Người bán → Tạo video)
  │  POST /api/v1/video-jobs  { prompt, images[<=3] base64, listingId? }
  ▼
FastAPI
  ├─ làm sạch + cải thiện prompt (thuần Python, có test)
  ├─ lưu VideoJob + ảnh tạm
  └─ POST http://127.0.0.1:48910/jobs  → sidecar
                                   ▼
                        video-agent/ (Node, tách từ HaoHao)
                          ├─ Chrome headless + profile Muse (login 1 lần)
                          ├─ engine/muse-page.js, muse-runner.js, verify.js
                          ├─ ffprobe kiểm file (có stream video, >= 2s)
                          └─ lưu .mp4 vào uploads/videos/
  ◀─ GET /api/v1/video-jobs/{id} (poll) ─ videoUrl khi xong
```

Vì sao sidecar Node: HaoHao điều khiển Muse bằng cách bơm script vào trang qua Chrome CDP và
tìm object React của Muse. Đây là code Node, không port sang Python hợp lý.

Vì sao một tài khoản Muse chung: đây là bản demo đồ án. Báo cáo ghi rõ production mỗi seller
tự kết nối tài khoản riêng.

## 3. Thành phần

### 3.1 `video-agent/` (mới, Node)

Chép từ `videotool/haohao-linux` (bản backup `haohao-linux-backup-2026-10-30`):

- `chrome.js` — khởi động Chrome, CDP
- `muse-page.js` — script trong trang Muse
- `muse-runner.js` — gửi lệnh, dò phiên, tải file
- `verify.js` — ffprobe quality gate

Thêm mới:

- `server.js` — HTTP API nội bộ, chỉ nghe `127.0.0.1:48910`
- `package.json` — không phụ thuộc Electron

API:

| Method | Path | Mô tả |
|---|---|---|
| POST | `/jobs` | `{prompt, images:[{mimeType,dataBase64}]}` → `{id}` |
| GET | `/jobs/:id` | `{status, error, file}` |
| POST | `/jobs/:id/cancel` | huỷ |
| GET | `/health` | Chrome + Muse login còn sống không |

Hàng đợi trong bộ nhớ, chạy tuần tự 1 job/lần (Muse không hợp chạy song song trên 1 tài khoản).

### 3.2 FastAPI

- `app/services/video_prompt.py` — thuần Python:
  - `strip_durations(text)` — bỏ `\d+\s*(s|giây|sec|seconds)` và các cụm "15s", "20 giây"…
  - `improve(text, listing)` — nếu < 40 từ thì ghép template 3 nhịp (mở / giữa / chốt) từ tiêu đề,
    danh mục, tình trạng, giá; thêm style quay bằng điện thoại, người Việt bình thường.
  - `finalize(prompt)` — `"Tạo video 10 giây · tỷ lệ 9:16 dọc\n" + prompt + "\nĐộ dài đúng 10 giây."`
- `app/services/video_agent.py` — client gọi sidecar (httpx), timeout, lỗi mạng rõ ràng.
- `app/routers/videos.py` — endpoint dưới `/api/v1/video-jobs`.
- Model `VideoJob`.

Giới hạn: tối đa 3 ảnh, mỗi ảnh ≤ 5 MB, tổng ≤ 8 MB (giới hạn `MAX_ATTACH` của Muse).

### 3.3 Database

Bảng mới `VideoJob` (chỉ thêm, không sửa bảng cũ):

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | int PK | |
| sellerId | int | FK User |
| listingId | int null | gắn vào tin nào |
| agentJobId | text null | id job bên sidecar |
| prompt | text | người dùng nhập |
| finalPrompt | text | sau làm sạch + cải thiện |
| status | enum `QUEUED/RUNNING/DONE/FAILED/CANCELLED` | |
| error | text null | |
| videoUrl | text null | `/uploads/videos/...` |
| createdAt / finishedAt | timestamp | |

### 3.4 Frontend

- Trang mới `/seller/video` (trong `Seller.jsx` hoặc tách `SellerVideo.jsx`):
  - Thông báo cố định: "Chỉ tạo được video 10 giây. Tối đa 3 ảnh."
  - Ô prompt + nút **Cải thiện prompt** (gọi endpoint preview, hiện kết quả trước khi gửi)
  - Chọn tối đa 3 ảnh (chặn ở client, server chặn lại)
  - Danh sách job + trạng thái + video đã xong
  - Nút "Gắn vào tin đăng"
- Trang sản phẩm: hiện video của `VideoJob` gắn với listing (nếu có).

## 4. Không làm (đợt này)

- Nhiều tài khoản Muse / mỗi seller một tài khoản.
- Ghép nhiều cảnh, chèn nhạc, phụ đề.
- Đăng Facebook Reels (HaoHao có `facebook-poster.js`, nhưng ngoài phạm vi).
- Lưu video lên Supabase Storage (đợt này lưu đĩa local như ảnh hiện tại).

## 5. Rủi ro đã biết

1. **License**: mã HaoHao ghi "Proprietary – Horizon LLC", README ghi chỉ dùng cá nhân. Đây là đồ án
   học tập, không phát hành thương mại. Cần ghi nguồn trong `video-agent/README.md`.
2. **ToS Muse**: điều khiển Muse bằng automation có thể vi phạm điều khoản dịch vụ.
3. **Một tài khoản chung**: hết hạn mức là mọi seller dừng.
4. **Phụ thuộc UI Muse**: Muse đổi giao diện là adapter gãy; `adapter-health.js` báo đúng mảnh gãy.
5. **Chrome trên server**: cần `google-chrome` + `ffmpeg`; login Muse lần đầu phải làm tay (có UI).

## 6. Kiểm thử

- `tests/test_video_prompt.py`: bỏ mốc thời gian, luôn có 10 giây, chặn >3 ảnh, prompt rỗng.
- Sidecar: `node --test` cho phần làm sạch prompt; test thật với Muse là thủ công.
- E2E thủ công: đăng nhập Muse → tạo job 3 ảnh → nhận mp4 ≥ 2s → gắn vào tin → hiện trên trang sản phẩm.

## 7. Ước lượng

2–3 ngày người.
