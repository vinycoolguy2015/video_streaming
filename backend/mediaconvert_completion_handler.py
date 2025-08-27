import json
import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Get DynamoDB table
table_name = os.environ.get('DYNAMODB_TABLE_NAME')
table = dynamodb.Table(table_name) if table_name else None

def lambda_handler(event, context):
    """
    Lambda function to handle MediaConvert job completion events from EventBridge
    Creates video metadata when jobs complete successfully or handles failures
    """
    try:
        print(f"Received EventBridge event: {json.dumps(event)}")
        
        # Parse EventBridge event
        detail = event.get('detail', {})
        job_id = detail.get('jobId')
        status = detail.get('status')
        
        if not job_id or not status:
            print(f"Missing required fields - jobId: {job_id}, status: {status}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields'})
            }
        
        print(f"Processing MediaConvert job completion: {job_id}, status: {status}")
        
        if status == 'COMPLETE':
            handle_job_completion(job_id, detail)
        elif status == 'ERROR':
            handle_job_error(job_id, detail)
        else:
            print(f"Unhandled job status: {status}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed job {job_id} with status {status}'
            })
        }
        
    except Exception as e:
        print(f"Error processing MediaConvert completion event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to process completion event: {str(e)}'
            })
        }

def handle_job_completion(job_id, detail):
    """
    Handle successful MediaConvert job completion
    Creates video record in DynamoDB with all metadata
    """
    try:
        # Extract filename directly from EventBridge event
        filename = extract_filename_from_event(detail)
        if not filename:
            print(f"Could not extract filename from event for job ID: {job_id}")
            return
        
        print(f"Processing completed job {job_id} for file: {filename}")
        
        # We don't need the original key/bucket since we have all output info
        original_key = f"{filename}.mp4"  # Reconstructed for reference
        input_bucket = "processed"  # Generic since we don't need it
        
        # Check if a video record already exists for this filename
        existing_video = find_existing_video_by_filename(filename)
        
        if existing_video:
            video_id = existing_video['videoId']
            print(f"Found existing video record: {video_id}")
        else:
            # Generate unique video ID for new video
            video_id = str(uuid.uuid4())
            print(f"Creating new video record: {video_id}")
        
        # Get output details from environment
        output_bucket = os.environ.get('OUTPUT_BUCKET')
        cloudfront_domain = os.environ.get('CLOUDFRONT_DOMAIN', '')
        
        # Determine which URLs to update based on job output
        job_type = get_job_type_from_detail(detail)
        
        # Start with existing URLs if video exists
        if existing_video:
            video_urls = existing_video.get('videoUrls', {})
        else:
            video_urls = {}
        
        # Update URLs based on job type
        if job_type == 'free':
            video_urls['free'] = f"https://{cloudfront_domain}/free/{filename}_free_480p.mp4"
        else:  # full job
            video_urls.update({
                'standard': f"https://{cloudfront_domain}/standard/{filename}_standard_480p.mp4", 
                'premium_720p': f"https://{cloudfront_domain}/premium/{filename}_premium_720p.mp4",
                'premium_1080p': f"https://{cloudfront_domain}/premium/{filename}_premium_1080p.mp4"
            })
        
        # Extract actual thumbnail URL from job output if available
        thumbnail_url = extract_thumbnail_url_from_event(detail, cloudfront_domain, filename)
        
        # Get video duration from MediaConvert job details if available
        duration = extract_duration_from_job_detail(detail)
        
        # Create or update video record
        if existing_video:
            # Update existing record
            video_record = existing_video.copy()
            video_record['videoUrls'] = video_urls
            video_record['mediaConvertJobId'] = f"{existing_video.get('mediaConvertJobId', '')},{job_id}"
            video_record['completedDate'] = datetime.utcnow().isoformat()
            
            # Update thumbnail URL if this is the full job
            if job_type == 'full':
                video_record['thumbnailUrl'] = thumbnail_url
        else:
            # Create new record
            video_record = {
                'videoId': video_id,
                'originalFilename': filename,
                'originalKey': original_key,
                'inputBucket': input_bucket,
                'mediaConvertJobId': job_id,
                'status': 'completed',
                'videoUrls': video_urls,
                'thumbnailUrl': thumbnail_url,
                'availableQualities': ['480p', '720p', '1080p'],
                'uploadDate': datetime.utcnow().isoformat(),
                'completedDate': datetime.utcnow().isoformat(),
                'title': filename.replace('_', ' ').replace('-', ' ').title(),
                'description': f"Video processed from {original_key}"
            }
        
        if duration:
            video_record['duration'] = Decimal(str(duration))
        
        # Create video record in DynamoDB
        create_video_record(video_record)
        
        print(f"Successfully created video record for completed job: {job_id}, video_id: {video_id}")
        
    except Exception as e:
        print(f"Error handling job completion: {str(e)}")
        raise

