import React, { useState } from 'react';
import { Toaster } from 'react-hot-toast';
import PantryPage from './components/PantryPage/PantryPage';
import MealPlannerPage from './components/MealPlannerPage/MealPlannerPage';
import './index.css';

const NAV_ITEMS = [
  { id: 'pantry', label: '🧺 Pantry', component: PantryPage },
  { id: 'planner', label: '🍳 Meal Planner', component: MealPlannerPage },
];

function App() {
  const [activePage, setActivePage] = useState('pantry');
  const ActiveComponent = NAV_ITEMS.find(n => n.id === activePage)?.component ?? PantryPage;

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

      {/* ── Top navigation ─────────────────── */}
      <nav className="app-nav">
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            id={`nav-${item.id}`}
            className={`app-nav-btn ${activePage === item.id ? 'app-nav-btn--active' : ''}`}
            onClick={() => setActivePage(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <ActiveComponent />
    </>
  );
}

export default App;
