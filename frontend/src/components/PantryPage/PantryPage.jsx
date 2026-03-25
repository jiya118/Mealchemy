import React, { useState } from 'react';
import toast from 'react-hot-toast';
import usePantryItems from '../../hooks/usePantryItems';
import PantryToolbar from '../PantryToolbar/PantryToolbar';
import PantryTable from '../PantryTable/PantryTable';
import PantrySummaryCards from '../PantrySummaryCards/PantrySummaryCards';
import PantryModal from '../PantryModal/PantryModal';
import GroceryScanner from '../GroceryScanner/GroceryScanner';
import ScanResultsModal from '../ScanResultsModal/ScanResultsModal';
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

    /* —— Scanner state —————————————————————————————————— */
    const [isScannerOpen, setIsScannerOpen] = useState(false);
    const [scanResult, setScanResult] = useState(null);
    const [isResultsOpen, setIsResultsOpen] = useState(false);

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

    /* —— Scanner flow —————————————————————————————————— */
    const handleScanClick = () => {
        setIsScannerOpen(true);
    };

    const handleScanComplete = (result) => {
        setIsScannerOpen(false);
        setScanResult(result);
        setIsResultsOpen(true);
    };

    const handleSaveScannedItems = async (itemsToSave) => {
        let saved = 0;
        let failed = 0;

        for (const item of itemsToSave) {
            try {
                await addItem(item);
                saved++;
            } catch (err) {
                console.error(`Failed to save "${item.name}":`, err);
                failed++;
            }
        }

        setIsResultsOpen(false);
        setScanResult(null);

        if (saved > 0) {
            toast.success(`🎉 ${saved} item${saved !== 1 ? 's' : ''} added to your pantry!`);
        }
        if (failed > 0) {
            toast.error(`⚠️ ${failed} item${failed !== 1 ? 's' : ''} failed to save.`);
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
                    onScanClick={handleScanClick}
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

            {/* —— Grocery Scanner ——————————————————————— */}
            {isScannerOpen && (
                <GroceryScanner
                    onScanComplete={handleScanComplete}
                    onClose={() => setIsScannerOpen(false)}
                />
            )}

            {/* —— Scan Results Modal ———————————————————— */}
            <ScanResultsModal
                isOpen={isResultsOpen}
                detectionResult={scanResult}
                onSave={handleSaveScannedItems}
                onClose={() => {
                    setIsResultsOpen(false);
                    setScanResult(null);
                }}
            />
        </div>
    );
}
