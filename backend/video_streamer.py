import json
import boto3
import jwt
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from decimal import Decimal
import time
import hashlib
import hmac

# Initialize AWS clients
s3 = boto3.client('s3')
cognito = boto3.client('cognito-idp')
cloudfront = boto3.client('cloudfront')
dynamodb = boto3.resource('dynamodb')

# Get DynamoDB table
table_name = os.environ.get('DYNAMODB_TABLE_NAME')
table = dynamodb.Table(table_name) if table_name else None

def lambda_handler(event, context):
    """
    Lambda function to serve video content based on user subscription type
    Supports guest, standard, and premium subscription plans
    """
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # Extract user information from JWT token
        user_info = extract_user_info(event)
        if not user_info:
            return create_error_response(401, 'Invalid or missing authorization')
        
        # Get video ID from path parameters
        video_id = event['pathParameters'].get('videoId')
        if not video_id:
            return create_error_response(400, 'Video ID is required')
        
        # Get user subscription type
        subscription_type = get_user_subscription(user_info['username'])
        print(f"User {user_info['username']} has subscription type: {subscription_type}")
        
        # Get video metadata from DynamoDB
        video_metadata = get_video_metadata(video_id)
        if not video_metadata:
            return create_error_response(404, 'Video not found')
        
        if video_metadata['status'] != 'completed':
            return create_error_response(202, 'Video is still processing')
        
        # Generate appropriate video response based on subscription
        video_response = generate_video_response(video_id, subscription_type, user_info, video_metadata, event)
        
        # Convert any Decimal types to float for JSON serialization
        video_response = decimal_to_float(video_response)
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'OPTIONS,GET',
                'Content-Type': 'application/json'
            },
            'body': json.dumps(video_response)
        }
        
    except Exception as e:
        print(f"Error in video streaming: {str(e)}")
        return create_error_response(500, f'Internal server error: {str(e)}')

def extract_user_info(event):
    """Extract user information from JWT token"""
    try:
        headers = event.get('headers', {})
        print(f"Request headers: {headers}")
        
        auth_header = headers.get('Authorization', '') or headers.get('authorization', '')
        if not auth_header.startswith('Bearer '):
            print(f"Invalid authorization header: {auth_header}")
            return None
        
        token = auth_header.split(' ')[1]
        print(f"Extracted token: {token[:50]}...")
        
        # Decode JWT token without signature verification (for development)
        # In production, you should verify the signature properly
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        print(f"Decoded token: {decoded_token}")
        
        user_info = {
            'username': decoded_token.get('cognito:username'),
            'email': decoded_token.get('email'),
            'sub': decoded_token.get('sub')
        }
        print(f"Extracted user info: {user_info}")
        
        return user_info
    except Exception as e:
        print(f"Error extracting user info: {str(e)}")
        return None

def get_user_subscription(username):
    """Get user subscription type from Cognito"""
    try:
        user_pool_id = os.environ['USER_POOL_ID']
        
        response = cognito.admin_get_user(
            UserPoolId=user_pool_id,
            Username=username
        )
        
        # Look for custom subscription_type attribute
        subscription_type = None
        for attr in response['UserAttributes']:
            if attr['Name'] == 'custom:subscription_type':
                subscription_type = attr['Value']
                break
        
        print(f"Found subscription_type for {username}: {subscription_type}")
        
        # Map old subscription types to new ones for backward compatibility
        if subscription_type == 'trial':
            return 'free'
        elif subscription_type == 'saving':
            return 'standard'
        elif subscription_type == 'guest':
            return 'free'
        elif subscription_type in ['free', 'standard', 'premium']:
            return subscription_type
        else:
            # If no valid subscription type found, default to free for security
            print(f"No valid subscription type found for {username}, defaulting to free")
            return 'free'
        
    except ClientError as e:
        print(f"Error getting user subscription: {str(e)}")
        # Default to free for security purposes
        return 'free'

def get_video_metadata(video_id):
    """Get video metadata from DynamoDB"""
    try:
        if not table:
            print("DynamoDB table not configured")
            return None
            
        print(f"Looking up video metadata for video_id: {video_id}")
        response = table.get_item(
            Key={'videoId': video_id}
        )
        
        item = response.get('Item')
        if item:
            print(f"Found video metadata: {item}")
        else:
            print(f"No video found with ID: {video_id}")
        
        return item
        
    except Exception as e:
        print(f"Error getting video metadata for {video_id}: {str(e)}")
        return None

