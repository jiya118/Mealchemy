import React from 'react';
import { Toaster } from 'react-hot-toast';
import PantryPage from './components/PantryPage/PantryPage';
import './index.css';

function App() {
  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            border: '2px solid var(--border-color)',
            fontFamily: 'var(--font-body)',
            fontWeight: 600,
            borderRadius: 'var(--border-radius-lg)',
            boxShadow: 'var(--shadow-md)',
          },
          success: {
            iconTheme: {
              primary: 'var(--color-success)',
              secondary: 'white',
            },
          },
        }}
      />
      <PantryPage />
    </>
  );
}

export default App;
