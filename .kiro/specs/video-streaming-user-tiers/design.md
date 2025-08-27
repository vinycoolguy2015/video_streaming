# Design Document

## Overview

This design document outlines the architecture and implementation approach for updating the existing video streaming platform to support a three-tier user subscription system (Free, Standard, Premium) with manual video upload workflow and automated transcoding. The design leverages the existing AWS infrastructure while making targeted modifications to support the new user tier requirements.

## Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway    │    │   Lambda        │
│   (JavaScript)  │◄──►│   (REST API)     │◄──►│   Functions     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                                               │
         ▼                                               ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFront    │    │   Amazon S3      │    │   MediaConvert  │
│   (CDN)         │◄──►│   (Storage)      │◄──►│   (Processing)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   End Users     │    │   Amazon Cognito │    │   DynamoDB      │
│   (Streaming)   │    │   (Auth)         │    │   (Metadata)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Updated User Tier System

| Tier | Duration | Quality | Features |
|------|----------|---------|----------|
| Free | 10 seconds | 480p | Preview only, upgrade prompts |
| Standard | Full video | 480p | Complete access, single quality |
| Premium | Full video | 720p/1080p | Complete access, quality selection |

## Components and Interfaces

### 1. Authentication System (Cognito)

**Current State:** Already implemented with custom subscription attributes
**Required Changes:** Update subscription type values and validation

```javascript
// Updated subscription types
const SUBSCRIPTION_TYPES = {
    FREE: 'free',
    STANDARD: 'standard', 
    PREMIUM: 'premium'
};
```

**Interface Updates:**
- Modify signup flow to use new subscription types
- Update user attribute validation
- Maintain backward compatibility during transition

### 2. Video Processing Pipeline (EventBridge + MediaConvert)

**Current State:** Creates trial (15s), saving (720p), premium (1080p) versions
**Required Changes:** Update to create free (10s), standard (480p), premium (720p/1080p) versions with EventBridge-driven completion handling

**New Architecture:**
1. **Video Upload** → S3 triggers video processor Lambda
2. **Job Creation** → Lambda creates MediaConvert job (no DynamoDB operations)
3. **Processing** → MediaConvert processes video in background
4. **Completion Event** → MediaConvert sends EventBridge event on completion
5. **Metadata Update** → EventBridge triggers completion handler Lambda to update DynamoDB

```python
# Video Processor Lambda (simplified - only creates jobs)
def lambda_handler(event, context):
    # Parse S3 upload event
    # Create MediaConvert job for all quality tiers
    # Return job ID (no DynamoDB operations)
    
# MediaConvert Completion Handler Lambda (new)
def lambda_handler(event, context):
    # Parse EventBridge MediaConvert completion event
    # Update video metadata in DynamoDB with final URLs
    # Handle both success and error scenarios
```

**EventBridge Rule Configuration:**
```json
{
    "source": ["aws.mediaconvert"],
    "detail-type": ["MediaConvert Job State Change"],
    "detail": {
        "status": ["COMPLETE", "ERROR"]
    }
}
```

### 3. Video Streaming Service (Lambda)

**Current State:** Serves videos based on trial/saving/premium tiers
**Required Changes:** Update logic for free/standard/premium access control

```python
def get_video_url(video_id, user_subscription, quality_preference=None):
    """
    Returns appropriate video URL based on user subscription
    """
    if user_subscription == 'free':
        return get_preview_url(video_id)  # 10-second preview
    elif user_subscription == 'standard':
        return get_standard_url(video_id)  # 480p full video
    elif user_subscription == 'premium':
        if quality_preference in ['720p', '1080p']:
            return get_premium_url(video_id, quality_preference)
        return get_premium_url(video_id, '720p')  # Default to 720p
    else:
        raise ValueError("Invalid subscription type")
```

### 4. Frontend Video Player

**Current State:** Handles trial limitations and ad insertion
**Required Changes:** Update for 10-second free preview and quality selection

```javascript
class VideoPlayer {
    constructor(videoElement, userSubscription) {
        this.video = videoElement;
        this.subscription = userSubscription;
        this.previewLimit = 10; // seconds for free users
    }
    
    handleTimeUpdate() {
        if (this.subscription === 'free' && this.video.currentTime >= this.previewLimit) {
            this.video.pause();
            this.showUpgradeModal();
        }
    }
    
    showQualitySelector() {
        if (this.subscription === 'premium') {
            // Show 720p/1080p options
            return ['720p', '1080p'];
        }
        return []; // No quality selection for free/standard
    }
}
```

### 5. Configuration Management

**Current State:** Supports trial/saving/premium configuration
**Required Changes:** Update to free/standard/premium with new limits

```javascript
const APP_CONFIG = {
    subscriptionPlans: {
        free: {
            name: 'Free',
            description: '10 seconds preview',
            features: ['Basic quality', '10-second previews', 'No ads'],
            maxDuration: 10,
            quality: '480p',
            price: 'Free'
        },
        standard: {
            name: 'Standard',
            description: 'Full videos in standard quality',
            features: ['Standard quality', 'Full content', 'No ads'],
            maxDuration: null,
            quality: '480p',
            price: '$4.99/month'
        },
        premium: {
            name: 'Premium',
            description: 'Full videos with HD quality options',
            features: ['HD quality options', 'Full content', 'No ads', 'Quality selection'],
            maxDuration: null,
            quality: ['720p', '1080p'],
            price: '$9.99/month'
        }
    }
};
```

