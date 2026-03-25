/**
 * Axios instance configured for the Mealchemy backend.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    timeout: 15000,
});

/* ── Request interceptor (auth placeholder) ───────────────────────── */
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error),
);

/* ── Response interceptor (global error normalisation) ────────────── */
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const message =
            error.response?.data?.detail ||
            error.response?.data?.message ||
            error.message ||
            'An unexpected error occurred';

        return Promise.reject({ message, status: error.response?.status });
    },
);

export default api;
