import { Link } from 'react-router-dom';
import { useCategories } from '../categories';
import { useSession } from '../session';
import { Icon } from '../ui';

export function Footer() {
  const categories = useCategories();
  const { user, hasRole } = useSession();

  return (
    <footer id="site-footer">
      <div className="foot-main">
        <div>
          <Link className="logo" to="/">
            <span className="brand-mark">
              <Icon name="cycle" />
            </span>
            <span>
              <span className="g">nola</span>2hand
            </span>
          </Link>
          <p>
            Một món đồ còn tốt.
            <br />
            Một lựa chọn đáng giá.
          </p>
          <span className="footer-note">Mua bán đồ đã qua sử dụng cùng Nola2Hand.</span>
        </div>
        <div>
          <h4>Khám phá</h4>
          {categories.slice(0, 4).map((category) => (
            <Link key={category.id} to={'/category/' + encodeURIComponent(category.slug)}>
              {category.name}
            </Link>
          ))}
          <Link to="/shops">Các gian hàng</Link>
        </div>
        <div>
          <h4>Mua sắm cùng Nola</h4>
          <Link to="/favorites">Tin đã lưu</Link>
          <Link to="/compare">So sánh sản phẩm</Link>
          <Link to="/saved-searches">Theo dõi tìm kiếm</Link>
          <Link to="/assistant">Trợ lý tìm đồ</Link>
          <Link to="/returns">Trả hàng và hoàn tiền</Link>
        </div>
        <div>
          <h4>Tài khoản của bạn</h4>
          {user ? (
            <>
              <Link to="/profile">Hồ sơ cá nhân</Link>
              <Link to="/orders">Đơn mua</Link>
              <Link to="/wallet">Ví SafePay</Link>
              <Link to="/chat">Tin nhắn</Link>
            </>
          ) : (
            <>
              <Link to="/login">Đăng nhập</Link>
              <Link to="/register">Tạo tài khoản</Link>
            </>
          )}
          <Link to="/seller">Kênh người bán</Link>
          {hasRole('ADMIN_FINANCE', 'ADMIN_CONTENT') && <Link to="/admin">Trang quản trị</Link>}
        </div>
      </div>
      <div className="foot-copy">
        <span>© 2026 Nola2Hand</span>
        <span>Trao cơ hội mới cho những món đồ còn tốt.</span>
      </div>
    </footer>
  );
}
