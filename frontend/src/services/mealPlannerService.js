/**
 * Service layer for LLM Meal Planner API.
 */
import api from './api';

const ENDPOINT = '/llm';

// LLM calls can take up to 20s for a 7-day plan — use a longer-lived client
const llmApi = api.create ? api : {
    post: (url, data, config) => api.post(url, data, { ...config, timeout: 60000 }),
    get: (url, config) => api.get(url, { ...config, timeout: 60000 }),
    delete: (url, config) => api.delete(url, { ...config, timeout: 30000 }),
    patch: (url, data, config) => api.patch(url, data, { ...config, timeout: 30000 }),
};

/**
 * Generate a weekly LLM meal plan.
 * @param {{ days, diet_type, servings, meals_per_day }} opts
 */
export const generateMealPlan = async ({
    days = 7,
    diet_type = 'standard',
    servings = 2,
    meals_per_day = 1,
} = {}) => {
    const { data } = await api.post(
        `${ENDPOINT}/generate`,
        { days, diet_type, servings, meals_per_day },
        { timeout: 90000 }   // up to 90 s for large plans
    );
    return data;
};

/**
 * Generate a single meal suggestion.
 * @param {{ diet_type, servings, meal_type }} opts
 */
export const generateSingleMeal = async ({
    diet_type = 'standard',
    servings = 2,
    meal_type = 'dinner',
} = {}) => {
    const { data } = await api.post(
        `${ENDPOINT}/generate-single`,
        { diet_type, servings, meal_type },
        { timeout: 30000 }
    );
    return data;
};

/**
 * Get a saved meal plan by ID.
 */
export const getMealPlan = async (planId) => {
    const { data } = await api.get(`${ENDPOINT}/${planId}`, { timeout: 10000 });
    return data;
};

/**
 * Regenerate a specific day in an existing plan.
 */
export const regenerateDay = async (planId, day) => {
    const { data } = await api.post(
        `${ENDPOINT}/${planId}/regenerate-day`,
        { day },
        { timeout: 30000 }
    );
    return data;
};

/**
 * Mark a meal as completed and deduct from real pantry.
 */
export const completeMeal = async (planId, day, meal_type = 'dinner') => {
    const { data } = await api.patch(
        `${ENDPOINT}/${planId}/complete`,
        { day, meal_type },
        { timeout: 15000 }
    );
    return data;
};

/**
 * Delete a saved meal plan.
 */
export const deleteMealPlan = async (planId) => {
    await api.delete(`${ENDPOINT}/${planId}`, { timeout: 10000 });
};