def generate_video_response(video_id, subscription_type, user_info, video_metadata, event=None):
    """Generate video response based on subscription type"""
    
    cloudfront_domain = os.environ['CLOUDFRONT_DOMAIN']
    
    # Get video URLs from metadata
    video_urls = video_metadata.get('videoUrls', {})
    
    # Determine which video URL to use based on subscription
    video_url = None
    quality = None
    max_duration = None
    
    print(f"Available video URLs: {video_urls}")
    
    if subscription_type == 'free':
        video_url = video_urls.get('free')
        quality = '480p'
        max_duration = 10  # 10 seconds for free users
        print(f"Free user - using video_url: {video_url}")
    elif subscription_type == 'standard':
        video_url = video_urls.get('standard')
        quality = '480p'
        max_duration = None  # Full video
        print(f"Standard user - using video_url: {video_url}")
    elif subscription_type == 'premium':
        # Premium users can choose quality, default to 720p
        requested_quality = '720p'
        if event and event.get('queryStringParameters'):
            requested_quality = event['queryStringParameters'].get('quality', '720p')
        
        if requested_quality == '1080p':
            video_url = video_urls.get('premium_1080p')
            quality = '1080p'
        elif requested_quality == '480p':
            video_url = video_urls.get('standard')  # Use standard 480p version
            quality = '480p'
        else:  # Default to 720p
            video_url = video_urls.get('premium_720p')
            quality = '720p'
        max_duration = None  # Full video
    
    if not video_url:
        raise Exception(f"Video not available for subscription type: {subscription_type}")
    
    # Generate signed URL for CloudFront for all users
    signed_url = generate_cloudfront_signed_url(video_url, subscription_type)
    
    # Prepare response based on subscription type
    response = {
        'videoId': video_id,
        'title': video_metadata.get('title', 'Untitled Video'),
        'description': video_metadata.get('description', ''),
        'thumbnail': video_metadata.get('thumbnailUrl', ''),
        'duration': float(video_metadata.get('duration', 0)) if video_metadata.get('duration') else 0,
        'subscriptionType': subscription_type,
        'videoUrl': signed_url,
        'quality': quality,
        'maxDuration': max_duration,
        'availableQualities': get_available_qualities(subscription_type),
        'user': user_info['username']
    }
    
    # Add subscription-specific features
    if subscription_type == 'free':
        response['features'] = {
            'maxDuration': 10
        }
    elif subscription_type == 'standard':
        response['features'] = {
            'fullAccess': True
        }
    elif subscription_type == 'premium':
        response['features'] = {
            'fullAccess': True,
            'qualitySelection': True
        }
    
    return response

def get_available_qualities(subscription_type):
    """Get available video qualities based on subscription type"""
    if subscription_type == 'free':
        return ['480p']
    elif subscription_type == 'standard':
        return ['480p']
    elif subscription_type == 'premium':
        return ['480p', '720p', '1080p']  # Premium users can see all qualities
    else:
        return ['480p']

def generate_cloudfront_signed_url(video_url, subscription_type):
    """Generate CloudFront signed URL with appropriate expiration"""
    try:
        # Set different expiration times based on subscription
        if subscription_type == 'free':
            # Short expiration for free users to limit access
            expiration_time = datetime.utcnow() + timedelta(minutes=15)
        else:
            # Longer expiration for paying users
            expiration_time = datetime.utcnow() + timedelta(hours=2)
        
        # This is a simplified version - in production you'd use proper CloudFront signing
        return video_url + f"?expires={int(expiration_time.timestamp())}"
        
    except Exception as e:
        print(f"Error generating signed URL: {str(e)}")
        return video_url


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: decimal_to_float(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj

def generate_validation_token(username, video_id, max_duration):
    """Generate a validation token for time-limited access"""
    secret = os.environ.get('JWT_SECRET', 'default-secret')
    timestamp = int(time.time())
    data = f"{username}:{video_id}:{max_duration}:{timestamp}"
    token = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}:{token}"

def create_error_response(status_code, message):
    """Create standardized error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'OPTIONS,GET',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.utcnow().isoformat()
        })
    }
