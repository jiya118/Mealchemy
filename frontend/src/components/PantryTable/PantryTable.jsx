/**
 * PantryTable — renders the main pantry items data table.
 *
 * Props:
 *  - items          : PantryItemResponse[]
 *  - loading        : boolean
 *  - sortBy         : string
 *  - sortOrder      : 'asc' | 'desc'
 *  - onSort         : (field: string) => void
 *  - onEdit         : (item) => void
 *  - onDelete       : (item) => void
 */
import { getCategoryByValue } from '../../constants/pantryConstants';
import { formatQuantity, getExpiryStatus, formatDate } from '../../utils/dateHelpers';
import './PantryTable.css';

/* ── Sub-components ────────────────────────────────────────────────── */

function SortableHeader({ label, field, sortBy, sortOrder, onSort }) {
    const isActive = sortBy === field;
    const classes = [
        'sortable',
        isActive ? 'active' : '',
        isActive && sortOrder === 'desc' ? 'desc' : '',
    ]
        .filter(Boolean)
        .join(' ');

    return (
        <th className={classes} onClick={() => onSort(field)}>
            {label}
            <span className="sort-icon">▲</span>
        </th>
    );
}

function ExpiryBadge({ dateStr }) {
    const status = getExpiryStatus(dateStr);
    return (
        <span className={`expiry-status status-${status.type}`}>
            <span className="status-dot" />
            {status.type === 'ok' ? formatDate(dateStr) : status.label}
        </span>
    );
}

function SkeletonRows({ count = 5 }) {
    return Array.from({ length: count }, (_, i) => (
        <tr key={i} className="skeleton-row">
            <td>
                <div className="skeleton-name">
                    <div className="skeleton-block circle" />
                    <div className="skeleton-block wide" />
                </div>
            </td>
            <td><div className="skeleton-block medium" /></td>
            <td><div className="skeleton-block narrow" /></td>
            <td><div className="skeleton-block medium" /></td>
            <td><div className="skeleton-block narrow" /></td>
        </tr>
    ));
}

/* ── Main Component ────────────────────────────────────────────────── */

export default function PantryTable({
    items,
    loading,
    sortBy,
    sortOrder,
    onSort,
    onEdit,
    onDelete,
}) {
    const headerProps = { sortBy, sortOrder, onSort };

    /* Empty state */
    if (!loading && items.length === 0) {
        return (
            <div className="pantry-table-wrapper">
                <div className="table-empty-state">
                    <div className="empty-emoji">🫙</div>
                    <h3 className="empty-title">Your pantry looks empty!</h3>
                    <p className="empty-subtitle">
                        Add your first item to start managing your kitchen inventory.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="pantry-table-wrapper">
            <table className="pantry-table" id="pantry-items-table">
                <thead>
                    <tr>
                        <SortableHeader label="Item Name" field="name" {...headerProps} />
                        <SortableHeader label="Category" field="category" {...headerProps} />
                        <SortableHeader label="Quantity" field="quantity" {...headerProps} />
                        <SortableHeader label="Expiry Date" field="expiry_date" {...headerProps} />
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {loading ? (
                        <SkeletonRows count={5} />
                    ) : (
                        items.map((item) => {
                            const cat = getCategoryByValue(item.category);
                            return (
                                <tr key={item.id || item._id}>
                                    {/* NAME */}
                                    <td>
                                        <div className="item-name-cell">
                                            <span className="item-emoji">{cat.emoji}</span>
                                            <span className="item-name">{item.name}</span>
                                        </div>
                                    </td>

                                    {/* CATEGORY */}
                                    <td>
                                        <span className="category-badge">{cat.label}</span>
                                    </td>

                                    {/* QUANTITY */}
                                    <td className="quantity-cell">
                                        {formatQuantity(item.quantity, item.unit)}
                                    </td>

                                    {/* EXPIRY */}
                                    <td>
                                        <ExpiryBadge dateStr={item.expiry_date} />
                                    </td>

                                    {/* ACTIONS */}
                                    <td>
                                        <div className="actions-cell">
                                            <button
                                                className="action-btn edit-btn"
                                                title="Edit item"
                                                id={`edit-${item.id || item._id}`}
                                                onClick={() => onEdit(item)}
                                            >
                                                ✏️
                                            </button>
                                            <button
                                                className="action-btn delete-btn"
                                                title="Delete item"
                                                id={`delete-${item.id || item._id}`}
                                                onClick={() => onDelete(item)}
                                            >
                                                🗑️
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            );
                        })
                    )}
                </tbody>
            </table>
        </div>
    );
}
