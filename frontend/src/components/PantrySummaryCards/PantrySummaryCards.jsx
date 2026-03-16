import React from 'react';
import './PantrySummaryCards.css';

export default function PantrySummaryCards({
    expiringCount,
    lowStockCount,
    totalCount,
}) {
    return (
        <div className="summary-cards">
            {/* Expiring Soon */}
            <div className="card card-warning animated-hover">
                <div className="card-header">
                    <span className="card-icon warning-icon">⚠️</span>
                    <h3 className="card-title">Expiring Soon</h3>
                </div>
                <div className="card-body">
                    <span className="card-number">{expiringCount}</span>
                    <span className="card-text">Items</span>
                </div>
                <p className="card-footer-text">Check these before they go waste.</p>
            </div>

            {/* Low Stock */}
            <div className="card card-danger animated-hover">
                <div className="card-header">
                    <span className="card-icon danger-icon">📉</span>
                    <h3 className="card-title">Low Stock</h3>
                </div>
                <div className="card-body">
                    <span className="card-number">{lowStockCount}</span>
                    <span className="card-text">Items</span>
                </div>
                <p className="card-footer-text">Consider adding these to your shopping list.</p>
            </div>

            {/* Total Items */}
            <div className="card card-success animated-hover">
                <div className="card-header">
                    <span className="card-icon success-icon">📦</span>
                    <h3 className="card-title">Total Items</h3>
                </div>
                <div className="card-body">
                    <span className="card-number">{totalCount}</span>
                    <span className="card-text">Items</span>
                </div>
                <p className="card-footer-text">Current pantry capacity at {Math.min(100, (totalCount / 50) * 100).toFixed(0)}%.</p>
            </div>
        </div>
    );
}