def handle_job_error(job_id, detail):
    """
    Handle failed MediaConvert job
    Creates video record with error status
    """
    try:
        # Extract filename directly from EventBridge event (if available in error case)
        filename = extract_filename_from_event(detail)
        if not filename:
            # For failed jobs, we might not have output details, so use job ID as fallback
            filename = f"failed_job_{job_id}"
            print(f"Could not extract filename from event for failed job ID: {job_id}, using fallback")
        
        print(f"Processing failed job {job_id} for file: {filename}")
        
        # Generic values for failed jobs
        original_key = f"{filename}.mp4"
        input_bucket = "failed"
        
        # Generate unique video ID
        video_id = str(uuid.uuid4())
        
        # Extract error information from the event detail
        error_message = detail.get('errorMessage', 'Unknown error')
        error_code = detail.get('errorCode', 'UNKNOWN_ERROR')
        
        # Create video record with error status
        video_record = {
            'videoId': video_id,
            'originalFilename': filename,
            'originalKey': original_key,
            'inputBucket': input_bucket,
            'mediaConvertJobId': job_id,
            'status': 'failed',
            'uploadDate': datetime.utcnow().isoformat(),
            'errorDate': datetime.utcnow().isoformat(),
            'errorMessage': error_message,
            'errorCode': error_code,
            'title': filename.replace('_', ' ').replace('-', ' ').title(),
            'description': f"Failed to process video from {original_key}"
        }
        
        # Create video record in DynamoDB
        create_video_record(video_record)
        
        print(f"Created video record for failed job: {job_id}, video_id: {video_id}, error: {error_message}")
        
    except Exception as e:
        print(f"Error handling job error: {str(e)}")
        raise



def find_existing_video_by_filename(filename):
    """
    Find existing video record by original filename
    """
    try:
        if not table:
            print("DynamoDB table not configured")
            return None
        
        # Scan for existing video with same filename
        response = table.scan(
            FilterExpression='originalFilename = :filename',
            ExpressionAttributeValues={':filename': filename}
        )
        
        items = response.get('Items', [])
        if items:
            print(f"Found {len(items)} existing videos for filename: {filename}")
            return items[0]  # Return the first match
        
        return None
        
    except Exception as e:
        print(f"Error finding existing video by filename: {str(e)}")
        return None

def create_video_record(video_record):
    """
    Create or update video record in DynamoDB
    """
    try:
        if not table:
            print("DynamoDB table not configured")
            return
        
        table.put_item(Item=video_record)
        print(f"Created/updated video record: {video_record['videoId']}")
        
    except Exception as e:
        print(f"Error creating video record: {str(e)}")
        raise

