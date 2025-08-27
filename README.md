# Video Streaming App with User Tiers

A serverless video streaming application built on AWS with multiple subscription tiers (Free, Standard, Premium) and automatic video processing.

## Architecture Overview

This application uses a serverless architecture with the following AWS services:
- **S3**: Video storage (uploads, processed content, web hosting)
- **CloudFront**: Content delivery network
- **MediaConvert**: Video processing and transcoding
- **Lambda**: Serverless compute for video processing and API endpoints
- **API Gateway**: RESTful API for video streaming
- **Cognito**: User authentication and authorization
- **DynamoDB**: Video metadata storage

## Project Structure

```
├── backend/                    # Lambda function source code
│   ├── video_processor.py     # MediaConvert job creation
│   ├── mediaconvert_completion_handler.py  # Job completion handling
│   ├── video_streamer.py      # Video streaming API
│   ├── video_lister.py        # Video listing API
│   └── requirements.txt       # Python dependencies
├── cloudformation/            # Infrastructure as Code
│   ├── 00-lambda-deployment-bucket.yaml  # S3 bucket for Lambda packages
│   ├── 01-cognito-auth.yaml             # User authentication
│   ├── 02-storage-processing.yaml       # Storage, processing & database
│   └── 04-api-backend.yaml              # API Gateway and Lambda functions
├── frontend/                  # Web application
│   ├── index.html            # Main application page
│   ├── config.js             # AWS configuration
│   ├── auth.js               # Authentication logic
│   ├── app.js                # Main application logic
│   ├── player.js             # Video player functionality
│   ├── video-list.js         # Video listing functionality
│   └── styles.css            # Application styling
└── deploy.sh                 # Deployment script
```

## CloudFormation Stack Architecture

### 1. Lambda Deployment Bucket (`00-lambda-deployment-bucket.yaml`)
- **Purpose**: Stores Lambda deployment packages
- **Resources**: S3 bucket with versioning enabled (`videostreamingapp-lambda-deployments-{account-id}`)
- **Dependencies**: None

### 2. Cognito Authentication (`01-cognito-auth.yaml`)
- **Purpose**: User authentication and authorization
- **Resources**: 
  - Cognito User Pool with custom attributes
  - User Pool Client
  - Identity Pool for AWS resource access
- **Dependencies**: None

### 3. Storage & Processing (`02-storage-processing.yaml`) - **MERGED STACK**
- **Purpose**: Complete storage, processing, and database infrastructure
- **Resources**:
  - **DynamoDB**: Video metadata table with GSI indexes
  - **S3 Buckets**: 
  - Upload: `videostreamingapp-video-uploads-{account-id}`
  - Content: `videostreamingapp-video-content-{account-id}`
  - Web: `videostreamingapp-web-{account-id}`
  - **CloudFront**: CDN distribution with multiple cache behaviors
  - **MediaConvert**: Role and Lambda function for video processing
  - **S3 Event Notifications**: Automatic video processing triggers
- **Dependencies**: Lambda Deployment Bucket (for Lambda code)

### 4. API Backend (`04-api-backend.yaml`)
- **Purpose**: API Gateway and Lambda functions for video streaming
- **Resources**:
  - API Gateway with CORS support
  - Lambda functions for video streaming and listing
  - IAM roles and permissions
- **Dependencies**: All previous stacks (uses ImportValue)

## Deployment

### Prerequisites
- AWS CLI configured with appropriate permissions
- Python 3.9+ (for Lambda packaging)
- Bash shell (macOS/Linux)

### Quick Start
```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy all infrastructure
./deploy.sh deploy
```

### Deployment Process
The deployment script automatically:

1. **Creates Lambda Deployment Bucket**: Stores Lambda function packages
2. **Packages Lambda Functions**: 
   - Installs Python dependencies
   - Creates deployment packages
   - Uploads to S3
3. **Deploys CloudFormation Stacks** in order:
   - Cognito Authentication
   - Storage & Processing (merged)
   - API Backend
4. **Configures Frontend**: Updates configuration with deployed resources
5. **Uploads Frontend**: Deploys web application to S3/CloudFront

### Other Commands
```bash
# Clean up all resources
./deploy.sh cleanup

# Update frontend only
./deploy.sh frontend

# Debug failed deployments
./deploy.sh debug
```

## Lambda Function Architecture

### Event-Driven Processing
The application uses an **event-driven architecture** for video processing:

1. **Upload Event**: S3 triggers video processor Lambda
2. **Job Creation**: Video processor creates MediaConvert job (no database operations)
3. **Background Processing**: MediaConvert processes video asynchronously
4. **Completion Event**: MediaConvert sends EventBridge event on job completion
5. **Metadata Update**: EventBridge triggers completion handler to update DynamoDB

### EventBridge Integration
- **Event Source**: AWS MediaConvert
- **Event Types**: Job State Changes (COMPLETE, ERROR)
- **Target**: MediaConvert Completion Handler Lambda
- **Benefits**: Decoupled architecture, reliable event processing, better error handling

