import { useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { CatNav, Header, MobileNav, Topbar } from './components/Header';
import { Footer } from './components/Footer';
import { clearComparison, useComparison } from './compare';

function CompareTray() {
  const ids = useComparison();
  return (
    <aside id="comparison-tray" hidden={!ids.length}>
      <span>So sánh: {ids.length}/3 sản phẩm</span>
      <Link className="btn btn-green btn-sm" to={'/compare?ids=' + ids.join(',')}>
        Mở so sánh
      </Link>
      <button className="btn btn-line btn-sm" onClick={clearComparison}>
        Xóa chọn
      </button>
    </aside>
  );
}

export default function Layout() {
  const location = useLocation();
  const isAdmin = location.pathname.startsWith('/admin');

  useEffect(() => {
    document.body.classList.toggle('admin-mode', isAdmin);
    const page = location.pathname.split('/')[1] || 'home';
    document.body.dataset.page = page;
    if (!isAdmin) document.title = 'Nola2Hand — Sàn đồ cũ';
  }, [location.pathname, isAdmin]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  if (isAdmin) {
    return (
      <main id="app">
        <Outlet />
      </main>
    );
  }

  return (
    <>
      <Topbar />
      <Header />
      <CatNav />
      <main id="app">
        <Outlet />
      </main>
      <Footer />
      <CompareTray />
      <MobileNav />
    </>
  );
}
