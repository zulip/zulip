export function show_loading_indicator() {
    const loading = document.createElement('div');
    loading.className = 'loading-indicator';
    loading.innerHTML = '<div class="spinner"></div> Loading messages...';
    loading.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        z-index: 9999;
    `;
    document.body.appendChild(loading);
    return loading;
}

export function hide_loading_indicator(loading) {
    if (loading && loading.parentNode) {
        loading.parentNode.removeChild(loading);
    }
}