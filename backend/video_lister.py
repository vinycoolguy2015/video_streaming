import json
import boto3
import os
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME')
table = dynamodb.Table(table_name) if table_name else None

def decimal_default(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """
    Lambda function to list videos with pagination
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 12))
        status_filter = query_params.get('status')  # No default status filter
        
        # Calculate pagination parameters
        start_key = None
        if page > 1:
            # For simplicity, we'll use scan with limit and calculate offset
            # In production, you might want to use pagination tokens
            offset = (page - 1) * limit
        else:
            offset = 0
        
        logger.info(f"Listing videos - Page: {page}, Limit: {limit}, Status: {status_filter}")
        
        # Query DynamoDB for videos
        if status_filter:
            response = table.query(
                IndexName='StatusIndex',
                KeyConditionExpression=Key('status').eq(status_filter),
                ScanIndexForward=False,  # Sort by upload date descending
                Limit=limit * page  # Get more items to handle pagination
            )
        else:
            response = table.scan(
                Limit=limit * page
            )
        
        items = response.get('Items', [])
        
        # Handle pagination by slicing results
        start_index = offset
        end_index = start_index + limit
        paginated_items = items[start_index:end_index]
        
        # Transform items for frontend
        videos = []
        for item in paginated_items:
            video = {
                'id': item.get('videoId'),
                'title': item.get('title', 'Untitled Video'),
                'description': item.get('description', ''),
                'thumbnail': item.get('thumbnailUrl', ''),
                'duration': item.get('duration', 0),
                'uploadDate': item.get('uploadDate', ''),
                'status': item.get('status', 'processing'),
                'qualities': item.get('availableQualities', ['480p']),
                'fileSize': item.get('fileSize', 0),
                'originalFilename': item.get('originalFilename', '')
            }
            videos.append(video)
        
        # Calculate pagination info
        total_items = len(items) if len(items) < limit * page else None
        if total_items is None:
            # If we got the full limit, there might be more items
            # Do a count query to get total (expensive operation, consider caching)
            count_response = table.query(
                IndexName='StatusIndex',
                KeyConditionExpression=Key('status').eq(status_filter),
                Select='COUNT'
            ) if status_filter else table.scan(Select='COUNT')
            total_items = count_response.get('Count', 0)
        
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1
        
        # Prepare response
        response_data = {
            'videos': videos,
            'pagination': {
                'currentPage': page,
                'totalPages': total_pages,
                'totalItems': total_items,
                'itemsPerPage': limit,
                'hasNext': has_next,
                'hasPrevious': has_prev
            }
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps(response_data, default=decimal_default)
        }
        
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

def get_video_by_id(video_id):
    """
    Get a specific video by ID
    """
    try:
        response = table.get_item(
            Key={'videoId': video_id}
        )
        
        item = response.get('Item')
        if not item:
            return None
            
        video = {
            'id': item.get('videoId'),
            'title': item.get('title', 'Untitled Video'),
            'description': item.get('description', ''),
            'thumbnail': item.get('thumbnailUrl', ''),
            'duration': item.get('duration', 0),
            'uploadDate': item.get('uploadDate', ''),
            'status': item.get('status', 'processing'),
            'qualities': item.get('availableQualities', ['480p']),
            'fileSize': item.get('fileSize', 0),
            'originalFilename': item.get('originalFilename', ''),
            'videoUrls': item.get('videoUrls', {})
        }
        
        return video
        
    except Exception as e:
        logger.error(f"Error getting video {video_id}: {str(e)}")
        return None

def update_video_metadata(video_id, metadata):
    """
    Update video metadata in DynamoDB
    """
    try:
        # Prepare update expression
        update_expression = "SET "
        expression_attribute_values = {}
        expression_attribute_names = {}
        
        for key, value in metadata.items():
            if key != 'videoId':  # Don't update the primary key
                attr_name = f"#{key}"
                attr_value = f":{key}"
                update_expression += f"{attr_name} = {attr_value}, "
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = value
        
        # Remove trailing comma and space
        update_expression = update_expression.rstrip(', ')
        
        response = table.update_item(
            Key={'videoId': video_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='UPDATED_NEW'
        )
        
        return response.get('Attributes')
        
    except Exception as e:
        logger.error(f"Error updating video metadata {video_id}: {str(e)}")
        return None
