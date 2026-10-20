export const ORDER_ST = {
  PENDING_DEPOSIT: ['Chờ đặt cọc', 'p-warn'],
  DEPOSITED: ['Đã cọc', 'p-info'],
  CONFIRMED: ['Đã xác nhận', 'p-info'],
  SHIPPING: ['Đang giao', 'p-info'],
  DELIVERED: ['Đã giao', 'p-ok'],
  COMPLETED: ['Hoàn tất', 'p-ok'],
  CANCELLED: ['Đã huỷ', 'p-mut'],
  DISPUTED: ['Tranh chấp', 'p-bad'],
  REFUNDED: ['Đã hoàn tiền', 'p-mut'],
};

export const ROLE_NAMES = {
  BUYER: 'Người mua',
  SELLER: 'Người bán',
  ADMIN_FINANCE: 'Admin tài chính',
  ADMIN_CONTENT: 'Admin nội dung',
};

export const USER_STATUS_NAMES = {
  ACTIVE: 'Đang hoạt động',
  BANNED: 'Đã khóa',
  PENDING_VERIFICATION: 'Chờ xác minh',
};

export const OFFER_ST = {
  PENDING: ['Chờ phản hồi', 'p-warn'],
  ACCEPTED: ['Đã đồng ý', 'p-ok'],
  REJECTED: ['Từ chối', 'p-bad'],
  CANCELLED: ['Đã hủy', 'p-mut'],
  EXPIRED: ['Hết hạn', 'p-mut'],
};

export const LISTING_STATUS_NAMES = {
  DRAFT: 'Nháp',
  PENDING_REVIEW: 'Chờ duyệt',
  ACTIVE: 'Đang bán',
  RESERVED: 'Đang giữ',
  HIDDEN: 'Đang ẩn',
  SOLD_OUT: 'Đã bán',
  REJECTED: 'Bị từ chối',
  DELETED: 'Đã xóa',
};

export const ESCROW_STATUS_NAMES = {
  HELD: 'Đang giữ hộ',
  RELEASED: 'Đã giải ngân',
  REFUNDED: 'Đã hoàn',
  CANCELLED: 'Đã hủy',
};

export const TXN_TYPE_NAMES = {
  TOPUP: 'Nạp tiền',
  WITHDRAW: 'Rút tiền',
  ORDER_INCOME: 'Thu bán hàng',
  ORDER_PAYMENT: 'Thanh toán đơn',
  PLATFORM_FEE: 'Phí sàn',
  REFUND: 'Hoàn tiền',
  ADJUSTMENT: 'Điều chỉnh',
};

export const DISPUTE_STATUS_NAMES = {
  OPEN: 'Mới mở',
  REVIEWING: 'Đang xem xét',
  REFUNDED: 'Đã hoàn tiền',
  REJECTED: 'Đã bác',
  CLOSED: 'Đã đóng',
};

export const DISPUTE_DECISIONS = {
  BUYER_WINS: 'Người mua thắng',
  SELLER_WINS: 'Người bán thắng',
  SPLIT: 'Chia đôi',
  REJECT: 'Bác khiếu nại',
};

export const REPORT_STATUS_NAMES = {
  NEW: 'Mới',
  REVIEWING: 'Đang xem xét',
  RESOLVED: 'Đã xử lý',
  DISMISSED: 'Bỏ qua',
};

export const AUDIT_ACTIONS = {
  RETURN_APPROVE: 'Duyệt trả hàng',
  RETURN_REJECT: 'Từ chối trả hàng',
  RETURN_CANCEL: 'Hủy trả hàng',
  RETURN_SHIP: 'Buyer gửi trả',
  RETURN_RECEIVE: 'Đã nhận hàng trả',
  RETURN_REFUND: 'Hoàn tiền trả hàng',
  RETURN_COD_REFUND: 'Ghi nhận hoàn COD',
  RETURN_COD_CONFIRM: 'Buyer xác nhận COD',
  CREATE_FEE: 'Tạo phí',
  UPDATE_FEE: 'Sửa phí',
  DELETE_FEE: 'Xóa phí',
  LOCK_USER: 'Khóa tài khoản',
  UNLOCK_USER: 'Mở khóa',
  VERIFY_USER: 'Duyệt xác minh',
  SET_ROLES: 'Đổi vai trò',
  MODERATE_LISTING: 'Duyệt tin',
  RESOLVE_DISPUTE: 'Xử lý tranh chấp',
  WITHDRAW_APPROVE: 'Duyệt rút tiền',
  WITHDRAW_PAY: 'Đã chuyển khoản',
  WITHDRAW_REJECT: 'Từ chối rút tiền',
  WITHDRAW_FAIL: 'Chuyển thất bại',
};