### External Code Deployment
All Lambda functions use **external code deployment** instead of inline code:

- **Source Code**: Located in `backend/` directory
- **Packaging**: Automatic dependency installation and ZIP creation
- **Storage**: S3-based deployment packages
- **Benefits**:
  - Better version control
  - Proper dependency management
  - Easier local testing
  - Cleaner CloudFormation templates

### Lambda Functions

#### 1. Video Processor (`video_processor.py`)
- **Trigger**: S3 upload events (*.mp4 files)
- **Purpose**: Creates MediaConvert jobs for video transcoding (no DynamoDB operations)
- **Output Formats**:
  - Free: 480p, 1Mbps, 10-second preview
  - Standard: 480p, 2Mbps, full video
  - Premium: 720p/1080p, 4-6Mbps, full video
  - Thumbnails: 320x180 JPEG

#### 2. MediaConvert Completion Handler (`mediaconvert_completion_handler.py`)
- **Trigger**: EventBridge events from MediaConvert job state changes
- **Purpose**: Updates video metadata when MediaConvert jobs complete or fail
- **Features**:
  - Handles COMPLETE and ERROR job statuses
  - Updates DynamoDB with final video URLs and thumbnails
  - Proper error logging and status tracking

#### 3. Video Streamer (`video_streamer.py`)
- **Trigger**: API Gateway requests
- **Purpose**: Serves video content based on user subscription
- **Features**:
  - JWT token validation
  - Subscription-based access control
  - CloudFront URL generation

#### 4. Video Lister (`video_lister.py`)
- **Trigger**: API Gateway requests
- **Purpose**: Lists available videos with pagination
- **Features**:
  - DynamoDB querying with GSI
  - Pagination support
  - Status filtering

## User Subscription Tiers

### Free Tier
- **Video Quality**: 480p
- **Duration Limit**: 10 seconds preview
- **Bitrate**: 1 Mbps

### Standard Tier
- **Video Quality**: 480p
- **Duration Limit**: Full video
- **Bitrate**: 2 Mbps

### Premium Tier
- **Video Quality**: 720p/1080p
- **Duration Limit**: Full video
- **Bitrate**: 4-6 Mbps

## API Endpoints

### Authentication Required
All API endpoints require Cognito JWT token in Authorization header:
```
Authorization: Bearer <jwt-token>
```

### Endpoints

#### Get Video Stream
```
GET /videos/stream/{videoId}
```
Returns video URL and metadata based on user subscription.

#### List Videos
```
GET /videos/list?page=1&limit=12&status=completed
```
Returns paginated list of available videos.

## Configuration

### Frontend Configuration (`frontend/config.js`)
Automatically updated during deployment with:
- AWS region
- Cognito User Pool details
- API Gateway URL
- CloudFront domain

### Environment Variables
Lambda functions receive environment variables for:
- S3 bucket names
- DynamoDB table names
- CloudFront domain
- MediaConvert role ARN

## Monitoring and Troubleshooting

### CloudWatch Logs
Each Lambda function creates its own log group:
- `/aws/lambda/VideoStreamingApp-MediaConvertJob` (video processor)
- `/aws/lambda/VideoStreamingApp-MediaConvertCompletion` (completion handler)
- `/aws/lambda/VideoStreamingApp-VideoStream` (video streaming API)
- `/aws/lambda/VideoStreamingApp-VideoList` (video listing API)

### Common Issues

#### Stack Deletion Problems
- **Solution**: Use the merged stack architecture to avoid ImportValue circular dependencies
- **Order**: API → Storage → Cognito → Lambda Deployment

#### Video Processing Failures
- **Check**: MediaConvert job status in AWS Console
- **Logs**: Review Lambda logs for MediaConvert errors
- **Permissions**: Verify MediaConvert role has S3 access

#### CORS Issues
- **Solution**: All Lambda functions include proper CORS headers
- **Preflight**: OPTIONS requests are handled automatically

## Security Features

- **Authentication**: Cognito-based user management
- **Authorization**: JWT token validation
- **S3 Security**: Private buckets with CloudFront OAC
- **API Security**: Cognito authorizer on API Gateway
- **IAM**: Least privilege access for all resources

## Cost Optimization

- **S3**: Intelligent tiering for cost optimization
- **CloudFront**: Price class 100 (US, Canada, Europe)
- **DynamoDB**: Pay-per-request billing
- **Lambda**: Optimized package sizes and timeouts
- **MediaConvert**: On-demand pricing

## Development

### Local Testing
```bash
# Install dependencies
pip install -r backend/requirements.txt

# Test Lambda functions locally
python backend/video_processor.py
```

### Adding New Features
1. Update Lambda functions in `backend/`
2. Modify CloudFormation templates if needed
3. Run `./deploy.sh deploy` to update infrastructure
4. Update frontend code and run `./deploy.sh frontend`

## Support

For issues and questions:
1. Check CloudWatch logs for Lambda errors
2. Use `./deploy.sh debug` for stack troubleshooting
3. Review AWS Console for resource status
4. Check IAM permissions for access issues