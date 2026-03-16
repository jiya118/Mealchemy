import React from 'react';
import { CATEGORIES } from '../../constants/pantryConstants';
import './PantryToolbar.css';

export default function PantryToolbar({
    search,
    onSearchChange,
    category,
    onCategoryChange,
    onAddClick,
}) {
    return (
        <div className="pantry-toolbar">
            {/* Search Input */}
            <div className="search-wrapper">
                <span className="search-icon">🔍</span>
                <input
                    type="text"
                    className="search-input"
                    placeholder="Search by item name..."
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                />
            </div>

            {/* Category Filter */}
            <div className="toolbar-select-wrapper">
                <select
                    className="toolbar-select"
                    value={category}
                    onChange={(e) => onCategoryChange(e.target.value)}
                >
                    <option value="">All Categories</option>
                    {CATEGORIES.map((cat) => (
                        <option key={cat.value} value={cat.value}>
                            {cat.emoji} {cat.label}
                        </option>
                    ))}
                </select>
                <span className="select-chevron">▼</span>
            </div>

            {/* Add Button */}
            <button className="add-item-btn" onClick={onAddClick}>
                <span className="btn-icon">✚</span>
                Add New Item
            </button>
        </div>
    );
}
