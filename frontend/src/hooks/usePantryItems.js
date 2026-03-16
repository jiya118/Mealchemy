/**
 * usePantryItems — custom hook encapsulating all pantry CRUD state & logic.
 *
 * Keeps components thin by owning:
 *  - fetch / pagination / search / filter / sort state
 *  - create, update, delete mutations
 *  - summary stats (expiring-soon, low-stock, total)
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import toast from 'react-hot-toast';
import {
    fetchPantryItems,
    fetchExpiringItems,
    fetchLowStockItems,
    createPantryItem,
    updatePantryItem,
    deletePantryItem,
} from '../services/pantryService';

const DEBOUNCE_MS = 400;

export default function usePantryItems() {
    /* ── List state ──────────────────────────────────────────────────── */
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    /* Pagination */
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);
    const [total, setTotal] = useState(0);
    const [totalPages, setTotalPages] = useState(1);

    /* Filters & sorting */
    const [search, setSearch] = useState('');
    const [category, setCategory] = useState('');
    const [sortBy, setSortBy] = useState('name');
    const [sortOrder, setSortOrder] = useState('asc');

    /* Summary cards */
    const [expiringCount, setExpiringCount] = useState(0);
    const [lowStockCount, setLowStockCount] = useState(0);

    /* Debounce ref for search */
    const searchTimerRef = useRef(null);

    /* ── Fetch items ─────────────────────────────────────────────────── */
    const loadItems = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const data = await fetchPantryItems({
                page,
                pageSize,
                category: category || null,
                search: search || null,
                sortBy,
                sortOrder,
            });

            setItems(data.items || []);
            setTotal(data.total);
            setTotalPages(data.total_pages);
        } catch (err) {
            setError(err.message);
            toast.error(err.message || 'Failed to load pantry items');
        } finally {
            setLoading(false);
        }
    }, [page, pageSize, category, search, sortBy, sortOrder]);

    /* ── Fetch summary stats ─────────────────────────────────────────── */
    const loadSummary = useCallback(async () => {
        try {
            const [expiring, lowStock] = await Promise.all([
                fetchExpiringItems(7),
                fetchLowStockItems(2),
            ]);
            setExpiringCount(expiring.length);
            setLowStockCount(lowStock.length);
        } catch {
            /* Non-critical — silently fail */
        }
    }, []);

    /* ── Effects ─────────────────────────────────────────────────────── */
    useEffect(() => {
        loadItems();
    }, [loadItems]);

    useEffect(() => {
        loadSummary();
    }, [loadSummary]);

    /* ── Debounced search setter ─────────────────────────────────────── */
    const handleSearchChange = useCallback((value) => {
        if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
        searchTimerRef.current = setTimeout(() => {
            setSearch(value);
            setPage(1); // reset to first page on new search
        }, DEBOUNCE_MS);
    }, []);

    /* ── Category change resets page ─────────────────────────────────── */
    const handleCategoryChange = useCallback((value) => {
        setCategory(value);
        setPage(1);
    }, []);

    /* ── Sort handler ────────────────────────────────────────────────── */
    const handleSortChange = useCallback((field) => {
        setSortBy((prev) => {
            if (prev === field) {
                setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
                return prev;
            }
            setSortOrder('asc');
            return field;
        });
        setPage(1);
    }, []);

    /* ── CRUD mutations ──────────────────────────────────────────────── */
    const addItem = useCallback(
        async (itemData) => {
            const created = await createPantryItem(itemData);
            toast.success(`🎉 ${created.name} added to pantry!`);
            await loadItems();
            await loadSummary();
            return created;
        },
        [loadItems, loadSummary],
    );

    const editItem = useCallback(
        async (id, itemData) => {
            const updated = await updatePantryItem(id, itemData);
            toast.success(`✏️ ${updated.name} updated!`);
            await loadItems();
            await loadSummary();
            return updated;
        },
        [loadItems, loadSummary],
    );

    const removeItem = useCallback(
        async (id, name) => {
            await deletePantryItem(id);
            toast.success(`🗑️ ${name} removed from pantry`);
            /* If current page becomes empty after deletion, go back a page */
            if (items.length === 1 && page > 1) {
                setPage((p) => p - 1);
            } else {
                await loadItems();
            }
            await loadSummary();
        },
        [items.length, page, loadItems, loadSummary],
    );

    /* ── Return public API ───────────────────────────────────────────── */
    return {
        /* data */
        items,
        loading,
        error,
        total,
        totalPages,
        page,
        pageSize,
        search,
        category,
        sortBy,
        sortOrder,
        expiringCount,
        lowStockCount,

        /* actions */
        setPage,
        setPageSize: (size) => { setPageSize(size); setPage(1); },
        handleSearchChange,
        handleCategoryChange,
        handleSortChange,
        addItem,
        editItem,
        removeItem,
        refresh: loadItems,
    };
}
