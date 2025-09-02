document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let state = {
        devices: {}, // { ip: { name, ip, status, title, thumbnail } }
        mediaFiles: [], // [ { filename, thumbnail_url } ]
        modalTargetDeviceIp: null
    };

    // --- DOM ELEMENTS ---
    const deviceGrid = document.getElementById('device-grid');
    const modal = document.getElementById('file-modal');
    const modalCloseBtn = document.querySelector('.modal-close');
    const modalFileList = document.getElementById('modal-file-list');
    const uploadForm = document.getElementById('upload-form');

    // --- API FUNCTIONS ---
    const api = {
        getDevices: () => fetch('/api/devices').then(res => res.json()),
        getMedia: () => fetch('/api/media').then(res => res.json()),
        getAllStatus: (ips) => fetch('/api/all_status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips })
        }).then(res => res.json()),
        cast: (deviceIp, filename) => fetch('/api/cast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_ip: deviceIp, source: filename })
        }).then(res => res.json()),
        control: (deviceIp, action) => fetch('/api/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_ip: deviceIp, action: action })
        }).then(res => res.json()),
        delete: (filename) => fetch('/api/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        }).then(res => res.json()),
        upload: (formData) => fetch('/api/upload', { method: 'POST', body: formData }).then(res => res.json())
    };

// --- REVISED RENDER FUNCTION ---
// In static/script.js

// --- REVISED RENDER FUNCTION ---
function render() {
    deviceGrid.innerHTML = ''; // Clear the grid
    for (const ip in state.devices) {
        const device = state.devices[ip];
        const card = document.createElement('div');
        card.className = 'device-card';
        card.dataset.ip = ip;

        let contentHTML = '';
        let footerHTML = '';

        if (device.title && (device.status === 'PLAYING' || device.status === 'PAUSED' || device.status === 'UNKNOWN')) {
            card.classList.add('playing');
            const media = state.mediaFiles.find(m => m.filename.startsWith(device.title));
            const thumbnailUrl = media ? media.thumbnail_url : '/static/placeholder.png';
            const displayTitle = media ? media.filename : device.title;
            contentHTML = `
                <img src="${thumbnailUrl}" alt="${displayTitle}">
                <p class="now-playing-title">${displayTitle}</p>
            `;
            footerHTML = `<button class="stop-btn">Stop</button>`;
        } else {
            card.classList.add('idle');
            // --- HIER IST DIE ÄNDERUNG: Emoji durch Ihr Bild ersetzt ---
            contentHTML = `<img src="/static/screen.png" alt="Idle Device" class="idle-device-icon">`;
        }

        card.innerHTML = `
            <div class="device-header">${device.name}</div>
            <div class="device-content">${contentHTML}</div>
            <div class="device-footer">${footerHTML}</div>
        `;
        deviceGrid.appendChild(card);
    }
}



    // --- EVENT HANDLERS ---
    deviceGrid.addEventListener('click', (e) => {
        const card = e.target.closest('.device-card');
        if (!card) return;
        
        const deviceIp = card.dataset.ip;

        if (e.target.classList.contains('stop-btn')) {
            api.control(deviceIp, 'stop').then(() => pollStatus(true)); // Poll immediately after action
        } else if (card.classList.contains('idle')) {
            openModal(deviceIp);
        }
    });

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = uploadForm.querySelector('button');
        btn.textContent = 'Lade hoch...';
        btn.disabled = true;
        await api.upload(new FormData(uploadForm));
        uploadForm.reset();
        await loadMediaFiles(); // Refresh media list
        btn.textContent = 'Hochladen';
        btn.disabled = false;
    });

    // --- MODAL LOGIC ---
// In static/script.js
// In static/script.js

// --- FINAL openModal FUNCTION WITH CORNER BUTTON ---
function openModal(deviceIp) {
    state.modalTargetDeviceIp = deviceIp;
    modalFileList.innerHTML = ''; // Clear previous list
    
    state.mediaFiles.forEach((media, index) => {
        const item = document.createElement('div');
        item.className = 'file-item';
        
        // Set the main content of the item
        item.innerHTML = `
            <img src="${media.thumbnail_url}" alt="${media.filename}" loading="lazy">
            <span>${media.filename}</span>
        `;

        // --- CREATE AND APPEND THE SEPARATE DELETE BUTTON ---
        const deleteBtn = document.createElement('div');
        deleteBtn.className = 'delete-corner-btn';
        deleteBtn.innerHTML = '&#128465;'; // Trash can icon
        deleteBtn.title = 'Datei löschen';

        // Add the delete logic ONLY to the delete button
        deleteBtn.addEventListener('click', (event) => {
            // Stop the click from triggering the parent's (the item's) click listener
            event.stopPropagation(); 

            if (confirm(`Möchten Sie die Datei "${media.filename}" wirklich löschen?`)) {
                api.delete(media.filename).then(response => {
                    if (response.status === 'ok') {
                        item.remove();
                        state.mediaFiles.splice(index, 1);
                    } else {
                        alert(`Fehler: ${response.message}`);
                    }
                });
            }
        });
        
        // Add the button to the item
        item.appendChild(deleteBtn);
        // --- END OF DELETE BUTTON LOGIC ---

        // Add the main click listener to the entire item for casting
        item.addEventListener('click', () => {
             api.cast(state.modalTargetDeviceIp, media.filename).then(() => {
                 closeModal();
                 pollStatus(true);
             });
        });

        modalFileList.appendChild(item);
    });
    modal.style.display = 'flex';
}

    function closeModal() {
        modal.style.display = 'none';
        state.modalTargetDeviceIp = null;
    }

    modalCloseBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    modalFileList.addEventListener('click', (e) => {
        const item = e.target.closest('.file-item');
        if (item) {
            const filename = item.dataset.filename;
            api.cast(state.modalTargetDeviceIp, filename).then(() => {
                closeModal();
                pollStatus(true); // Poll immediately for fast UI update
            });
        }
    });

    // --- POLLING & INITIALIZATION ---
    async function pollStatus(immediate = false) {
        const ips = Object.keys(state.devices);
        if (ips.length === 0) return;

        const statuses = await api.getAllStatus(ips);
        let changed = false;
        for (const ip in statuses) {
            if (state.devices[ip].status !== statuses[ip].state || state.devices[ip].title !== statuses[ip].title) {
                state.devices[ip].status = statuses[ip].state;
                state.devices[ip].title = statuses[ip].title;
                changed = true;
            }
        }
        if (changed || immediate) {
            render();
        }
    }

    async function loadMediaFiles() {
        state.mediaFiles = await api.getMedia();
    }

    async function init() {
        // 1. Discover devices
        const discoveredDevices = await api.getDevices();
        discoveredDevices.forEach(d => {
            state.devices[d.ip] = { ...d, status: 'UNKNOWN', title: null };
        });

        // 2. Load media library
        await loadMediaFiles();

        // 3. Initial render and start polling
        render();
        await pollStatus(true); // Initial poll
        setInterval(pollStatus, 5000); // Poll every 5 seconds
    }

    init();
});