## Data Models

### 1. User Model (Cognito)

```json
{
    "username": "user@example.com",
    "email": "user@example.com", 
    "custom:subscription_type": "free|standard|premium",
    "email_verified": true,
    "created_date": "2024-01-01T00:00:00Z"
}
```

### 2. Video Metadata Model (DynamoDB)

```json
{
    "videoId": "uuid-string",
    "title": "Video Title",
    "originalFilename": "video.mp4",
    "s3Key": "uploads/video.mp4",
    "status": "processing|completed|failed",
    "uploadDate": "2024-01-01T00:00:00Z",
    "duration": 120,
    "fileSize": 50000000,
    "availableQualities": ["480p", "720p", "1080p"],
    "videoUrls": {
        "free": "https://cdn.example.com/free/video_preview.mp4",
        "standard": "https://cdn.example.com/standard/video_480p.mp4", 
        "premium_720p": "https://cdn.example.com/premium/video_720p.mp4",
        "premium_1080p": "https://cdn.example.com/premium/video_1080p.mp4"
    },
    "thumbnailUrl": "https://cdn.example.com/thumbnails/video.jpg",
    "mediaConvertJobId": "job-id-string"
}
```

### 3. MediaConvert Job Configuration

```json
{
    "jobId": "mediaconvert-job-id",
    "inputUri": "s3://bucket/uploads/video.mp4",
    "outputBucket": "s3://bucket/processed/",
    "status": "submitted|progressing|complete|error",
    "outputs": [
        {
            "type": "free_preview",
            "duration": 10,
            "quality": "480p",
            "outputUri": "s3://bucket/processed/free/video_preview.mp4"
        },
        {
            "type": "standard",
            "duration": "full", 
            "quality": "480p",
            "outputUri": "s3://bucket/processed/standard/video_480p.mp4"
        },
        {
            "type": "premium_720p",
            "duration": "full",
            "quality": "720p", 
            "outputUri": "s3://bucket/processed/premium/video_720p.mp4"
        },
        {
            "type": "premium_1080p",
            "duration": "full",
            "quality": "1080p",
            "outputUri": "s3://bucket/processed/premium/video_1080p.mp4"
        }
    ]
}
```

### 3. EventBridge Integration (New Component)

**Purpose:** Decouple video processing from metadata management
**Implementation:** EventBridge rule captures MediaConvert job state changes

```python
# EventBridge Event Pattern
{
    "source": ["aws.mediaconvert"],
    "detail-type": ["MediaConvert Job State Change"],
    "detail": {
        "status": ["COMPLETE", "ERROR"],
        "jobId": [{"exists": true}]
    }
}

# Completion Handler Lambda
def handle_job_completion(job_id, detail):
    # Find video by MediaConvert job ID
    # Update DynamoDB with final video URLs and status
    # Handle thumbnail URL generation
    # Set completion timestamp
    
def handle_job_error(job_id, detail):
    # Update video status to 'failed'
    # Log error details from MediaConvert
    # Set error timestamp and message
```

**Benefits:**
- **Decoupled Architecture**: Job creation and metadata updates are independent
- **Reliability**: EventBridge ensures completion events are processed
- **Scalability**: Can handle multiple concurrent video processing jobs
- **Error Resilience**: Metadata operations don't affect job creation

## Error Handling

### 1. Video Processing Errors (Updated)

```python
# MediaConvert Completion Handler
def handle_job_error(job_id, detail):
    """
    Handle MediaConvert job failures via EventBridge events
    """
    try:
        # Extract error information from EventBridge event
        error_message = detail.get('errorMessage', 'Unknown error')
        error_code = detail.get('errorCode', 'UNKNOWN_ERROR')
        
        # Find and update video metadata
        video = find_video_by_job_id(job_id)
        if video:
            update_video_metadata(video['videoId'], {
                'status': 'failed',
                'errorMessage': error_message,
                'errorCode': error_code,
                'errorDate': datetime.utcnow().isoformat()
            })
            
        # Log for monitoring and alerting
        logger.error(f"MediaConvert job {job_id} failed: {error_message}")
            
    except Exception as e:
        logger.error(f"Error handling MediaConvert failure: {str(e)}")
```

### 2. Authentication Errors

```javascript
function handleAuthError(error) {
    const errorMessages = {
        'NotAuthorizedException': 'Invalid email or password',
        'UserNotConfirmedException': 'Please verify your email address',
        'UserNotFoundException': 'Account not found',
        'TokenExpiredException': 'Session expired, please log in again'
    };
    
    const message = errorMessages[error.code] || 'Authentication failed';
    showErrorMessage(message);
    
    if (error.code === 'TokenExpiredException') {
        redirectToLogin();
    }
}
```

### 3. Video Streaming Errors

