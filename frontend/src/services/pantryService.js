/**
 * Service layer for Pantry Items API.
 * All backend communication for pantry items is funnelled through here.
 */
import api from './api';

const ENDPOINT = '/pantry-items';

/* ── Read ──────────────────────────────────────────────────────────── */

/**
 * Fetch paginated, filterable, sortable list of pantry items.
 *
 * @param {Object}  params
 * @param {number}  params.page       – 1-indexed page number
 * @param {number}  params.pageSize   – items per page
 * @param {string}  [params.category] – filter by category value
 * @param {string}  [params.search]   – search term for name
 * @param {string}  [params.sortBy]   – field to sort by
 * @param {string}  [params.sortOrder]– 'asc' | 'desc'
 * @returns {Promise<{items, total, page, page_size, total_pages}>}
 */
export const fetchPantryItems = async ({
    page = 1,
    pageSize = 10,
    category = null,
    search = null,
    sortBy = 'name',
    sortOrder = 'asc',
} = {}) => {
    const params = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
    };
    if (category) params.category = category;
    if (search) params.search = search;

    const { data } = await api.get(ENDPOINT, { params });
    return data;
};

/**
 * Fetch a single pantry item by ID.
 */
export const fetchPantryItemById = async (id) => {
    const { data } = await api.get(`${ENDPOINT}/${id}`);
    return data;
};

/**
 * Fetch items expiring within `days`.
 */
export const fetchExpiringItems = async (days = 7, limit = 100) => {
    const { data } = await api.get(`${ENDPOINT}/expiring-soon`, {
        params: { days, limit },
    });
    return data;
};

/**
 * Fetch items at or below `threshold` quantity.
 */
export const fetchLowStockItems = async (threshold = 1, limit = 100) => {
    const { data } = await api.get(`${ENDPOINT}/low-stock`, {
        params: { threshold, limit },
    });
    return data;
};

/* ── Write ─────────────────────────────────────────────────────────── */

/**
 * Create a new pantry item.
 * @param {Object} itemData – { name, category, quantity, unit, expiry_date }
 */
export const createPantryItem = async (itemData) => {
    const { data } = await api.post(ENDPOINT, itemData);
    return data;
};

/**
 * Full-update a pantry item.
 * @param {string} id
 * @param {Object} itemData – partial update fields
 */
export const updatePantryItem = async (id, itemData) => {
    const { data } = await api.put(`${ENDPOINT}/${id}`, itemData);
    return data;
};

/**
 * Adjust item quantity by a delta value.
 */
export const adjustItemQuantity = async (id, delta) => {
    const { data } = await api.patch(`${ENDPOINT}/${id}/quantity`, null, {
        params: { delta },
    });
    return data;
};

/**
 * Delete a pantry item.
 */
export const deletePantryItem = async (id) => {
    await api.delete(`${ENDPOINT}/${id}`);
};
