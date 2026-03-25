/**
 * Service for Grocery Recognition (Computer Vision) API.
 * Handles image upload and grocery detection.
 */
import api from './api';

const ENDPOINT = '/grocery-recognition';

/**
 * Upload an image and detect grocery items using Google Gemini.
 *
 * @param {File} imageFile – Image file to scan (JPEG/PNG/WebP)
 * @returns {Promise<{detected_items, total_items_detected, total_instances, image_width, image_height}>}
 */
export const detectGroceries = async (imageFile) => {
    const formData = new FormData();
    formData.append('file', imageFile);

    const { data } = await api.post(`${ENDPOINT}/detect`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000, // 120s timeout in case Gemini API is slow
    });

    return data;
};