def extract_filename_from_event(detail):
    """
    Extract original filename from EventBridge event output file paths
    """
    try:
        output_group_details = detail.get('outputGroupDetails', [])
        
        for group in output_group_details:
            output_details = group.get('outputDetails', [])
            for output in output_details:
                output_file_paths = output.get('outputFilePaths', [])
                for file_path in output_file_paths:
                    # Extract filename from S3 path
                    # Example: "s3://bucket/free/filename_free_480p.mp4"
                    if file_path:
                        # Get the filename part
                        filename_with_suffix = file_path.split('/')[-1]
                        
                        # Remove the tier-specific suffix to get original filename
                        # Example: "filename_free_480p.mp4" -> "filename"
                        if '_free_480p.mp4' in filename_with_suffix:
                            return filename_with_suffix.replace('_free_480p.mp4', '')
                        elif '_standard_480p.mp4' in filename_with_suffix:
                            return filename_with_suffix.replace('_standard_480p.mp4', '')
                        elif '_premium_720p.mp4' in filename_with_suffix:
                            return filename_with_suffix.replace('_premium_720p.mp4', '')
                        elif '_premium_1080p.mp4' in filename_with_suffix:
                            return filename_with_suffix.replace('_premium_1080p.mp4', '')
                        elif '_thumbnail.' in filename_with_suffix:
                            # Extract from thumbnail: "filename_thumbnail.0000000.jpg" -> "filename"
                            return filename_with_suffix.split('_thumbnail.')[0]
        
        return None
        
    except Exception as e:
        print(f"Error extracting filename from event: {str(e)}")
        return None

def get_job_type_from_detail(detail):
    """
    Determine if this is a free job or full job based on output paths
    """
    try:
        output_group_details = detail.get('outputGroupDetails', [])
        
        for group in output_group_details:
            output_details = group.get('outputDetails', [])
            for output in output_details:
                output_file_paths = output.get('outputFilePaths', [])
                for file_path in output_file_paths:
                    if '/free/' in file_path:
                        return 'free'
                    elif '/standard/' in file_path or '/premium/' in file_path:
                        return 'full'
        
        return 'unknown'
        
    except Exception as e:
        print(f"Error determining job type: {str(e)}")
        return 'unknown'

def extract_thumbnail_url_from_event(detail, cloudfront_domain, filename):
    """
    Extract actual thumbnail URL from MediaConvert job output
    """
    try:
        output_group_details = detail.get('outputGroupDetails', [])
        
        for group in output_group_details:
            output_details = group.get('outputDetails', [])
            for output in output_details:
                output_file_paths = output.get('outputFilePaths', [])
                for file_path in output_file_paths:
                    # Look for thumbnail files
                    if '/thumbnails/' in file_path and '_thumbnail.' in file_path:
                        # Convert S3 path to CloudFront URL
                        # Example: "s3://bucket/thumbnails/filename_thumbnail.0000000.jpg"
                        thumbnail_filename = file_path.split('/')[-1]
                        return f"https://{cloudfront_domain}/thumbnails/{thumbnail_filename}"
        
        # Fallback to expected naming pattern if not found in output
        return f"https://{cloudfront_domain}/thumbnails/{filename}_thumbnail.0000000.jpg"
        
    except Exception as e:
        print(f"Error extracting thumbnail URL: {str(e)}")
        # Fallback to expected naming pattern
        return f"https://{cloudfront_domain}/thumbnails/{filename}_thumbnail.0000000.jpg"

def extract_duration_from_job_detail(detail):
    """
    Extract video duration from MediaConvert job detail if available
    Returns duration in seconds as a float
    """
    try:
        # Try to get duration from output group details first
        output_group_details = detail.get('outputGroupDetails', [])
        for group in output_group_details:
            output_details = group.get('outputDetails', [])
            for output in output_details:
                duration_ms = output.get('durationInMs')
                if duration_ms:
                    return float(duration_ms) / 1000.0  # Convert to seconds
        
        # Fallback to job details if available
        job_details = detail.get('jobDetails', {})
        if 'durationInMs' in job_details:
            return float(job_details['durationInMs']) / 1000.0  # Convert to seconds
        
        return None
        
    except Exception as e:
        print(f"Error extracting duration: {str(e)}")
        return None