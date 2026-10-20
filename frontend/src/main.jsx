import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App';
import { SessionProvider } from './session';
import { CategoriesProvider } from './categories';
import { ModalProvider, ToastProvider } from './ui';
import './styles.css';
import './design.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <HashRouter>
      <SessionProvider>
        <CategoriesProvider>
          <ToastProvider>
            <ModalProvider>
              <App />
            </ModalProvider>
          </ToastProvider>
        </CategoriesProvider>
      </SessionProvider>
    </HashRouter>
  </StrictMode>,
);
