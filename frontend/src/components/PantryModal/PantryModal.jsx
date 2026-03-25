import React, { useState, useEffect } from 'react';
import { CATEGORIES, UNITS } from '../../constants/pantryConstants';
import './PantryModal.css';

export default function PantryModal({ isOpen, onClose, onSubmit, initialData }) {
    const isEdit = !!initialData;

    const [formData, setFormData] = useState({
        name: '',
        category: 'Grains & Cereals',
        quantity: 1,
        unit: 'pieces',
        expiry_date: '',
    });

    useEffect(() => {
        if (isOpen && initialData) {
            setFormData({
                name: initialData.name || '',
                category: initialData.category || 'Grains & Cereals',
                quantity: initialData.quantity || 1,
                unit: initialData.unit || 'pieces',
                expiry_date: initialData.expiry_date
                    ? new Date(initialData.expiry_date).toISOString().split('T')[0]
                    : '',
            });
        } else if (isOpen && !initialData) {
            setFormData({
                name: '',
                category: 'Grains & Cereals',
                quantity: 1,
                unit: 'pieces',
                expiry_date: '',
            });
        }
    }, [isOpen, initialData]);

    if (!isOpen) return null;

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData((prev) => ({
            ...prev,
            [name]: name === 'quantity' ? Number(value) : value,
        }));
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const dataToSubmit = { ...formData };
        if (!dataToSubmit.expiry_date) {
            dataToSubmit.expiry_date = null;
        }
        onSubmit(dataToSubmit);
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal-content bounce-in" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2>{isEdit ? '✨ Edit Potion (Item)' : '✨ Add New Potion (Item)'}</h2>
                    <button className="close-btn" onClick={onClose}>✖</button>
                </div>
                <form onSubmit={handleSubmit} className="modal-form">
                    <div className="form-group">
                        <label>Item Name</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name}
                            onChange={handleChange}
                            placeholder="e.g. Magic Beans"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Category</label>
                        <select name="category" value={formData.category} onChange={handleChange}>
                            {CATEGORIES.map(cat => (
                                <option key={cat.value} value={cat.value}>{cat.emoji} {cat.label}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-row">
                        <div className="form-group half">
                            <label>Quantity</label>
                            <input
                                type="number"
                                name="quantity"
                                min="0"
                                step="any"
                                value={formData.quantity}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group half">
                            <label>Unit</label>
                            <select name="unit" value={formData.unit} onChange={handleChange}>
                                {UNITS.map(u => (
                                    <option key={u.value} value={u.value}>{u.label}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Expiry Date</label>
                        <input
                            type="date"
                            name="expiry_date"
                            value={formData.expiry_date}
                            onChange={handleChange}
                        />
                    </div>

                    <div className="modal-footer">
                        <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-save">
                            {isEdit ? 'Save Changes' : 'Add to Pantry'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
