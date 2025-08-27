/**
 * Video Listing and Pagination Module
 * Handles video library display, pagination, and search functionality
 */

class VideoLibrary {
    constructor() {
        this.currentPage = 1;
        this.totalPages = 1;
        this.videosPerPage = (APP_CONFIG && APP_CONFIG.pagination && APP_CONFIG.pagination.videosPerPage) || 12;
        this.searchQuery = '';
        this.isLoading = false;

        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Search functionality
        const searchBtn = document.getElementById('search-btn');
        const searchInput = document.getElementById('search-input');

        if (searchBtn) {
            searchBtn.addEventListener('click', () => this.handleSearch());
        }

        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.handleSearch();
                }
            });
        }

        // Back to library button
        const backBtn = document.getElementById('back-to-library');
        if (backBtn) {
            backBtn.addEventListener('click', () => this.showLibrary());
        }

        // Video click handling using event delegation
        document.addEventListener('click', (e) => {
            const videoThumbnail = e.target.closest('[data-action="play-video"]');
            if (videoThumbnail) {
                const videoId = videoThumbnail.getAttribute('data-video-id');
                if (videoId) {
                    this.playVideo(videoId);
                }
            }
        });
    }

    async loadVideos(page = 1, search = '') {
        console.log('loadVideos called with page:', page, 'search:', search);
        if (this.isLoading) {
            console.log('Already loading, skipping...');
            return;
        }

        this.isLoading = true;
        this.showLoading(true);

        try {
            const token = await authManager.getToken();
            if (!token) {
                throw new Error('Authentication required');
            }

            const queryParams = new URLSearchParams({
                page: page.toString(),
                limit: this.videosPerPage.toString()
                // Removed status filter to show all videos
            });

            if (search) {
                queryParams.append('search', search);
            }

            const response = await fetch(`${AWS_CONFIG.api.baseUrl}/videos/list?${queryParams}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('API response data:', data);

            // Handle API response format
            const videos = data.videos || [];
            const totalVideos = data.pagination ? data.pagination.totalItems : 0;
            console.log('Extracted videos:', videos, 'totalVideos:', totalVideos);

            // Calculate pagination based on total videos
            this.totalPages = Math.ceil(totalVideos / this.videosPerPage);
            this.currentPage = Math.min(page, this.totalPages || 1);

            // For now, show all videos (we can add pagination later if needed)
            this.renderVideoGrid(videos);
            this.renderPagination({
                currentPage: this.currentPage,
                totalPages: this.totalPages,
                totalVideos: totalVideos
            });

        } catch (error) {
            console.error('Error loading videos:', error);
            this.showError('Failed to load videos. Please try again.');
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }

    renderVideoGrid(videos) {
        console.log('renderVideoGrid called with videos:', videos);
        const videoGrid = document.getElementById('video-grid');
        console.log('videoGrid element:', videoGrid);

        if (!videoGrid) {
            console.error('video-grid element not found!');
            return;
        }

        if (videos.length === 0) {
            console.log('No videos to display');
            videoGrid.innerHTML = `
                <div class="no-videos">
                    <h3>No videos found</h3>
                    <p>Videos will appear here once they are uploaded and processed.</p>
                </div>
            `;
            return;
        }

        console.log('Rendering', videos.length, 'videos');
        const videoCards = videos.map(video => this.createVideoCard(video));
        console.log('Generated video cards:', videoCards);
        videoGrid.innerHTML = videoCards.join('');
        console.log('Video grid innerHTML set, length:', videoGrid.innerHTML.length);
    }

    createVideoCard(video) {
        const duration = this.formatDuration(video.duration);
        const uploadDate = new Date(video.uploadDate).toLocaleDateString();

        return `
            <div class="video-card" data-video-id="${video.id}">
                <div class="video-thumbnail" data-action="play-video" data-video-id="${video.id}">
                    <img src="${video.thumbnail || 'placeholder-thumbnail.svg'}" 
                         alt="${video.title}" 
                         onerror="this.onerror=null; this.src='placeholder-thumbnail.svg'"
                         loading="lazy">
                    <div class="video-duration">${duration}</div>
                    <div class="play-overlay">
                        <div class="play-button">▶</div>
                    </div>
                </div>
                <div class="video-info">
                    <h3 class="video-title" title="${video.title}">${video.title}</h3>
                    <p class="video-description">${video.description || 'No description available'}</p>
                    <div class="video-meta">
                        <span class="upload-date">Uploaded: ${uploadDate}</span>
                        <span class="video-status status-${video.status}">${video.status}</span>
                        <span class="video-qualities">
                            ${(video.qualities || ['HD', 'SD', 'Trial']).map(q => `<span class="quality-badge">${q}</span>`).join('')}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }

    renderPagination(pagination) {
        const paginationContainer = document.getElementById('pagination');
        if (!paginationContainer) return;

        if (pagination.totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }

        const maxButtons = APP_CONFIG.pagination.maxPaginationButtons;
        const currentPage = pagination.currentPage;
        const totalPages = pagination.totalPages;

        let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
        let endPage = Math.min(totalPages, startPage + maxButtons - 1);

        if (endPage - startPage + 1 < maxButtons) {
            startPage = Math.max(1, endPage - maxButtons + 1);
        }

        let paginationHTML = `
            <div class="pagination-info">
                Showing ${(currentPage - 1) * this.videosPerPage + 1} - 
                ${Math.min(currentPage * this.videosPerPage, pagination.totalItems)} 
                of ${pagination.totalItems} videos
            </div>
            <div class="pagination-controls">
        `;

        // Previous button
        if (pagination.hasPrevious) {
            paginationHTML += `
                <button class="btn btn-pagination" onclick="videoLibrary.goToPage(${currentPage - 1})">
                    ← Previous
                </button>
            `;
        }

        // First page
        if (startPage > 1) {
            paginationHTML += `
                <button class="btn btn-pagination" onclick="videoLibrary.goToPage(1)">1</button>
            `;
            if (startPage > 2) {
                paginationHTML += `<span class="pagination-ellipsis">...</span>`;
            }
        }

        // Page numbers
        for (let i = startPage; i <= endPage; i++) {
            const isActive = i === currentPage ? 'active' : '';
            paginationHTML += `
                <button class="btn btn-pagination ${isActive}" onclick="videoLibrary.goToPage(${i})">
                    ${i}
                </button>
            `;
        }

        // Last page
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += `<span class="pagination-ellipsis">...</span>`;
            }
            paginationHTML += `
                <button class="btn btn-pagination" onclick="videoLibrary.goToPage(${totalPages})">
                    ${totalPages}
                </button>
            `;
        }

        // Next button
        if (pagination.hasNext) {
            paginationHTML += `
                <button class="btn btn-pagination" onclick="videoLibrary.goToPage(${currentPage + 1})">
                    Next →
                </button>
            `;
        }

        paginationHTML += `</div>`;
        paginationContainer.innerHTML = paginationHTML;
    }

    async goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) {
            return;
        }

        await this.loadVideos(page, this.searchQuery);

        // Scroll to top of video grid
        const videoGrid = document.getElementById('video-grid');
        if (videoGrid) {
            videoGrid.scrollIntoView({ behavior: 'smooth' });
        }
    }

    async handleSearch() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        this.searchQuery = searchInput.value.trim();
        this.currentPage = 1;

        await this.loadVideos(1, this.searchQuery);
    }

    async playVideo(videoId) {
        try {
            const token = await authManager.getToken();
            if (!token) {
                throw new Error('Authentication required');
            }

            // Get video details
            const response = await fetch(`${AWS_CONFIG.api.baseUrl}/videos/stream/${videoId}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                if (response.status === 202) {
                    this.showError('Video is still processing. Please try again later.');
                    return;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const videoData = await response.json();

            // Show video player
            this.showVideoPlayer(videoData);

        } catch (error) {
            console.error('Error playing video:', error);
            this.showError('Failed to load video. Please try again.');
        }
    }

    showVideoPlayer(videoData) {
        // Hide library, show player
        document.getElementById('video-library').style.display = 'none';
        document.getElementById('video-player-section').style.display = 'block';

        // Update video info
        document.getElementById('current-video-title').textContent = videoData.title;
        document.getElementById('current-video-description').textContent = videoData.description;

        // Setup quality selector for premium users
        const qualitySelector = document.getElementById('quality-selector');
        const qualitySelect = document.getElementById('quality-selector');

        if (videoData.subscriptionType === 'premium' && videoData.availableQualities.length > 1) {
            qualitySelector.style.display = 'block';
            qualitySelect.innerHTML = videoData.availableQualities
                .map(quality => `<option value="${quality}">${quality}</option>`)
                .join('');

            qualitySelect.addEventListener('change', () => {
                this.changeVideoQuality(videoData.videoId, qualitySelect.value);
            });
        } else {
            qualitySelector.style.display = 'none';
        }

        // Setup video player
        const videoPlayer = document.getElementById('main-video');
        videoPlayer.src = videoData.videoUrl;

        // Handle guest user limitations
        if (videoData.subscriptionType === 'guest' && videoData.maxDuration) {
            this.setupGuestLimitations(videoPlayer, videoData.maxDuration);
        }
    }

    setupGuestLimitations(videoPlayer, maxDuration) {
        let hasShownUpgrade = false;

        videoPlayer.addEventListener('timeupdate', () => {
            if (videoPlayer.currentTime >= maxDuration && !hasShownUpgrade) {
                hasShownUpgrade = true;
                videoPlayer.pause();
                this.showUpgradeOverlay();
            }
        });
    }

    showUpgradeOverlay() {
        const overlay = document.getElementById('upgrade-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
        }
    }

    async changeVideoQuality(videoId, quality) {
        try {
            const token = await authManager.getToken();
            const response = await fetch(`${AWS_CONFIG.api.baseUrl}/videos/stream/${videoId}?quality=${quality}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const videoData = await response.json();
            const videoPlayer = document.getElementById('main-video');
            const currentTime = videoPlayer.currentTime;

            videoPlayer.src = videoData.videoUrl;
            videoPlayer.addEventListener('loadedmetadata', () => {
                videoPlayer.currentTime = currentTime;
            }, { once: true });

        } catch (error) {
            console.error('Error changing video quality:', error);
            this.showError('Failed to change video quality.');
        }
    }

    showLibrary() {
        document.getElementById('video-player-section').style.display = 'none';
        document.getElementById('video-library').style.display = 'block';

        // Reload videos to get latest updates
        this.loadVideos(this.currentPage, this.searchQuery);
    }

    showLoading(show) {
        const loading = document.getElementById('loading');
        if (loading) {
            loading.style.display = show ? 'block' : 'none';
        }
    }

    showError(message) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = 'toast toast-error';
        toast.textContent = message;

        const container = document.getElementById('toast-container');
        if (container) {
            container.appendChild(toast);

            setTimeout(() => {
                toast.remove();
            }, 5000);
        }
    }

    formatDuration(seconds) {
        if (!seconds) return '0:00';

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
}

// Global functions for upgrade buttons
function upgradeToStandard() {
    alert('Upgrade to Standard plan functionality would be implemented here.');
    // In a real application, this would redirect to a payment page
}

function upgradeToPremium() {
    alert('Upgrade to Premium plan functionality would be implemented here.');
    // In a real application, this would redirect to a payment page
}

// Initialize video library when DOM is loaded
let videoLibrary;
document.addEventListener('DOMContentLoaded', () => {
    videoLibrary = new VideoLibrary();
});