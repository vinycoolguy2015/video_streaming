/**
 * Main Application Controller
 * Handles application initialization, navigation, and user interface
 */

class VideoStreamingApp {
    constructor() {
        this.currentUser = null;
        this.currentSection = 'auth';
        this.videoLibrary = null;
        
        this.initializeApp();
    }

    async initializeApp() {
        try {
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.init());
            } else {
                this.init();
            }
        } catch (error) {
            console.error('Error initializing app:', error);
            this.showError('Failed to initialize application. Please refresh the page.');
        }
    }

    async init() {
        try {
            // Small delay to ensure all scripts are loaded
            await new Promise(resolve => setTimeout(resolve, 100));

            // Validate configuration
            if (!CONFIG_UTILS.validateConfig()) {
                this.showError('Application configuration is incomplete. Please check the setup.');
                return;
            }

            // Initialize authentication manager
            if (typeof authManager !== 'undefined') {
                if (!authManager.init()) {
                    throw new Error('Failed to initialize authentication manager');
                }
            }

            // Setup event listeners
            this.setupEventListeners();

            // Wait a moment for authManager to complete initialization
            await new Promise(resolve => setTimeout(resolve, 1000));

            // Check if user is already authenticated
            const token = await authManager.getToken();
            if (token && authManager.isTokenValid(token)) {
                const userInfo = authManager.getCurrentUser();
                console.log('Found authenticated user:', userInfo);
                if (userInfo) {
                    await this.handleSuccessfulAuth(userInfo);
                } else {
                    console.log('Token valid but no user info available');
                    this.showAuthSection();
                }
            } else {
                console.log('No valid token found');
                this.showAuthSection();
            }

            console.log('Video Streaming App initialized successfully');
            
        } catch (error) {
            console.error('Error initializing app:', error);
            this.showError('Failed to initialize application. Please refresh the page.');
        }
    }

    setupEventListeners() {
        // Authentication buttons
        const loginBtn = document.getElementById('login-btn');
        const signupBtn = document.getElementById('signup-btn');
        const logoutBtn = document.getElementById('logout-btn');

        if (loginBtn) {
            loginBtn.addEventListener('click', () => this.showLoginForm());
        }

        if (signupBtn) {
            signupBtn.addEventListener('click', () => this.showSignupForm());
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.handleLogout());
        }

        // Form toggle buttons
        const showSignupBtn = document.getElementById('show-signup');
        const showLoginBtn = document.getElementById('show-login');

        if (showSignupBtn) {
            showSignupBtn.addEventListener('click', () => this.showSignupForm());
        }

        if (showLoginBtn) {
            showLoginBtn.addEventListener('click', () => this.showLoginForm());
        }

        // Form submissions
        const loginForm = document.getElementById('login-form-element');
        const signupForm = document.getElementById('signup-form-element');
        const verificationForm = document.getElementById('verification-form-element');

        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        if (signupForm) {
            signupForm.addEventListener('submit', (e) => this.handleSignup(e));
        }

        if (verificationForm) {
            verificationForm.addEventListener('submit', (e) => this.handleVerification(e));
        }

        // Resend verification code button
        const resendCodeBtn = document.getElementById('resend-code-btn');
        if (resendCodeBtn) {
            resendCodeBtn.addEventListener('click', (e) => this.handleResendCode(e));
        }

        // Global keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    handleKeyboardShortcuts(e) {
        // ESC key to close modals/sections
        if (e.key === 'Escape') {
            if (this.currentSection === 'player') {
                this.showLibrary();
            }
        }

        // Space bar to play/pause video
        if (e.key === ' ' && this.currentSection === 'player') {
            e.preventDefault();
            const videoPlayer = document.getElementById('main-video');
            if (videoPlayer) {
                if (videoPlayer.paused) {
                    videoPlayer.play();
                } else {
                    videoPlayer.pause();
                }
            }
        }
    }

    // Authentication Methods
    showAuthSection() {
        this.hideAllSections();
        document.getElementById('auth-section').style.display = 'flex';
        document.getElementById('auth-buttons').style.display = 'flex';
        document.getElementById('user-info').style.display = 'none';
        this.currentSection = 'auth';
    }

    showLoginForm() {
        this.hideAuthForms();
        document.getElementById('login-form').style.display = 'block';
    }

    showSignupForm() {
        this.hideAuthForms();
        document.getElementById('signup-form').style.display = 'block';
    }

    showVerificationForm() {
        this.hideAuthForms();
        document.getElementById('verification-form').style.display = 'block';
    }

    hideAuthForms() {
        const forms = ['login-form', 'signup-form', 'verification-form'];
        forms.forEach(formId => {
            const form = document.getElementById(formId);
            if (form) form.style.display = 'none';
        });
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        if (!email || !password) {
            this.showError('Please fill in all fields');
            return;
        }

        try {
            this.showLoading('Signing in...');
            
            const result = await authManager.signIn(email, password);
            this.hideLoading();
            
            if (result && result.success && result.user) {
                console.log('Login successful, handling auth...', result.user);
                await this.handleSuccessfulAuth(result.user);
                this.showSuccess('Successfully signed in!');
            } else {
                console.error('Login failed:', result);
                this.showError((result && result.error) || 'Login failed. Please try again.');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('Login failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async handleSignup(e) {
        e.preventDefault();
        
        const email = document.getElementById('signup-email').value;
        const password = document.getElementById('signup-password').value;
        const subscriptionPlan = document.getElementById('subscription-plan').value;

        if (!email || !password || !subscriptionPlan) {
            this.showError('Please fill in all fields');
            return;
        }

        // Validate password strength
        if (password.length < 8) {
            this.showError('Password must be at least 8 characters long');
            return;
        }

        try {
            this.showLoading('Creating account...');
            
            const result = await authManager.signUp(email, password, {
                subscription_type: subscriptionPlan
            });
            
            if (result.success) {
                this.showVerificationForm();
                this.showSuccess('Account created! Please check your email for verification code.');
            } else {
                this.showError(result.error || 'Signup failed');
            }
        } catch (error) {
            console.error('Signup error:', error);
            this.showError('Signup failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async handleVerification(e) {
        e.preventDefault();
        
        const code = document.getElementById('verification-code').value;

        if (!code) {
            this.showError('Please enter the verification code');
            return;
        }

        try {
            this.showLoading('Verifying...');
            
            const result = await authManager.confirmSignUp(code);
            
            if (result.success) {
                this.showLoginForm();
                this.showSuccess('Email verified! Please sign in.');
            } else {
                this.showError(result.error || 'Verification failed');
            }
        } catch (error) {
            console.error('Verification error:', error);
            this.showError('Verification failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async handleResendCode(e) {
        e.preventDefault();
        
        try {
            this.showLoading('Resending verification code...');
            
            const result = await authManager.resendVerificationCode();
            
            if (result.success) {
                this.showSuccess(result.message || 'Verification code sent to your email');
            } else {
                this.showError(result.error || 'Failed to resend verification code');
            }
        } catch (error) {
            console.error('Resend code error:', error);
            this.showError('Failed to resend verification code. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async handleSuccessfulAuth(user) {
        console.log('Handling successful auth with user:', user);
        
        if (!user) {
            console.error('No user data provided to handleSuccessfulAuth');
            return;
        }

        this.currentUser = user;
        
        // Update UI
        const userNameElement = document.getElementById('user-name');
        if (userNameElement) {
            userNameElement.textContent = user.email || user.username;
        }
        
        // Update subscription badge
        const subscriptionBadge = document.getElementById('subscription-badge');
        const subscriptionType = user['custom:subscription_type'] || 'guest';
        const planInfo = APP_CONFIG.subscriptionPlans[subscriptionType];
        
        if (subscriptionBadge && planInfo) {
            subscriptionBadge.textContent = planInfo.name;
            subscriptionBadge.className = `subscription-badge subscription-${subscriptionType}`;
        }

        // Show authenticated UI
        const authButtons = document.getElementById('auth-buttons');
        const userInfo = document.getElementById('user-info');
        const authSection = document.getElementById('auth-section');
        const videoLibrarySection = document.getElementById('video-library');
        
        if (authButtons) authButtons.style.display = 'none';
        if (userInfo) userInfo.style.display = 'flex';
        if (authSection) authSection.style.display = 'none';
        if (videoLibrarySection) videoLibrarySection.style.display = 'block';
        
        console.log('Auth UI updated successfully');
        
        // Show video library
        this.showLibrary();
    }

    handleLogout() {
        try {
            authManager.signOut();
            this.currentUser = null;
            this.showAuthSection();
        } catch (error) {
            console.error('Logout error:', error);
            this.showError('Logout failed');
        }
    }

    // Navigation Methods
    showLibrary() {
        this.hideAllSections();
        document.getElementById('video-library').style.display = 'block';
        this.currentSection = 'library';
        
        // Use the global video library instance
        if (typeof videoLibrary !== 'undefined' && videoLibrary) {
            this.videoLibrary = videoLibrary;
            console.log('Loading videos from showLibrary...');
            this.videoLibrary.loadVideos();
        } else {
            console.log('videoLibrary not available yet, will retry...');
            // Retry after a short delay if videoLibrary isn't ready
            setTimeout(() => {
                if (typeof videoLibrary !== 'undefined' && videoLibrary) {
                    this.videoLibrary = videoLibrary;
                    console.log('Loading videos after retry...');
                    this.videoLibrary.loadVideos();
                }
            }, 500);
        }
    }

    showPlayer() {
        this.hideAllSections();
        document.getElementById('video-player-section').style.display = 'block';
        this.currentSection = 'player';
    }

    hideAllSections() {
        const sections = [
            'auth-section',
            'video-library', 
            'video-player-section'
        ];
        
        sections.forEach(sectionId => {
            const section = document.getElementById(sectionId);
            if (section) section.style.display = 'none';
        });
    }

    // Utility Methods
    showLoading(message = 'Loading...') {
        // Create or update loading overlay
        let overlay = document.getElementById('loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'loading-overlay';
            overlay.className = 'loading-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            `;
            document.body.appendChild(overlay);
        }
        
        overlay.innerHTML = `
            <div class="loading-content" style="
                background: white;
                padding: 2rem;
                border-radius: 8px;
                text-align: center;
                color: #333;
            ">
                <div class="spinner" style="
                    width: 40px;
                    height: 40px;
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #007bff;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 1rem;
                "></div>
                <p>${message}</p>
            </div>
        `;
        overlay.style.display = 'flex';
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.setAttribute('role', 'alert');
        
        const container = document.getElementById('toast-container');
        if (container) {
            container.appendChild(toast);
            
            // Add click to dismiss
            toast.addEventListener('click', () => {
                toast.classList.add('removing');
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            });
            
            // Auto remove after 5 seconds
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.classList.add('removing');
                    setTimeout(() => {
                        if (toast.parentNode) {
                            toast.parentNode.removeChild(toast);
                        }
                    }, 300);
                }
            }, 5000);
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new VideoStreamingApp();
});

// Global error handler
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
    if (window.app) {
        window.app.showError('An unexpected error occurred. Please refresh the page.');
    }
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (e) => {
    console.error('Unhandled promise rejection:', e.reason);
    if (window.app) {
        window.app.showError('An unexpected error occurred. Please try again.');
    }
});
