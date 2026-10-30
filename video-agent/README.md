# video-agent

Sidecar tạo **video quảng bá 10 giây** cho nola2hand, điều khiển [Muse](https://muse.ai) qua Google Chrome.

Backend FastAPI gọi HTTP tới `127.0.0.1:48910`; agent chạy Muse, tải `.mp4` về, kiểm bằng `ffprobe` rồi trả đường dẫn file.

## Nguồn gốc mã

`engine/{chrome,muse-page,muse-runner,verify,adapter-health}.js` chép từ dự án **HaoHao**
(`videotool/haohao-linux`, bản backup `haohao-linux-backup-2026-10-30`).

Giấy phép gốc ghi **"Proprietary – Horizon LLC"**, README gốc ghi *"chỉ nên dùng cá nhân"*.
Đây là đồ án học tập, **không phát hành thương mại**. Nếu định thương mại hoá, phải xin phép chủ bản quyền
hoặc thay engine bằng bản tự viết.

## Yêu cầu

- Node ≥ 20
- Google Chrome (`google-chrome` / `chromium`)
- `ffmpeg` + `ffprobe`

```bash
sudo apt install ffmpeg
```

## Chạy

```bash
cd video-agent
npm start
```

### Đăng nhập Muse (một lần)

Agent chạy Chrome **ẩn ngoài màn hình** và mở `about:blank`, nên đăng nhập ở cửa sổ Chrome khác
(profile khác) **không có tác dụng**. Phải đăng nhập đúng profile của agent:

```bash
node login.js          # mở cửa sổ Chrome ở profile của agent
```

Đăng nhập muse.ai trong cửa sổ đó, khi thấy `✅ Đã đăng nhập Muse` thì Ctrl+C.
Profile `video-agent/.profile/` giữ session cho các lần sau.

Kiểm tra: `node login.js --check` hoặc `curl 127.0.0.1:48910/health` → `"museLogin": true`.

## API

| Method | Path | Body | Trả |
|---|---|---|---|
| GET | `/health` | — | `{ok, chrome, museLogin, error}` |
| POST | `/jobs` | `{prompt, images:[{mimeType,dataBase64}], outputDir?}` | `{id}` |
| GET | `/jobs/:id` | — | `{id, status, error, file, step}` |
| POST | `/jobs/:id/cancel` | — | `{ok:true}` |

`status`: `queued` → `running` → `done` / `failed` / `cancelled`.

Chạy tuần tự 1 job/lần (một tài khoản Muse không hợp chạy song song).

## Giới hạn

- **Tối đa 3 ảnh** mỗi job (Muse giới hạn tổng ảnh gửi kèm 8 MB).
- **Video 10 giây**: agent không tự thêm mốc thời gian; prompt do backend làm sạch và ép 10 giây.
- **Quality gate**: video tải về phải có luồng video và dài ≥ 2 giây, nếu không job `failed`.

## Test

```bash
npm test
```

## Cảnh báo

Điều khiển Muse bằng automation có thể vi phạm điều khoản dịch vụ của Muse. Dùng cho đồ án/demo nội bộ.
