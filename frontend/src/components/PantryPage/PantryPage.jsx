import React, { useState } from 'react';
import usePantryItems from '../../hooks/usePantryItems';
import PantryToolbar from '../PantryToolbar/PantryToolbar';
import PantryTable from '../PantryTable/PantryTable';
import PantrySummaryCards from '../PantrySummaryCards/PantrySummaryCards';
import PantryModal from '../PantryModal/PantryModal';
import './PantryPage.css';

export default function PantryPage() {
    const {
        items,
        loading,
        page,
        pageSize,
        total,
        totalPages,
        search,
        category,
        sortBy,
        sortOrder,
        expiringCount,
        lowStockCount,
        setPage,
        setPageSize,
        handleSearchChange,
        handleCategoryChange,
        handleSortChange,
        addItem,
        editItem,
        removeItem,
    } = usePantryItems();

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingItem, setEditingItem] = useState(null);

    const handleAddClick = () => {
        setEditingItem(null);
        setIsModalOpen(true);
    };

    const handleEditClick = (item) => {
        setEditingItem(item);
        setIsModalOpen(true);
    };

    const handleDeleteClick = (item) => {
        if (window.confirm(`Are you sure you want to delete ${item.name}? This action cannot be undone.`)) {
            removeItem(item.id || item._id, item.name);
        }
    };

    const handleModalSubmit = async (formData) => {
        try {
            if (editingItem) {
                await editItem(editingItem.id || editingItem._id, formData);
            } else {
                await addItem(formData);
            }
            setIsModalOpen(false);
            setEditingItem(null);
        } catch (error) {
            console.error("Failed to save item:", error);
        }
    };

    return (
        <div className="pantry-page">
            <header className="pantry-header">
                <div>
                    <h1 className="page-title">Pantry Inventory</h1>
                    <p className="page-subtitle">Track and manage your kitchen essentials efficiently.</p>
                </div>
                <div className="header-decoration">
                    <span className="floating-emoji">🥦</span>
                    <span className="floating-emoji delay-1">🥩</span>
                    <span className="floating-emoji delay-2">🥕</span>
                </div>
            </header>

            <div className="pantry-content-card">
                <PantryToolbar
                    search={search}
                    onSearchChange={handleSearchChange}
                    category={category}
                    onCategoryChange={handleCategoryChange}
                    onAddClick={handleAddClick}
                />

                <PantryTable
                    items={items}
                    loading={loading}
                    sortBy={sortBy}
                    sortOrder={sortOrder}
                    onSort={handleSortChange}
                    onEdit={handleEditClick}
                    onDelete={handleDeleteClick}
                />

                {!loading && items.length > 0 && (
                    <div className="pagination-bar">
                        <span className="pagination-info">
                            Showing {items.length} of {total} items
                        </span>
                        <div className="pagination-controls">
                            <button
                                className="page-btn"
                                disabled={page === 1}
                                onClick={() => setPage(p => p - 1)}
                            >
                                Previous
                            </button>
                            <span className="page-number">Page {page} of {totalPages}</span>
                            <button
                                className="page-btn"
                                disabled={page === totalPages || totalPages === 0}
                                onClick={() => setPage(p => p + 1)}
                            >
                                Next
                            </button>
                        </div>
                    </div>
                )}
            </div>

            <PantrySummaryCards
                expiringCount={expiringCount}
                lowStockCount={lowStockCount}
                totalCount={total}
            />

            <PantryModal
                isOpen={isModalOpen}
                onClose={() => {
                    setIsModalOpen(false);
                    setEditingItem(null);
                }}
                onSubmit={handleModalSubmit}
                initialData={editingItem}
            />
        </div>
    );
}
