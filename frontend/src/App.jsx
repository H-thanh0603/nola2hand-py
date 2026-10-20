import { Route, Routes } from 'react-router-dom';
import Layout from './Layout';
import Catalog from './pages/Catalog';
import Listing from './pages/Listing';
import Shops from './pages/Shops';
import Shop from './pages/Shop';
import Compare from './pages/Compare';
import Assistant from './pages/Assistant';
import SavedSearches from './pages/SavedSearches';
import { Forgot, Login, Register, Reset, VerifyEmail, VerifyOtp } from './pages/Auth';
import Favorites from './pages/Favorites';
import Notifications from './pages/Notifications';
import Chat from './pages/Chat';
import Profile from './pages/Profile';
import Wallet from './pages/Wallet';
import Offers from './pages/Offers';
import Orders from './pages/Orders';
import OrderDetail from './pages/OrderDetail';
import Cart from './pages/Cart';
import Returns from './pages/Returns';
import { Seller, SellerEdit } from './pages/Seller';
import Admin from './pages/Admin';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Catalog />} />
        <Route path="category/:slug" element={<Catalog />} />
        <Route path="listing/:id" element={<Listing />} />
        <Route path="compare" element={<Compare />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="shops" element={<Shops />} />
        <Route path="shop/:id" element={<Shop />} />

        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="verify-otp" element={<VerifyOtp />} />
        <Route path="verify/:token" element={<VerifyEmail />} />
        <Route path="forgot" element={<Forgot />} />
        <Route path="reset/:token" element={<Reset />} />

        <Route path="favorites" element={<Favorites />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="chat" element={<Chat />} />
        <Route path="chat/:userId" element={<Chat />} />
        <Route path="profile" element={<Profile />} />
        <Route path="wallet" element={<Wallet />} />
        <Route path="offers" element={<Offers />} />
        <Route path="orders" element={<Orders />} />
        <Route path="orders/:id" element={<OrderDetail />} />
        <Route path="cart" element={<Cart />} />
        <Route path="returns" element={<Returns />} />
        <Route path="saved-searches" element={<SavedSearches />} />

        <Route path="seller" element={<Seller />} />
        <Route path="seller/:tab" element={<Seller />} />
        <Route path="edit-listing/:id" element={<SellerEdit />} />
        <Route path="admin" element={<Admin />} />
        <Route path="admin/:tab" element={<Admin />} />
      </Route>
    </Routes>
  );
}
