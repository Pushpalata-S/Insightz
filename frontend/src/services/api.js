import axios from 'axios';

const API_URL = "http://127.0.0.1:8000";

export const api = axios.create({
    baseURL: API_URL,
    headers: {
        "Content-Type": "application/json",
    },
});

// --- JWT INTERCEPTOR ---
// This code runs before EVERY request.
// It checks for a token and attaches it to the header.
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem("ranger_token");
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Optional: specific helper for file uploads if needed later
export const uploadFile = (formData) => {
    return api.post('/upload', formData, {
        headers: { "Content-Type": "multipart/form-data" },
    });
};