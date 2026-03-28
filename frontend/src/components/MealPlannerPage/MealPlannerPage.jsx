import React, { useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import {
    generateMealPlan,
    generateSingleMeal,
    completeMeal,
    regenerateDay,
    deleteMealPlan,
} from '../../services/mealPlannerService';
import './MealPlannerPage.css';

const DIET_OPTIONS = [
    { value: 'standard', label: '🍽️ Standard', desc: 'Everything goes' },
    { value: 'vegetarian', label: '🥗 Vegetarian', desc: 'No meat or fish' },
    { value: 'vegan', label: '🌱 Vegan', desc: 'Plant-based only' },
    { value: 'eggetarian', label: '🥚 Eggetarian', desc: 'Eggs & dairy ok' },
    { value: 'pescatarian', label: '🐟 Pescatarian', desc: 'Fish allowed' },
    { value: 'keto', label: '🥑 Keto', desc: 'Low carb, high fat' },
    { value: 'gluten_free', label: '🌾 Gluten Free', desc: 'No wheat or barley' },
    { value: 'dairy_free', label: '🥛 Dairy Free', desc: 'No milk products' },
];

const DAY_EMOJIS = {
    monday: '🌙', tuesday: '🔥', wednesday: '💧', thursday: '⚡',
    friday: '🌟', saturday: '🎉', sunday: '☀️',
};

export default function MealPlannerPage() {
    // ── Config state ──────────────────────────────────────────────────
    const [days, setDays] = useState(7);
    const [dietType, setDietType] = useState('standard');
    const [servings, setServings] = useState(2);

    // ── Result state ──────────────────────────────────────────────────
    const [plan, setPlan] = useState(null);
    const [planId, setPlanId] = useState(null);
    const [completedMeals, setCompletedMeals] = useState(new Set());
    const [regenLoading, setRegenLoading] = useState(null);

    // ── UI state ──────────────────────────────────────────────────────
    const [loading, setLoading] = useState(false);
    const [loadingMsg, setLoadingMsg] = useState('');
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('plan'); // 'plan' | 'shopping'

    // ── Helpers ───────────────────────────────────────────────────────
    const resetResult = () => {
        setPlan(null);
        setPlanId(null);
        setCompletedMeals(new Set());
        setError(null);
    };

    // ── Generate weekly plan ──────────────────────────────────────────
    const handleGenerate = useCallback(async () => {
        resetResult();
        setLoading(true);
        setLoadingMsg('🧠 Asking our AI chef to plan your week…');
        setActiveTab('plan');

        try {
            const result = await generateMealPlan({ days, diet_type: dietType, servings });

            if (result.status === 'error') {
                setError(result.error || 'Generation failed');
                toast.error(`😕 ${result.error}`);
                return;
            }

            setPlan(result);
            setPlanId(result.plan_id);
            toast.success(`🎉 ${result.days_generated}-day plan ready!`);
        } catch (err) {
            const msg = err.message || 'Something went wrong';
            setError(msg);
            toast.error(`❌ ${msg}`);
        } finally {
            setLoading(false);
            setLoadingMsg('');
        }
    }, [days, dietType, servings]);

    // ── Regenerate a single day ───────────────────────────────────────
    const handleRegenDay = useCallback(async (day) => {
        if (!planId) return;
        setRegenLoading(day);
        try {
            const result = await regenerateDay(planId, day);
            if (result.status === 'success' && result.plan) {
                // Update just this day in stored plan
                setPlan(prev => ({
                    ...prev,
                    meal_plan: {
                        ...prev.meal_plan,
                        [day]: result.new_recipe,
                    },
                }));
                toast.success(`✨ ${day.charAt(0).toUpperCase() + day.slice(1)} updated to "${result.new_recipe}"`);
            } else {
                toast.error('Could not regenerate — please try again');
            }
        } catch (err) {
            toast.error(`❌ ${err.message || 'Regeneration failed'}`);
        } finally {
            setRegenLoading(null);
        }
    }, [planId]);

    // ── Complete a meal ───────────────────────────────────────────────
    const handleComplete = useCallback(async (day) => {
        if (!planId) return;
        try {
            await completeMeal(planId, day, 'dinner');
            setCompletedMeals(prev => new Set([...prev, day]));
            toast.success(`✅ Pantry updated for ${day.charAt(0).toUpperCase() + day.slice(1)}!`);
        } catch (err) {
            toast.error(`❌ ${err.message || 'Could not mark as complete'}`);
        }
    }, [planId]);

    // ── Delete plan ───────────────────────────────────────────────────
    const handleDelete = useCallback(async () => {
        if (!planId || !window.confirm('Delete this meal plan?')) return;
        try {
            await deleteMealPlan(planId);
            resetResult();
            toast.success('🗑️ Meal plan deleted');
        } catch (err) {
            toast.error(`❌ ${err.message || 'Delete failed'}`);
        }
    }, [planId]);

    // ── Derived data ──────────────────────────────────────────────────
    const mealEntries = plan?.meal_plan ? Object.entries(plan.meal_plan) : [];
    const shoppingList = plan?.shopping_list || [];
    const pantryWarnings = plan?.pantry_summary?.expiring_soon || [];

    // ═══════════════════════════════════════════════════════════════════
    // RENDER
    // ═══════════════════════════════════════════════════════════════════
    return (
        <div className="mp-page">

            {/* ── Header ─────────────────────────────────────────────── */}
            <header className="pantry-header">
                <div>
                    <h1 className="page-title">Meal Planner</h1>
                    <p className="page-subtitle">Let AI craft your perfect weekly menu ✨</p>
                </div>
                <div className="header-decoration">
                    <span className="floating-emoji">🍳</span>
                    <span className="floating-emoji delay-1">🥘</span>
                    <span className="floating-emoji delay-2">🌿</span>
                </div>
            </header>

            {/* ── Config Card ─────────────────────────────────────────── */}
            <div className="pantry-content-card mp-config-card">
                <div className="mp-config-title">
                    <span>⚙️</span>
                    <span>Customise your plan</span>
                </div>

                <div className="mp-config-grid">
                    {/* Days */}
                    <div className="mp-field">
                        <label className="mp-label">🗓️ Days to plan</label>
                        <div className="mp-day-btns">
                            {[3, 5, 7, 10, 14].map(d => (
                                <button
                                    key={d}
                                    className={`mp-day-btn ${days === d ? 'mp-day-btn--active' : ''}`}
                                    onClick={() => setDays(d)}
                                >
                                    {d}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Servings */}
                    <div className="mp-field">
                        <label className="mp-label">🍽️ Servings</label>
                        <div className="mp-stepper">
                            <button
                                className="mp-step-btn"
                                onClick={() => setServings(s => Math.max(1, s - 1))}
                                disabled={servings <= 1}
                            >−</button>
                            <span className="mp-step-val">{servings}</span>
                            <button
                                className="mp-step-btn"
                                onClick={() => setServings(s => Math.min(8, s + 1))}
                                disabled={servings >= 8}
                            >+</button>
                        </div>
                    </div>
                </div>

                {/* Diet selector */}
                <div className="mp-field">
                    <label className="mp-label">🥑 Dietary preference</label>
                    <div className="mp-diet-grid">
                        {DIET_OPTIONS.map(opt => (
                            <button
                                key={opt.value}
                                className={`mp-diet-btn ${dietType === opt.value ? 'mp-diet-btn--active' : ''}`}
                                onClick={() => setDietType(opt.value)}
                                title={opt.desc}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Generate button */}
                <button
                    className="mp-generate-btn"
                    onClick={handleGenerate}
                    disabled={loading}
                    id="generate-plan-btn"
                >
                    {loading ? (
                        <>
                            <span className="mp-spinner" />
                            <span>{loadingMsg || 'Generating…'}</span>
                        </>
                    ) : (
                        <>✨ Generate {days}-Day Plan</>
                    )}
                </button>

                {loading && (
                    <p className="mp-loading-hint">
                        This may take ~{Math.ceil(days * 2.5)}–{days * 3}s as the AI crafts each recipe 🍳
                    </p>
                )}
            </div>

            {/* ── Error ───────────────────────────────────────────────── */}
            {error && (
                <div className="mp-error-card">
                    <span>😟</span>
                    <div>
                        <strong>Oops!</strong> {error}
                        <br />
                        <small>Make sure your pantry has some items first.</small>
                    </div>
                </div>
            )}

            {/* ── Expiry Warnings ─────────────────────────────────────── */}
            {plan && pantryWarnings.length > 0 && (
                <div className="mp-warning-banner">
                    <span>⚠️</span>
                    <span>
                        <strong>Use soon!</strong>{' '}
                        {pantryWarnings.map(w => `${w.name} (${w.days_until_expiry}d)`).join(' · ')}
                    </span>
                </div>
            )}

            {/* ── Result Panel ─────────────────────────────────────────── */}
            {plan && (
                <div className="pantry-content-card mp-result-card">

                    {/* Tabs */}
                    <div className="mp-tabs">
                        <button
                            className={`mp-tab ${activeTab === 'plan' ? 'mp-tab--active' : ''}`}
                            onClick={() => setActiveTab('plan')}
                        >
                            📅 Meal Plan
                            <span className="mp-tab-badge">{mealEntries.length}</span>
                        </button>
                        <button
                            className={`mp-tab ${activeTab === 'shopping' ? 'mp-tab--active' : ''}`}
                            onClick={() => setActiveTab('shopping')}
                        >
                            🛒 Shopping List
                            {shoppingList.length > 0 && (
                                <span className="mp-tab-badge mp-tab-badge--accent">{shoppingList.length}</span>
                            )}
                        </button>

                        <div className="mp-tabs-spacer" />

                        {/* Delete */}
                        <button className="mp-delete-btn" onClick={handleDelete} title="Delete plan">
                            🗑️ Delete
                        </button>
                    </div>

                    {/* ── Plan Tab ──────────────────────────────────────── */}
                    {activeTab === 'plan' && (
                        <div className="mp-day-list">
                            {mealEntries.map(([day, recipe], idx) => {
                                const isDone = completedMeals.has(day);
                                const isRegen = regenLoading === day;
                                return (
                                    <div
                                        key={day}
                                        className={`mp-day-card ${isDone ? 'mp-day-card--done' : ''}`}
                                        style={{ animationDelay: `${idx * 60}ms` }}
                                    >
                                        <div className="mp-day-left">
                                            <span className="mp-day-emoji">
                                                {isDone ? '✅' : DAY_EMOJIS[day] || '🍽️'}
                                            </span>
                                            <div>
                                                <div className="mp-day-name">{day.charAt(0).toUpperCase() + day.slice(1)}</div>
                                                <div className="mp-recipe-name">{recipe}</div>
                                            </div>
                                        </div>
                                        <div className="mp-day-actions">
                                            {!isDone && (
                                                <>
                                                    <button
                                                        className="mp-action-btn mp-regen-btn"
                                                        onClick={() => handleRegenDay(day)}
                                                        disabled={!!regenLoading}
                                                        title="Suggest a different recipe"
                                                    >
                                                        {isRegen ? <span className="mp-spinner mp-spinner--sm" /> : '🔄'}
                                                    </button>
                                                    <button
                                                        className="mp-action-btn mp-done-btn"
                                                        onClick={() => handleComplete(day)}
                                                        title="Mark as cooked — deducts from pantry"
                                                    >
                                                        ✓ Cooked!
                                                    </button>
                                                </>
                                            )}
                                            {isDone && (
                                                <span className="mp-done-badge">Pantry updated</span>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* ── Shopping Tab ──────────────────────────────────── */}
                    {activeTab === 'shopping' && (
                        <div className="mp-shopping-panel">
                            {shoppingList.length === 0 ? (
                                <div className="mp-empty-shopping">
                                    <span className="mp-empty-icon">🎉</span>
                                    <p>Your pantry has everything you need!</p>
                                    <small>No shopping required for this plan.</small>
                                </div>
                            ) : (
                                <>
                                    <p className="mp-shopping-hint">
                                        🛒 {shoppingList.length} item{shoppingList.length !== 1 ? 's' : ''} to grab from the store
                                    </p>
                                    <ul className="mp-shopping-list">
                                        {shoppingList.map((item, i) => (
                                            <li key={i} className="mp-shopping-item">
                                                <span className="mp-shopping-bullet">•</span>
                                                <span>{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* ── Summary Cards ────────────────────────────────────────── */}
            {plan && (
                <div className="mp-summary-row">
                    <div className="mp-summary-card">
                        <div className="mp-summary-icon">📅</div>
                        <div className="mp-summary-val">{plan.days_generated}</div>
                        <div className="mp-summary-label">Days planned</div>
                    </div>
                    <div className="mp-summary-card">
                        <div className="mp-summary-icon">🛒</div>
                        <div className="mp-summary-val">{shoppingList.length}</div>
                        <div className="mp-summary-label">Items to buy</div>
                    </div>
                    <div className="mp-summary-card">
                        <div className="mp-summary-icon">✅</div>
                        <div className="mp-summary-val">{completedMeals.size}</div>
                        <div className="mp-summary-label">Meals cooked</div>
                    </div>
                    <div className="mp-summary-card">
                        <div className="mp-summary-icon">🧺</div>
                        <div className="mp-summary-val">{plan.pantry_summary?.total_items ?? '—'}</div>
                        <div className="mp-summary-label">Pantry items</div>
                    </div>
                </div>
            )}
        </div>
    );
}
