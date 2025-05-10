/**
 * Main JavaScript for Scanly Web UI
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Handle sidebar toggle on mobile
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            document.querySelector('.sidebar').classList.toggle('show');
        });
    }
    
    // Add active class to current nav item based on URL
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar .nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
    
    // File browser functionality
    initializeFileBrowser();
    
    // Form validation
    initializeFormValidation();
    
    // Initialize scan progress indicators
    initializeScanProgress();
});

/**
 * Initialize file browser functionality
 */
function initializeFileBrowser() {
    const fileBrowser = document.querySelector('.file-browser');
    if (!fileBrowser) return;
    
    // Handle folder click events
    const folders = document.querySelectorAll('.folder-item');
    folders.forEach(folder => {
        folder.addEventListener('click', function(e) {
            e.preventDefault();
            const path = this.dataset.path;
            
            // Show loading indicator
            this.innerHTML += ' <div class="spinner-border spinner-border-sm" role="status"></div>';
            
            // Make AJAX request to get folder contents
            fetch(`/api/browser?path=${encodeURIComponent(path)}`)
                .then(response => response.json())
                .then(data => {
                    // Update file browser content
                    updateFileBrowserContent(data, path);
                })
                .catch(error => {
                    console.error('Error fetching directory contents:', error);
                    showToast('Error accessing directory', 'error');
                })
                .finally(() => {
                    // Remove loading indicator
                    this.querySelector('.spinner-border').remove();
                });
        });
    });
}

/**
 * Update file browser content
 * @param {Object} data - Directory contents
 * @param {String} currentPath - Current directory path
 */
function updateFileBrowserContent(data, currentPath) {
    const fileBrowser = document.querySelector('.file-browser');
    if (!fileBrowser) return;
    
    // Clear current content
    fileBrowser.innerHTML = '';
    
    // Add parent directory option if not at root
    if (currentPath !== '/') {
        const parentPath = currentPath.split('/').slice(0, -1).join('/') || '/';
        const parentDir = document.createElement('div');
        parentDir.className = 'folder-item';
        parentDir.dataset.path = parentPath;
        parentDir.innerHTML = '<i class="fas fa-level-up-alt me-2"></i> ..';
        fileBrowser.appendChild(parentDir);
    }
    
    // Add folders
    data.directories.forEach(dir => {
        const dirElement = document.createElement('div');
        dirElement.className = 'folder-item';
        dirElement.dataset.path = `${currentPath}/${dir}`.replace(/\/\//g, '/');
        dirElement.innerHTML = `<i class="fas fa-folder me-2"></i> ${dir}`;
        fileBrowser.appendChild(dirElement);
    });
    
    // Add files (only show media files)
    data.files.forEach(file => {
        if (file.match(/\.(mp4|mkv|avi|mov|wmv|m4v|jpg|jpeg|png|gif)$/i)) {
            const fileElement = document.createElement('div');
            fileElement.className = 'file-item';
            fileElement.innerHTML = `<i class="fas fa-file me-2"></i> ${file}`;
            fileBrowser.appendChild(fileElement);
        }
    });
    
    // Re-initialize event handlers for new elements
    initializeFileBrowser();
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        });
    });
}

/**
 * Show toast notification
 * @param {String} message - Toast message
 * @param {String} type - Toast type (success, error, warning, info)
 */
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-${getToastClass(type)} border-0`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    
    // Create toast content
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    // Add to container
    toastContainer.appendChild(toastEl);
    
    // Initialize and show toast
    const toast = new bootstrap.Toast(toastEl);
    toast.show();
    
    // Remove toast after it's hidden
    toastEl.addEventListener('hidden.bs.toast', function() {
        toastEl.remove();
    });
}

/**
 * Get Bootstrap color class for toast type
 * @param {String} type - Toast type
 * @return {String} Bootstrap color class
 */
function getToastClass(type) {
    switch (type) {
        case 'success': return 'success';
        case 'error': return 'danger';
        case 'warning': return 'warning';
        case 'info': return 'info';
        default: return 'primary';
    }
}

/**
 * Initialize scan progress tracking
 */
function initializeScanProgress() {
    const scanProgressElement = document.getElementById('scanProgress');
    if (!scanProgressElement) return;
    
    let scanInterval;
    
    // Function to start progress updates
    window.startScanProgress = function() {
        let progress = 0;
        
        // Update progress bar every 500ms
        scanInterval = setInterval(() => {
            // Simulate progress
            if (progress < 100) {
                // Non-linear progress to simulate realistic scanning
                const increment = Math.max(0.1, Math.random() * (100 - progress) / 20);
                progress = Math.min(99, progress + increment);
                
                // Update progress bar
                scanProgressElement.style.width = `${progress}%`;
                scanProgressElement.setAttribute('aria-valuenow', Math.round(progress));
                scanProgressElement.textContent = `${Math.round(progress)}%`;
            }
        }, 500);
    };
    
    // Function to complete progress
    window.completeScanProgress = function() {
        clearInterval(scanInterval);
        scanProgressElement.style.width = '100%';
        scanProgressElement.setAttribute('aria-valuenow', 100);
        scanProgressElement.textContent = '100%';
    };
    
    // Function to reset progress
    window.resetScanProgress = function() {
        clearInterval(scanInterval);
        scanProgressElement.style.width = '0%';
        scanProgressElement.setAttribute('aria-valuenow', 0);
        scanProgressElement.textContent = '0%';
    };
}