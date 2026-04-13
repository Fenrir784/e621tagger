if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js').then(reg => {
            console.log('Service Worker registered:', reg);
        }).catch(err => {
            console.error('Service Worker registration failed:', err);
        });
    });

    navigator.serviceWorker.addEventListener('message', event => {
        if (event.data && event.data.action === 'reload') {
            window.location.reload();
        }
    });
}