import React, { useState, useRef, useCallback } from 'react';
import { detectGroceries } from '../../services/groceryService';
import './GroceryScanner.css';

export default function GroceryScanner({ onScanComplete, onClose }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [scanning, setScanning] = useState(false);
    const [error, setError] = useState(null);
    const [dragOver, setDragOver] = useState(false);
    const fileInputRef = useRef(null);

    const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
    const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

    const handleFile = useCallback((file) => {
        setError(null);

        if (!ALLOWED_TYPES.includes(file.type)) {
            setError('Please upload a JPEG, PNG, or WebP image.');
            return;
        }
        if (file.size > MAX_SIZE) {
            setError('Image must be smaller than 10 MB.');
            return;
        }

        setSelectedFile(file);
        const reader = new FileReader();
        reader.onload = (e) => setPreview(e.target.result);
        reader.readAsDataURL(file);
    }, []);

    /* ── Drag & Drop handlers ────────────────────────────────────── */
    const handleDragOver = (e) => {
        e.preventDefault();
        setDragOver(true);
    };
    const handleDragLeave = (e) => {
        e.preventDefault();
        setDragOver(false);
    };
    const handleDrop = (e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    };

    /* ── File picker ─────────────────────────────────────────────── */
    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) handleFile(file);
    };

    /* ── Scan ────────────────────────────────────────────────────── */
    const handleScan = async () => {
        if (!selectedFile) return;

        setScanning(true);
        setError(null);

        try {
            const result = await detectGroceries(selectedFile);
            onScanComplete(result);
        } catch (err) {
            setError(err.message || 'Detection failed. Please try again.');
        } finally {
            setScanning(false);
        }
    };

    /* ── Clear ───────────────────────────────────────────────────── */
    const handleClear = () => {
        setSelectedFile(null);
        setPreview(null);
        setError(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    return (
        <div className="scanner-backdrop" onClick={onClose}>
            <div className="scanner-panel" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="scanner-header">
                    <h2>📷 Grocery Scanner</h2>
                    <p className="scanner-subtitle">
                        Upload a photo of your groceries and we'll identify them for you!
                    </p>
                    <button className="scanner-close-btn" onClick={onClose}>✖</button>
                </div>

                {/* Drop zone / Preview */}
                <div className="scanner-body">
                    {!preview ? (
                        <div
                            className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <div className="drop-zone-content">
                                <span className="drop-icon">🛒</span>
                                <p className="drop-title">
                                    Drag & drop a grocery photo here
                                </p>
                                <p className="drop-hint">
                                    or click to browse • JPEG, PNG, WebP up to 10 MB
                                </p>
                            </div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="image/jpeg,image/png,image/webp"
                                onChange={handleFileSelect}
                                style={{ display: 'none' }}
                                id="grocery-file-input"
                            />
                        </div>
                    ) : (
                        <div className="image-preview-container">
                            <img
                                src={preview}
                                alt="Grocery preview"
                                className="image-preview"
                            />
                            <button
                                className="clear-image-btn"
                                onClick={handleClear}
                                title="Remove image"
                            >
                                ✕
                            </button>
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div className="scanner-error">
                            <span>⚠️</span> {error}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="scanner-footer">
                    <button
                        className="btn-cancel-scan"
                        onClick={onClose}
                    >
                        Cancel
                    </button>
                    <button
                        className="btn-scan"
                        onClick={handleScan}
                        disabled={!selectedFile || scanning}
                    >
                        {scanning ? (
                            <>
                                <span className="scan-spinner"></span>
                                Scanning...
                            </>
                        ) : (
                            <>🔍 Scan Groceries</>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