```javascript
function handleStreamingError(error, videoElement) {
    console.error('Video streaming error:', error);
    
    const errorOverlay = document.createElement('div');
    errorOverlay.className = 'video-error-overlay';
    errorOverlay.innerHTML = `
        <div class="error-message">
            <h3>Video Unavailable</h3>
            <p>This video is currently unavailable. Please try again later.</p>
            <button onclick="retryVideo()">Retry</button>
        </div>
    `;
    
    videoElement.parentNode.appendChild(errorOverlay);
}
```

## Testing Strategy

### 1. Unit Testing

**Authentication Tests:**
- Test signup with different subscription types
- Test login/logout functionality
- Test token validation and refresh
- Test subscription type retrieval

**Video Processing Tests:**
- Test MediaConvert job creation for each tier
- Test video metadata storage and retrieval
- Test error handling for failed jobs
- Test thumbnail generation

**Streaming Tests:**
- Test video URL generation for each subscription tier
- Test access control enforcement
- Test quality selection for premium users
- Test preview limitation for free users

### 2. Integration Testing

**End-to-End Workflow Tests:**
- Upload video → Process → Stream for each user tier
- User signup → Login → Video access workflow
- Subscription upgrade → Immediate access change
- Video processing failure → Error handling → Retry

**API Testing:**
- Test all API endpoints with different user roles
- Test authentication middleware
- Test rate limiting and error responses
- Test CORS configuration

### 3. Performance Testing

**Load Testing:**
- Concurrent video streaming for multiple users
- Multiple video uploads and processing
- Authentication system under load
- Database query performance

**Stress Testing:**
- Maximum concurrent MediaConvert jobs
- CloudFront CDN performance
- Lambda function cold start times
- DynamoDB read/write capacity

### 4. Security Testing

**Authentication Security:**
- JWT token validation and expiration
- Session management and logout
- Password policy enforcement
- Email verification workflow

**Access Control Testing:**
- Verify users can only access their tier content
- Test unauthorized access attempts
- Verify signed URL security
- Test API authorization

## Migration Strategy

### Phase 1: Backend Updates (No User Impact)

1. **Update MediaConvert Configuration**
   - Modify video processing to create new quality tiers
   - Update output folder structure
   - Maintain backward compatibility with existing videos

2. **Update Lambda Functions**
   - Modify video streaming logic for new tiers
   - Update authentication checks
   - Add quality selection support

3. **Database Schema Updates**
   - Add new subscription types to validation
   - Update video metadata structure
   - Migrate existing user subscriptions

### Phase 2: Frontend Updates (Gradual Rollout)

1. **Update Configuration**
   - Change subscription plan definitions
   - Update UI text and descriptions
   - Add quality selector component

2. **Update Video Player**
   - Implement 10-second preview limitation
   - Add quality selection for premium users
   - Update upgrade prompts and messaging

3. **Update Authentication Flow**
   - Modify signup form for new subscription types
   - Update user profile display
   - Add subscription management features

### Phase 3: Testing and Validation

1. **User Acceptance Testing**
   - Test all user flows with new subscription tiers
   - Validate video quality and access controls
   - Test upgrade/downgrade scenarios

2. **Performance Validation**
   - Monitor video processing times
   - Validate streaming performance
   - Check database query performance

3. **Security Validation**
   - Verify access control enforcement
   - Test authentication security
   - Validate signed URL generation

### Phase 4: Production Deployment

1. **Gradual User Migration**
   - Migrate existing users to new subscription types
   - Communicate changes to users
   - Provide support for transition period

2. **Monitoring and Support**
   - Monitor system performance and errors
   - Provide user support for new features
   - Collect feedback and iterate

## Deployment Considerations

### Infrastructure Updates

1. **CloudFormation Templates**
   - Add EventBridge rule for MediaConvert job state changes
   - Create new MediaConvert completion handler Lambda function
   - Update MediaConvert job configuration for new quality tiers
   - Remove DynamoDB permissions from video processor Lambda
   - Add DynamoDB permissions to completion handler Lambda

2. **Lambda Functions**
   - **video_processor.py**: Simplified to only create MediaConvert jobs
   - **mediaconvert_completion_handler.py**: New function to handle job completion events
   - Update deployment script to package both Lambda functions

3. **Configuration Management**
   - Update frontend configuration files
   - Modify API Gateway settings
   - Update CloudFront cache behaviors

### Data Migration

1. **User Subscription Migration**
   ```python
   # Migration script for existing users
   def migrate_user_subscriptions():
       # trial -> free
       # saving -> standard  
       # premium -> premium (no change)
       pass
   ```

2. **Video Metadata Migration**
   ```python
   # Update existing video records
   def migrate_video_metadata():
       # Update video URLs for new tier structure
       # Regenerate missing quality versions if needed
       pass
   ```

### Rollback Strategy

1. **Configuration Rollback**
   - Maintain previous configuration versions
   - Quick rollback capability for frontend changes
   - Database migration rollback scripts

2. **Feature Flags**
   - Use feature flags for gradual rollout
   - Ability to disable new features quickly
   - A/B testing capability for user experience

This design provides a comprehensive approach to updating the existing video streaming platform while maintaining system stability and user experience during the transition.