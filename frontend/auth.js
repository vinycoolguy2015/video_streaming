class AuthManager {
    constructor() {
        this.userPool = null;
        this.currentUser = null;
        this.cognitoUser = null;
        // Don't initialize immediately - wait for init() to be called
    }

    init() {
        try {
            // Initialize the Cognito user pool with our config
            this.userPool = new AmazonCognitoIdentity.CognitoUserPool({
                UserPoolId: AWS_CONFIG.cognito.userPoolId,
                ClientId: AWS_CONFIG.cognito.userPoolWebClientId
            });

            // Check authentication state
            this.checkAuthState();
            return true;
        } catch (error) {
            console.error('Error initializing AuthManager:', error);
            return false;
        }
    }

    checkAuthState() {
        console.log('Checking authentication state...');
        const cognitoUser = this.userPool.getCurrentUser();
        
        if (cognitoUser != null) {
            cognitoUser.getSession((err, session) => {
                if (err) {
                    console.log('Session error:', err);
                    this.handleLogout();
                    return;
                }
                
                if (session.isValid()) {
                    console.log('Valid session found');
                    this.cognitoUser = cognitoUser;
                    
                    // Get user attributes
                    this.getUserAttributes((userInfo) => {
                        console.log('User attributes retrieved:', userInfo);
                        this.currentUser = userInfo;
                        this.updateUI(true);
                        
                        // Load videos if we have a valid session
                        if (typeof videoLibrary !== 'undefined' && videoLibrary.loadVideos) {
                            console.log('Loading videos...');
                            videoLibrary.loadVideos().catch(error => {
                                console.error('Error loading videos:', error);
                            });
                        }
                    });
                } else {
                    console.log('Invalid session');
                    this.handleLogout();
                }
            });
        } else {
            console.log('No authenticated user');
            this.updateUI(false);
        }
    }

    signUp(email, password, attributes = {}) {
        return new Promise((resolve, reject) => {
            const attributeList = [];
            
            // Add standard attributes
            attributeList.push(new AmazonCognitoIdentity.CognitoUserAttribute({
                Name: 'email',
                Value: email
            }));
            
            // Add custom attributes
            Object.keys(attributes).forEach(key => {
                attributeList.push(new AmazonCognitoIdentity.CognitoUserAttribute({
                    Name: 'custom:' + key,
                    Value: attributes[key]
                }));
            });
            
            this.userPool.signUp(email, password, attributeList, null, (err, result) => {
                if (err) {
                    console.error('Signup error:', err);
                    resolve({
                        success: false,
                        error: err.message || 'Could not create account'
                    });
                    return;
                }
                
                // Store the user for verification
                this.cognitoUser = result.user;
                console.log('User signed up successfully, stored for verification');
                
                resolve({
                    success: true,
                    user: result.user
                });
            });
        });
    }

    confirmSignUp(code) {
        return new Promise((resolve, reject) => {
            if (!this.cognitoUser) {
                console.error('No user to confirm - cognitoUser is null');
                resolve({
                    success: false,
                    error: 'No user to confirm. Please sign up again.'
                });
                return;
            }
            
            this.cognitoUser.confirmRegistration(code, true, (err, result) => {
                if (err) {
                    console.error('Verification error:', err);
                    resolve({
                        success: false,
                        error: err.message || 'Could not verify account'
                    });
                    return;
                }
                
                console.log('User verification successful');
                resolve({
                    success: true
                });
            });
        });
    }

    resendVerificationCode() {
        return new Promise((resolve, reject) => {
            if (!this.cognitoUser) {
                resolve({
                    success: false,
                    error: 'No user to resend code to. Please sign up again.'
                });
                return;
            }
            
            this.cognitoUser.resendConfirmationCode((err, result) => {
                if (err) {
                    console.error('Resend verification error:', err);
                    resolve({
                        success: false,
                        error: err.message || 'Could not resend verification code'
                    });
                    return;
                }
                
                resolve({
                    success: true,
                    message: 'Verification code sent to your email'
                });
            });
        });
    }

    signIn(email, password) {
        return new Promise((resolve, reject) => {
            const authData = {
                Username: email,
                Password: password
            };
            
            const authDetails = new AmazonCognitoIdentity.AuthenticationDetails(authData);
            
            const userData = {
                Username: email,
                Pool: this.userPool
            };
            
            this.cognitoUser = new AmazonCognitoIdentity.CognitoUser(userData);
            
            this.cognitoUser.authenticateUser(authDetails, {
                onSuccess: (result) => {
                    console.log('Authentication successful');
                    
                    // Get user attributes and return them with the success response
                    this.getUserAttributes((userInfo) => {
                        this.currentUser = userInfo;
                        this.updateUI(true);
                        resolve({
                            success: true,
                            user: userInfo
                        });
                    });
                },
                onFailure: (err) => {
                    console.error('Authentication failed:', err);
                    
                    // Provide user-friendly error messages
                    let errorMessage = 'Login failed. Please try again.';
                    
                    if (err.code === 'NotAuthorizedException') {
                        errorMessage = 'Incorrect email or password. Please try again.';
                    } else if (err.code === 'UserNotConfirmedException') {
                        errorMessage = 'Please verify your email address before logging in.';
                    } else if (err.code === 'UserNotFoundException') {
                        errorMessage = 'Account not found. Please check your email address.';
                    }
                    
                    resolve({
                        success: false,
                        error: errorMessage
                    });
                }
            });
        });
    }

    signOut() {
        if (this.cognitoUser) {
            this.cognitoUser.signOut();
        }
        this.cognitoUser = null;
        this.currentUser = null;
        this.updateUI(false);
    }

    getUserAttributes(callback) {
        if (!this.cognitoUser) {
            callback(null);
            return;
        }

        this.cognitoUser.getUserAttributes((err, attributes) => {
            if (err) {
                console.error('Error getting user attributes:', err);
                callback(null);
                return;
            }

            const userInfo = {};
            attributes.forEach(attribute => {
                userInfo[attribute.getName()] = attribute.getValue();
            });

            userInfo.username = this.cognitoUser.getUsername();
            callback(userInfo);
        });
    }

    getCurrentSession() {
        return new Promise((resolve, reject) => {
            if (!this.cognitoUser) {
                reject(new Error('No authenticated user'));
                return;
            }

            this.cognitoUser.getSession((err, session) => {
                if (err) {
                    reject(err);
                    return;
                }

                if (session.isValid()) {
                    resolve(session);
                } else {
                    reject(new Error('Session is not valid'));
                }
            });
        });
    }

    getToken() {
        return new Promise((resolve, reject) => {
            if (!this.cognitoUser) {
                resolve(null);
                return;
            }
            
            this.cognitoUser.getSession((err, session) => {
                if (err || !session || !session.isValid()) {
                    resolve(null);
                } else {
                    resolve(session.getIdToken().getJwtToken());
                }
            });
        });
    }

    isTokenValid(token) {
        if (!token) return false;
        
        try {
            // Simple JWT validation - check if it's not expired
            const payload = JSON.parse(atob(token.split('.')[1]));
            const expirationTime = payload.exp * 1000; // Convert to milliseconds
            return Date.now() < expirationTime;
        } catch (error) {
            console.error('Token validation error:', error);
            return false;
        }
    }

    getCurrentUser() {
        return this.currentUser;
    }

    getUserSubscriptionType() {
        if (this.currentUser && this.currentUser['custom:subscription_type']) {
            const subscription = this.currentUser['custom:subscription_type'];
            // Map old subscription types to new ones for backward compatibility
            if (subscription === 'trial' || subscription === 'guest') {
                return 'free';
            } else if (subscription === 'saving') {
                return 'standard';
            }
            return subscription;
        }
        return 'free';
    }

    updateUI(isAuthenticated) {
        const authSection = document.getElementById('auth-section');
        const videoSection = document.getElementById('video-section');
        const userName = document.getElementById('user-name');
        const subscriptionBadge = document.getElementById('subscription-badge');

        if (isAuthenticated && this.currentUser) {
            // Show video section, hide auth forms
            if (authSection) authSection.style.display = 'none';
            if (videoSection) videoSection.style.display = 'block';
            
            // Update user info
            if (userName) {
                userName.textContent = this.currentUser.email || this.currentUser.username;
            }
            
            if (subscriptionBadge) {
                const subscriptionType = this.getUserSubscriptionType();
                subscriptionBadge.textContent = subscriptionType;
                subscriptionBadge.className = `subscription-badge ${subscriptionType}`;
            }
            
            // Show user info section
            document.getElementById('auth-buttons').style.display = 'none';
            document.getElementById('user-info').style.display = 'flex';
        } else {
            // Show auth section, hide video section
            if (authSection) authSection.style.display = 'flex';
            if (videoSection) videoSection.style.display = 'none';
            
            // Show auth buttons, hide user info
            document.getElementById('auth-buttons').style.display = 'flex';
            document.getElementById('user-info').style.display = 'none';
        }
    }
}

// Create global instance
window.authManager = new AuthManager();
