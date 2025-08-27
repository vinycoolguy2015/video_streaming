// Global utility functions for the video streaming app

// Global toast notification function
window.showToast = function(message, type = 'info') {
    if (window.app && window.app.showToast) {
        window.app.showToast(message, type);
    } else {
        // Fallback: create a simple toast if app is not ready
        console.log(`Toast: ${message} (${type})`);
        
        // Try to create a basic toast
        const container = document.getElementById('toast-container');
        if (container) {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.textContent = message;
            toast.style.cssText = `
                background: ${type === 'error' ? '#f44336' : type === 'success' ? '#4caf50' : type === 'warning' ? '#ff9800' : '#2196f3'};
                color: white;
                padding: 12px 24px;
                margin: 8px 0;
                border-radius: 4px;
                opacity: 0.9;
            `;
            container.appendChild(toast);
            
            // Auto remove after 3 seconds
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 3000);
        }
    }
};

// Global loading indicator function
window.showLoading = function(show = true) {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.style.display = show ? 'block' : 'none';
    }
    
    // Also try to show/hide any loading overlay
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
    }
};

// Global error handler function
window.showError = function(message) {
    window.showToast(message, 'error');
};

// Global success handler function
window.showSuccess = function(message) {
    window.showToast(message, 'success');
};