import React, { useState, useEffect } from 'react';
import { CATEGORIES, UNITS } from '../../constants/pantryConstants';
import './ScanResultsModal.css';

export default function ScanResultsModal({ isOpen, detectionResult, onSave, onClose }) {
    const [items, setItems] = useState([]);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (isOpen && detectionResult?.detected_items) {
            setItems(
                detectionResult.detected_items.map((item, idx) => ({
                    _tempId: idx,
                    name: item.name,
                    quantity: item.quantity,
                    unit: item.unit || 'pieces',
                    category: item.category || 'other',
                    confidence: item.confidence,
                    selected: true,
                }))
            );
        }
    }, [isOpen, detectionResult]);

    if (!isOpen) return null;

    /* ── Handlers ──────────────────────────────────────────────────── */
    const updateItem = (tempId, field, value) => {
        setItems((prev) =>
            prev.map((it) =>
                it._tempId === tempId
                    ? { ...it, [field]: field === 'quantity' ? Number(value) : value }
                    : it
            )
        );
    };

    const toggleItem = (tempId) => {
        setItems((prev) =>
            prev.map((it) =>
                it._tempId === tempId ? { ...it, selected: !it.selected } : it
            )
        );
    };

    const removeItem = (tempId) => {
        setItems((prev) => prev.filter((it) => it._tempId !== tempId));
    };

    const addManualItem = () => {
        setItems((prev) => [
            ...prev,
            {
                _tempId: Date.now(),
                name: '',
                quantity: 1,
                unit: 'pieces',
                category: 'other',
                confidence: null,
                selected: true,
            },
        ]);
    };

    const handleSaveAll = async () => {
        const toSave = items
            .filter((it) => it.selected && it.name.trim())
            .map(({ name, quantity, unit, category }) => ({
                name: name.trim(),
                quantity,
                unit,
                category,
            }));

        if (toSave.length === 0) return;

        setSaving(true);
        try {
            await onSave(toSave);
        } finally {
            setSaving(false);
        }
    };

    const selectedCount = items.filter((it) => it.selected && it.name.trim()).length;

    const getConfidenceBadge = (conf) => {
        if (conf === null) return null;
        const pct = Math.round(conf * 100);
        let cls = 'conf-low';
        if (pct >= 80) cls = 'conf-high';
        else if (pct >= 50) cls = 'conf-mid';
        return <span className={`confidence-badge ${cls}`}>{pct}%</span>;
    };

    return (
        <div className="results-backdrop" onClick={onClose}>
            <div className="results-panel" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="results-header">
                    <div>
                        <h2>🧾 Scan Results</h2>
                        <p className="results-subtitle">
                            {detectionResult?.total_instances || 0} items detected •
                            Review and edit before saving to your pantry
                        </p>
                    </div>
                    <button className="results-close-btn" onClick={onClose}>✖</button>
                </div>

                {/* Item list */}
                <div className="results-body">
                    {items.length === 0 ? (
                        <div className="no-items-detected">
                            <span className="no-items-icon">🔍</span>
                            <p>No grocery items were detected in the image.</p>
                            <p className="no-items-hint">
                                Try uploading a clearer photo with visible groceries.
                            </p>
                        </div>
                    ) : (
                        <div className="results-list">
                            {items.map((item) => (
                                <div
                                    key={item._tempId}
                                    className={`result-item ${!item.selected ? 'deselected' : ''}`}
                                >
                                    {/* Checkbox */}
                                    <label className="item-checkbox">
                                        <input
                                            type="checkbox"
                                            checked={item.selected}
                                            onChange={() => toggleItem(item._tempId)}
                                        />
                                        <span className="checkmark"></span>
                                    </label>

                                    {/* Fields */}
                                    <div className="item-fields">
                                        <div className="field-row">
                                            <input
                                                type="text"
                                                className="field-name"
                                                value={item.name}
                                                onChange={(e) =>
                                                    updateItem(item._tempId, 'name', e.target.value)
                                                }
                                                placeholder="Item name"
                                            />
                                            {getConfidenceBadge(item.confidence)}
                                        </div>
                                        <div className="field-row-bottom">
                                            <input
                                                type="number"
                                                className="field-qty"
                                                min="1"
                                                value={item.quantity}
                                                onChange={(e) =>
                                                    updateItem(item._tempId, 'quantity', e.target.value)
                                                }
                                            />
                                            <select
                                                className="field-unit"
                                                value={item.unit}
                                                onChange={(e) =>
                                                    updateItem(item._tempId, 'unit', e.target.value)
                                                }
                                            >
                                                {UNITS.map((u) => (
                                                    <option key={u.value} value={u.value}>
                                                        {u.label}
                                                    </option>
                                                ))}
                                            </select>
                                            <select
                                                className="field-category"
                                                value={item.category}
                                                onChange={(e) =>
                                                    updateItem(item._tempId, 'category', e.target.value)
                                                }
                                            >
                                                {CATEGORIES.map((cat) => (
                                                    <option key={cat.value} value={cat.value}>
                                                        {cat.emoji} {cat.label}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    {/* Remove */}
                                    <button
                                        className="remove-item-btn"
                                        onClick={() => removeItem(item._tempId)}
                                        title="Remove item"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Add manual item */}
                    <button className="add-manual-btn" onClick={addManualItem}>
                        ✚ Add Item Manually
                    </button>
                </div>

                {/* Footer */}
                <div className="results-footer">
                    <button className="btn-cancel-results" onClick={onClose}>
                        Cancel
                    </button>
                    <button
                        className="btn-save-all"
                        onClick={handleSaveAll}
                        disabled={selectedCount === 0 || saving}
                    >
                        {saving ? (
                            <>
                                <span className="save-spinner"></span>
                                Saving...
                            </>
                        ) : (
                            <>✅ Save {selectedCount} Item{selectedCount !== 1 ? 's' : ''} to Pantry</>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
