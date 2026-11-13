import { useEffect, useRef, useState } from 'react';
import { api, MAX_IMAGE_BYTES, IMAGE_TYPES } from '../api';
import { ErrorState, Icon, Loading, useToast } from '../ui';

const MAX_IMAGES = 3;
const NOTICE = 'Chỉ tạo được video 10 giây. Tối đa 3 ảnh.';
const STATUS_LABEL = {
  QUEUED: 'Đang chờ',
  RUNNING: 'Muse đang dựng',
  DONE: 'Xong',
  FAILED: 'Lỗi',
  CANCELLED: 'Đã huỷ',
};

const readAsBase64 = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

export default function SellerVideo() {
  const toast = useToast();
  const [prompt, setPrompt] = useState('');
  const [images, setImages] = useState([]); // {mimeType, base64, url}
  const [listingId, setListingId] = useState('');
  const [listings, setListings] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [improved, setImproved] = useState('');
  const fileRef = useRef(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api('/seller/listings?limit=100'), api('/video-jobs')])
      .then(([listingRes, jobRes]) => {
        if (!alive) return;
        setListings(listingRes.data || []);
        setJobs(jobRes.jobs || []);
        setLoading(false);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // Poll khi còn job chưa xong
  useEffect(() => {
    const pending = jobs.some((job) => job.status === 'QUEUED' || job.status === 'RUNNING');
    if (!pending) return undefined;
    const timer = setInterval(() => {
      api('/video-jobs')
        .then((res) => setJobs(res.jobs || []))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, [jobs]);

  const addImages = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (!files.length) return;
    if (images.length + files.length > MAX_IMAGES) {
      toast(`Chỉ được chọn tối đa ${MAX_IMAGES} ảnh`, 'error');
      return;
    }
    const next = [];
    for (const file of files) {
      if (!IMAGE_TYPES.includes(file.type)) {
        toast('Chỉ nhận ảnh JPEG, PNG hoặc WebP', 'error');
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        toast('Mỗi ảnh không được vượt quá 5MB', 'error');
        continue;
      }
      next.push({ mimeType: file.type, base64: await readAsBase64(file), url: URL.createObjectURL(file) });
    }
    setImages((current) => [...current, ...next].slice(0, MAX_IMAGES));
  };

  const removeImage = (index) => {
    setImages((current) => current.filter((_, i) => i !== index));
  };

  const preview = async () => {
    if (!prompt.trim() && !listingId) {
      toast('Nhập mô tả hoặc chọn tin đăng trước', 'error');
      return;
    }
    try {
      const res = await api('/video-jobs/preview-prompt', {
        method: 'POST',
        body: { prompt, listingId: listingId ? Number(listingId) : null },
      });
      setImproved(res.finalPrompt);
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const submit = async () => {
    if (!images.length) {
      toast('Chọn ít nhất 1 ảnh sản phẩm', 'error');
      return;
    }
    if (!prompt.trim() && !listingId) {
      toast('Nhập mô tả hoặc chọn tin đăng trước', 'error');
      return;
    }
    setBusy(true);
    try {
      const res = await api('/video-jobs', {
        method: 'POST',
        body: {
          prompt,
          listingId: listingId ? Number(listingId) : null,
          images: images.map(({ mimeType, base64 }) => ({ mimeType, base64 })),
        },
      });
      setJobs((current) => [res.job, ...current]);
      setPrompt('');
      setImproved('');
      setImages([]);
      toast('Đã gửi yêu cầu tạo video');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (id) => {
    try {
      const res = await api(`/video-jobs/${id}/cancel`, { method: 'POST' });
      setJobs((current) => current.map((job) => (job.id === id ? res.job : job)));
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  // Gắn video đã dựng xong vào tin (hoặc bỏ gắn) — không phải tạo lại job 15 phút.
  const attach = async (id, value) => {
    try {
      const res = await api(`/video-jobs/${id}/attach`, {
        method: 'POST',
        body: { listingId: value ? Number(value) : null },
      });
      setJobs((current) => current.map((job) => (job.id === id ? res.job : job)));
      toast(value ? 'Đã gắn video vào tin đăng' : 'Đã bỏ gắn video');
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  return (
    <div className="video-studio">
      <section className="card video-notice" role="status">
        <Icon name="video" />
        <div>
          <strong>{NOTICE}</strong>
          <p>Muse dựng video dọc 9:16 từ ảnh sản phẩm. Video xong sẽ hiện trên tin đăng bạn chọn.</p>
        </div>
      </section>

      <section className="card">
        <h2>Tạo video mới</h2>

        <div className="form-row">
          <label className="lbl" htmlFor="video-prompt">
            Mô tả video
          </label>
          <textarea
            className="input"
            id="video-prompt"
            rows={4}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="VD: cận cảnh tai nghe trên bàn gỗ, tay nâng lên đeo thử"
          />
        </div>

        <div className="video-images">
          <span className="field-label">
            Ảnh sản phẩm ({images.length}/{MAX_IMAGES})
          </span>
          <div className="video-image-row">
            {images.map((image, index) => (
              <figure key={image.url} className="video-image">
                <img src={image.url} alt={`Ảnh ${index + 1}`} />
                <button type="button" onClick={() => removeImage(index)} aria-label="Bỏ ảnh">
                  ×
                </button>
              </figure>
            ))}
            {images.length < MAX_IMAGES && (
              <button type="button" className="video-image-add" onClick={() => fileRef.current?.click()}>
                <Icon name="plus" />
                Thêm ảnh
              </button>
            )}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept={IMAGE_TYPES.join(',')}
            multiple
            hidden
            onChange={addImages}
          />
        </div>

        <div className="form-row">
          <label className="lbl" htmlFor="video-listing">
            Gắn vào tin đăng (tuỳ chọn)
          </label>
          <select
            className="input"
            id="video-listing"
            value={listingId}
            onChange={(event) => setListingId(event.target.value)}
          >
            <option value="">Không gắn</option>
            {listings.map((listing) => (
              <option key={listing.id} value={listing.id}>
                {listing.title}
              </option>
            ))}
          </select>
        </div>

        <div className="video-actions">
          <button type="button" className="btn btn-line" onClick={preview}>
            Cải thiện prompt
          </button>
          <button type="button" className="btn btn-green" onClick={submit} disabled={busy}>
            {busy ? 'Đang gửi...' : 'Tạo video 10 giây'}
          </button>
        </div>

        {improved && (
          <div className="video-improved">
            <strong>Prompt sẽ gửi Muse</strong>
            <pre>{improved}</pre>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Video đã tạo</h2>
        {jobs.length === 0 ? (
          <p className="muted">Chưa có video nào.</p>
        ) : (
          <ul className="video-jobs">
            {jobs.map((job) => (
              <li key={job.id} className={`video-job is-${job.status.toLowerCase()}`}>
                <div className="video-job-head">
                  <strong>#{job.id}</strong>
                  <span className="pill">{STATUS_LABEL[job.status] || job.status}</span>
                  {(job.status === 'QUEUED' || job.status === 'RUNNING') && (
                    <button type="button" className="btn btn-sm btn-line" onClick={() => cancel(job.id)}>
                      Huỷ
                    </button>
                  )}
                </div>
                {job.error && <p className="video-job-error">{job.error}</p>}
                {job.status === 'DONE' && job.videoUrl && (
                  <video src={job.videoUrl} controls playsInline preload="metadata" />
                )}
                {job.status === 'DONE' && (
                  <label className="video-job-attach">
                    <span>Gắn vào tin đăng</span>
                    <select
                      className="input"
                      value={job.listingId ? String(job.listingId) : ''}
                      onChange={(event) => attach(job.id, event.target.value)}
                    >
                      <option value="">Không gắn</option>
                      {listings.map((listing) => (
                        <option key={listing.id} value={listing.id}>
                          {listing.title}
                        </option>
                      ))}
                      {job.listingId && !listings.some((item) => item.id === job.listingId) && (
                        <option value={job.listingId}>Tin #{job.listingId} (không còn trong danh sách)</option>
                      )}
                    </select>
                  </label>
                )}
                <details>
                  <summary>Prompt đã gửi</summary>
                  <pre>{job.finalPrompt}</pre>
                </details>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
