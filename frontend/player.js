// Video player with subscription-based features
class VideoPlayer {
    constructor() {
        this.currentVideo = null;
        this.subscriptionType = 'free';
        this.currentQuality = '720p';
        this.freeTimeLimit = 10; // 10 seconds for free users
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Back to library button
        const backBtn = document.getElementById('back-to-library');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                this.closePlayer();
            });
        }

        // Video player events
        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.addEventListener('loadedmetadata', () => {
                this.onVideoLoaded();
            });

            videoElement.addEventListener('timeupdate', () => {
                this.onTimeUpdate();
            });

            videoElement.addEventListener('ended', () => {
                this.onVideoEnded();
            });

            videoElement.addEventListener('play', () => {
                this.onVideoPlay();
            });

            videoElement.addEventListener('pause', () => {
                this.onVideoPause();
            });
        }

        // Ad controls
        const skipAdBtn = document.getElementById('skip-ad');
        if (skipAdBtn) {
            skipAdBtn.addEventListener('click', () => {
                this.skipAd();
            });
        }
    }

    async loadVideo(videoId, title) {
        try {
            showLoading(true);

            // Get video stream URL from backend
            const videoData = await this.getVideoStreamData(videoId);

            // Use subscription type from backend response (more reliable)
            this.subscriptionType = videoData.subscriptionType || authManager.getUserSubscriptionType();
            console.log(`Backend subscription type: ${videoData.subscriptionType}`);
            console.log(`Auth manager subscription type: ${authManager.getUserSubscriptionType()}`);
            console.log(`Final subscription type: ${this.subscriptionType}`);

            // Update UI
            this.showPlayer();
            this.updateVideoInfo(title, videoData);

            // Load video based on subscription type
            await this.loadVideoBySubscription(videoData);

            this.currentVideo = {
                id: videoId,
                title: title,
                data: videoData
            };

        } catch (error) {
            console.error('Error loading video:', error);
            showToast(`Failed to load video: ${error.message}`, 'error');
        } finally {
            showLoading(false);
        }
    }

    async getVideoStreamData(videoId, quality = null) {
        const token = await authManager.getToken();

        let url = `${CONFIG_UTILS.getApiEndpoint('stream')}/${videoId}`;
        if (quality) {
            url += `?quality=${quality}`;
        }

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get video stream');
        }

        return await response.json();
    }

    showPlayer() {
        const dashboard = document.getElementById('dashboard');
        const playerSection = document.getElementById('video-player-section');

        if (dashboard) dashboard.style.display = 'none';
        if (playerSection) playerSection.style.display = 'block';
    }

    closePlayer() {
        const dashboard = document.getElementById('dashboard');
        const playerSection = document.getElementById('video-player-section');
        const videoElement = document.getElementById('main-video');

        // Stop video
        if (videoElement) {
            videoElement.pause();
            videoElement.src = '';
        }

        // Hide overlays
        this.hideFreeUpgradeOverlay();

        // Show dashboard
        if (dashboard) dashboard.style.display = 'block';
        if (playerSection) playerSection.style.display = 'none';

        // Reset state
        this.currentVideo = null;
    }

    updateVideoInfo(title, videoData) {
        const titleElement = document.getElementById('current-video-title');
        const descriptionElement = document.getElementById('current-video-description');
        const qualityIndicator = document.getElementById('current-quality-value');

        if (titleElement) titleElement.textContent = title;
        if (descriptionElement) descriptionElement.textContent = videoData.description || '';

        // Update quality indicator
        if (qualityIndicator) {
            const quality = videoData.quality || '480p';
            qualityIndicator.textContent = quality;
            this.currentQuality = quality;
        }
    }

    async loadVideoBySubscription(videoData) {
        const videoElement = document.getElementById('main-video');
        if (!videoElement) return;

        // Set video source
        videoElement.src = videoData.videoUrl;

        // Setup subscription-specific features
        switch (this.subscriptionType) {
            case 'premium':
                this.setupPremiumFeatures(videoData);
                break;
            case 'standard':
                this.setupStandardFeatures(videoData);
                break;
            case 'free':
                this.setupFreeFeatures(videoData);
                break;
        }
    }

    setupPremiumFeatures(videoData) {
        // Premium users get full access with quality selection

        // Enable all video controls
        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.controls = true;
        }

        // Show quality selector
        this.showQualitySelector(videoData.availableQualities || ['480p', '720p', '1080p']);
    }

    setupStandardFeatures(videoData) {
        // Standard users get full video in 480p

        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.controls = true;
        }
    }

    setupFreeFeatures(videoData) {
        // Free users get limited access

        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.controls = true;
        }
    }

    onVideoLoaded() {
        const videoElement = document.getElementById('main-video');
        const durationElement = document.getElementById('video-duration');

        if (videoElement && durationElement) {
            const duration = videoElement.duration;
            durationElement.textContent = `Duration: ${CONFIG_UTILS.formatDuration(duration)}`;
        }

        // Show appropriate message based on subscription
        // No subscription messages needed
    }

    onTimeUpdate() {
        const videoElement = document.getElementById('main-video');
        if (!videoElement) return;

        // No need for frontend time limits since free users get actual 10-second video files
        // The video file itself enforces the limitation
    }

    showQualitySelector(availableQualities) {
        const qualitySelector = document.getElementById('quality-selector');
        if (!qualitySelector) return;

        // Clear existing options
        qualitySelector.innerHTML = '';

        // Add quality options and set the correct selection
        availableQualities.forEach(quality => {
            const option = document.createElement('option');
            option.value = quality;
            option.textContent = quality;
            qualitySelector.appendChild(option);
        });

        // Set the correct selected option based on current quality
        qualitySelector.value = this.currentQuality;

        // Show quality selector
        qualitySelector.style.display = 'block';

        // Remove existing event listeners to avoid duplicates
        const newSelector = qualitySelector.cloneNode(true);
        qualitySelector.parentNode.replaceChild(newSelector, qualitySelector);
        
        // Set the value again on the new selector
        newSelector.value = this.currentQuality;

        // Add change event listener to the new selector
        newSelector.addEventListener('change', (e) => {
            this.changeQuality(e.target.value);
        });
    }

    async changeQuality(newQuality) {
        if (!this.currentVideo || this.currentQuality === newQuality) return;

        try {
            showLoading(true);

            // Get new video URL with selected quality
            const videoData = await this.getVideoStreamData(this.currentVideo.id, newQuality);

            const videoElement = document.getElementById('main-video');
            if (videoElement) {
                const currentTime = videoElement.currentTime;
                const wasPlaying = !videoElement.paused;

                // Update video source
                videoElement.src = videoData.videoUrl;

                // Restore playback position
                videoElement.addEventListener('loadedmetadata', () => {
                    videoElement.currentTime = currentTime;
                    if (wasPlaying) {
                        videoElement.play();
                    }
                }, { once: true });
            }

            // Update quality indicator with the actual quality from backend response
            this.currentQuality = videoData.quality || newQuality;
            const qualityIndicator = document.getElementById('current-quality-value');
            if (qualityIndicator) {
                qualityIndicator.textContent = this.currentQuality;
            }

            // Also update the dropdown to match the actual quality
            const qualitySelector = document.getElementById('quality-selector');
            if (qualitySelector) {
                qualitySelector.value = this.currentQuality;
            }

            showToast(`Quality changed to ${this.currentQuality}`, 'success');

        } catch (error) {
            console.error('Quality change error:', error);
            showToast(`Failed to change quality: ${error.message}`, 'error');
        } finally {
            showLoading(false);
        }
    }

    showFreeUpgradeOverlay() {
        const upgradeOverlay = document.getElementById('upgrade-overlay');
        if (upgradeOverlay) {
            upgradeOverlay.style.display = 'flex';
        }

        // Setup upgrade buttons
        const upgradeButtons = upgradeOverlay?.querySelectorAll('button');
        upgradeButtons?.forEach(button => {
            button.addEventListener('click', (e) => {
                const planType = e.target.dataset.plan || 'standard';
                this.handleUpgrade(planType);
            });
        });
    }

    hideFreeUpgradeOverlay() {
        const upgradeOverlay = document.getElementById('upgrade-overlay');
        if (upgradeOverlay) {
            upgradeOverlay.style.display = 'none';
        }
    }

    async handleUpgrade(planType) {
        try {
            showLoading(true);

            // In a real application, this would redirect to a payment page
            // For demo purposes, we'll simulate the upgrade
            showToast(`Redirecting to upgrade to ${planType} plan...`, 'info');

            // Simulate upgrade process
            setTimeout(() => {
                showToast(`Upgrade to ${planType} completed! Please refresh to see changes.`, 'success');
                this.hideFreeUpgradeOverlay();
            }, 2000);

        } catch (error) {
            console.error('Upgrade error:', error);
            showToast(`Upgrade failed: ${error.message}`, 'error');
        } finally {
            showLoading(false);
        }
    }

    onVideoPlay() {
        console.log('Video started playing');
    }

    onVideoPause() {
        console.log('Video paused');
    }

    onVideoEnded() {
        console.log('Video ended');

        // Show replay option and back button instead of auto-closing
        this.showVideoEndedOptions();
    }

    showVideoEndedOptions() {
        // Just ensure controls are visible for replay - no toast message needed
        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.controls = true; // Ensure controls are visible for replay
        }
    }

    // Utility methods for video controls
    setPlaybackRate(rate) {
        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.playbackRate = rate;
        }
    }

    setVolume(volume) {
        const videoElement = document.getElementById('main-video');
        if (videoElement) {
            videoElement.volume = Math.max(0, Math.min(1, volume));
        }
    }

    toggleFullscreen() {
        const videoElement = document.getElementById('main-video');
        if (!videoElement) return;

        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            videoElement.requestFullscreen();
        }
    }

    // Picture-in-Picture support
    togglePictureInPicture() {
        const videoElement = document.getElementById('main-video');
        if (!videoElement) return;

        if (document.pictureInPictureElement) {
            document.exitPictureInPicture();
        } else if (videoElement.requestPictureInPicture) {
            videoElement.requestPictureInPicture();
        }
    }
}

// Initialize video player
const videoPlayer = new VideoPlayer();