export const FEE_KIND_NAMES = {
  PLATFORM_TXN: 'Phí giao dịch',
  WITHDRAW: 'Phí rút tiền',
  PENALTY: 'Phí phạt',
};

export const PROMO_STATUS_NAMES = {
  DRAFT: 'Nháp',
  ACTIVE: 'Đang chạy',
  PAUSED: 'Tạm dừng',
  ENDED: 'Kết thúc',
};

export const CONDITION_NAMES = {
  NEW: 'Mới, chưa sử dụng',
  LIKE_NEW: 'Như mới',
  USED_GOOD: 'Đã dùng, còn tốt',
  USED_FAIR: 'Đã dùng, có hao mòn',
  FOR_PARTS: 'Dùng làm linh kiện',
};

export const DELIVERY_NAMES = {
  ANY: 'Giao hàng hoặc gặp trực tiếp',
  MEETUP: 'Gặp trực tiếp',
  DELIVERY: 'Giao hàng',
};

export const WORKFLOW_LABELS = {
  PENDING: 'Chờ duyệt',
  APPROVED: 'Đã duyệt',
  PAID: 'Đã chuyển khoản',
  REJECTED: 'Từ chối',
  FAILED: 'Chuyển thất bại',
  CANCELLED: 'Đã hủy',
  REQUESTED: 'Yêu cầu trả hàng',
  SHIPPED: 'Đã gửi trả',
  RECEIVED: 'Đã nhận hàng trả',
  REFUNDED: 'Đã hoàn tiền',
};

export const CATEGORY_DESIGNS = {
  'dien-tu-cu': {
    theme: 'tech',
    title: 'Công nghệ hay. Giá vừa tay.',
    description:
      'Khám phá điện thoại, laptop và thiết bị công nghệ đã qua sử dụng. So sánh tình trạng, chọn đúng món bạn cần.',
    topics: ['Điện thoại', 'Laptop', 'Tai nghe', 'Bàn phím'],
  },
  'noi-that': {
    theme: 'living',
    title: 'Thêm chất riêng cho tổ ấm.',
    description:
      'Bàn ghế, sofa và đồ nội thất có cơ hội về nhà mới. Làm mới không gian với những lựa chọn tiết kiệm hơn.',
    topics: ['Sofa', 'Bàn', 'Ghế', 'Tủ'],
  },
  'do-gia-dung': {
    theme: 'kitchen',
    title: 'Đồ hữu ích. Nhà thêm tiện.',
    description:
      'Tìm đồ dùng nhà bếp và thiết bị gia đình phù hợp với nhu cầu hằng ngày, từ người bán trên Nola2Hand.',
    topics: ['Bếp', 'Nồi', 'Quạt', 'Máy giặt'],
  },
  'thoi-trang-2hand': {
    theme: 'living',
    title: 'Phong cách mới, lựa chọn bền vững.',
    description:
      'Khám phá quần áo, giày dép và phụ kiện 2Hand để làm mới phong cách của bạn.',
    topics: ['Áo', 'Quần', 'Giày', 'Túi'],
  },
  'xe-co': {
    theme: 'tech',
    title: 'Tìm người bạn đồng hành mới.',
    description:
      'Khám phá xe đã qua sử dụng. Trao đổi với người bán để kiểm tra giấy tờ và tình trạng trước khi giao dịch.',
    topics: ['Xe máy', 'Xe đạp', 'Ô tô'],
  },
  'cho-tang-0d': {
    theme: 'kitchen',
    title: 'Bạn không dùng, ai đó đang cần.',
    description:
      'Trao đi món đồ còn tốt, nối dài vòng đời sử dụng và cùng giảm lãng phí.',
    topics: [],
  },
};

export const lbl = (map, value) => (value != null && map[value]) || value || '—';
