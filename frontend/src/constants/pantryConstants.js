/**
 * Pantry item constants — mirroring backend enums for category & unit.
 */

export const CATEGORIES = [
    { value: 'grains', label: 'Grains', emoji: '🌾' },
    { value: 'Grains & Cereals', label: 'Grains & Cereals', emoji: '🌾' },
    { value: 'canned_goods', label: 'Canned Goods', emoji: '🥫' },
    { value: 'spices', label: 'Spices', emoji: '🌶️' },
    { value: 'Spices & Condiments', label: 'Spices & Condiments', emoji: '🧂' },
    { value: 'condiments', label: 'Condiments', emoji: '🫙' },
    { value: 'baking', label: 'Baking', emoji: '🧁' },
    { value: 'Bakery & Snacks', label: 'Bakery & Snacks', emoji: '🍪' },
    { value: 'snacks', label: 'Snacks', emoji: '🍿' },
    { value: 'Beverages', label: 'Beverages', emoji: '☕' },
    { value: 'Dairy', label: 'Dairy', emoji: '🥛' },
    { value: 'Eggs', label: 'Eggs', emoji: '🥚' },
    { value: 'Vegetables', label: 'Vegetables', emoji: '🥬' },
    { value: 'Fruits', label: 'Fruits', emoji: '🍎' },
    { value: 'Oils', label: 'Oils', emoji: '🫒' },
    { value: 'Sugar & Sweeteners', label: 'Sugar & Sweeteners', emoji: '🍯' },
    { value: 'frozen', label: 'Frozen', emoji: '🧊' },
    { value: 'Pulses & Lentils', label: 'Pulses & Lentils', emoji: '🫘' },
    { value: 'other', label: 'Other', emoji: '📦' },
];

export const UNITS = [
    { value: 'pieces', label: 'Pieces' },
    { value: 'grams', label: 'Grams (g)' },
    { value: 'kilograms', label: 'Kilograms (kg)' },
    { value: 'kg', label: 'kg' },
    { value: 'milliliters', label: 'Milliliters (ml)' },
    { value: 'ml', label: 'ml' },
    { value: 'liters', label: 'Liters (L)' },
    { value: 'liter', label: 'Liter' },
    { value: 'ounces', label: 'Ounces (oz)' },
    { value: 'pounds', label: 'Pounds (lb)' },
    { value: 'cups', label: 'Cups' },
    { value: 'tablespoons', label: 'Tablespoons' },
    { value: 'teaspoons', label: 'Teaspoons' },
    { value: 'slices', label: 'Slices' },
    { value: 'pack', label: 'Pack' },
    { value: 'packs', label: 'Packs' },
];

/**
 * Lookup helpers
 */
export const getCategoryByValue = (value) =>
    CATEGORIES.find((c) => c.value === value) || { value, label: value, emoji: '📦' };

export const getUnitLabel = (value) => {
    const u = UNITS.find((u) => u.value === value);
    return u ? u.label : value;
};

/**
 * Sort-by options for the UI
 */
export const SORT_OPTIONS = [
    { value: 'name', label: 'Name' },
    { value: 'category', label: 'Category' },
    { value: 'quantity', label: 'Quantity' },
    { value: 'expiry_date', label: 'Expiry Date' },
    { value: 'created_at', label: 'Date Added' },
];

export const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];
