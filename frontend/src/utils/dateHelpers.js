/**
 * Date & expiry helper utilities.
 */

/**
 * Format an ISO date string to a readable format.
 * @param {string|null} dateStr – ISO date string
 * @returns {string}
 */
export const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return '—';

    return date.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
    });
};

/**
 * Calculate days until expiry from an ISO date string.
 * @param {string|null} dateStr
 * @returns {number|null} – negative means expired
 */
export const daysUntilExpiry = (dateStr) => {
    if (!dateStr) return null;
    const expiry = new Date(dateStr);
    if (isNaN(expiry.getTime())) return null;

    const now = new Date();
    now.setHours(0, 0, 0, 0);
    expiry.setHours(0, 0, 0, 0);

    return Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
};

/**
 * Return a status object for display based on days remaining.
 * @param {string|null} dateStr
 * @returns {{ label: string, type: 'expired'|'warning'|'ok'|'none' }}
 */
export const getExpiryStatus = (dateStr) => {
    const days = daysUntilExpiry(dateStr);

    if (days === null) return { label: 'No expiry', type: 'none', days: null };
    if (days < 0) return { label: 'Expired', type: 'expired', days };
    if (days === 0) return { label: 'Expires today', type: 'expired', days };
    if (days <= 3) return { label: `In ${days}d`, type: 'warning', days };
    if (days <= 7) return { label: `In ${days}d`, type: 'warning', days };
    return { label: formatDate(dateStr), type: 'ok', days };
};

/**
 * Format a quantity + unit into a compact readable string.
 */
export const formatQuantity = (qty, unit) => {
    if (qty === undefined || qty === null) return '—';
    const rounded = Number.isInteger(qty) ? qty : parseFloat(qty.toFixed(1));
    return `${rounded} ${unit || ''}`.trim();
};
