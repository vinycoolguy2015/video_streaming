#!/bin/bash

# Video Streaming App Deployment Script
# This script deploys all CloudFormation stacks and uploads frontend to S3

set -e  # Exit on any error

# Configuration
APP_NAME="VideoStreamingApp"
AWS_REGION="ap-southeast-1"  # Change to your preferred region
AWS_PROFILE="default"   # Change to your AWS profile if needed

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to package Lambda function
package_lambda() {
    local function_name=$1
    local source_file=$2
    local output_dir="lambda-packages"
    local current_dir=$(pwd)
    local zip_file="${current_dir}/${output_dir}/${function_name}.zip"
    
    print_status "Packaging Lambda function: $function_name" >&2
    
    # Check if source file exists
    if [ ! -f "backend/${source_file}" ]; then
        print_error "Source file does not exist: backend/${source_file}" >&2
        exit 1
    fi
    
    # Create output directory
    mkdir -p $output_dir
    
    # Create temporary directory for packaging
    local temp_dir=$(mktemp -d)
    
    # Copy source file and rename to lambda_function.py (standard Lambda entry point)
    cp "backend/${source_file}" "${temp_dir}/lambda_function.py"
    
    # Install dependencies if requirements.txt exists
    if [ -f "backend/requirements.txt" ]; then
        print_status "Installing dependencies for $function_name..." >&2
        # Use pip3 if available, otherwise pip
        local pip_cmd="pip"
        if command -v pip3 &> /dev/null; then
            pip_cmd="pip3"
        fi
        
        $pip_cmd install -r backend/requirements.txt -t $temp_dir --quiet --no-deps --upgrade
        
        # Remove unnecessary files to reduce package size
        find $temp_dir -name "*.pyc" -delete
        find $temp_dir -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find $temp_dir -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
        find $temp_dir -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
    fi
    
    # Create zip file
    cd $temp_dir
    zip -r "$zip_file" . -q
    local zip_exit_code=$?
    cd "$current_dir"
    
    # Check if zip creation was successful
    if [ $zip_exit_code -ne 0 ]; then
        print_error "Failed to create zip file for $function_name" >&2
        rm -rf $temp_dir
        exit 1
    fi
    
    # Verify zip file was created
    if [ ! -f "$zip_file" ]; then
        print_error "Zip file was not created: $zip_file" >&2
        rm -rf $temp_dir
        exit 1
    fi
    
    # Clean up temp directory
    rm -rf $temp_dir
    
    print_success "Created package: $zip_file" >&2
    
    # Debug: Show file size (redirect to stderr so it doesn't interfere with return value)
    local file_size=$(ls -lh "$zip_file" | awk '{print $5}')
    print_status "Package size: $file_size" >&2
    
    # Return the zip file path (only this will be captured by command substitution)
    echo "$zip_file"
}

# Function to upload Lambda package to S3
upload_lambda_package() {
    local zip_file=$1
    local function_name=$(basename $zip_file .zip)
    local s3_key="lambda-packages/${function_name}.zip"
    
    # Get the Lambda deployment bucket name
    local lambda_bucket="videostreamingapp-lambda-deployments-$(aws sts get-caller-identity --query Account --output text)"
    
    print_status "Uploading $zip_file to S3..."
    
    # Debug: Check if file exists and show details
    if [ ! -f "$zip_file" ]; then
        print_error "Zip file does not exist: $zip_file"
        print_error "Current directory: $(pwd)"
        print_error "Lambda packages directory contents:"
        ls -la lambda-packages/ 2>/dev/null || print_error "lambda-packages directory does not exist"
        exit 1
    fi
    
    # Show file details
    print_status "Zip file details: $(ls -lh "$zip_file")"
    
    # Check if bucket exists first
    if ! aws s3 ls "s3://$lambda_bucket" --region $AWS_REGION --profile $AWS_PROFILE >/dev/null 2>&1; then
        print_error "Lambda deployment bucket does not exist: $lambda_bucket"
        print_error "Make sure the Lambda deployment stack is deployed first"
        exit 1
    fi
    
    # Upload the file
    if aws s3 cp "$zip_file" "s3://$lambda_bucket/$s3_key" --region $AWS_REGION --profile $AWS_PROFILE; then
        print_success "Successfully uploaded $zip_file"
        echo $s3_key
    else
        print_error "Failed to upload $zip_file to s3://$lambda_bucket/$s3_key"
        print_error "Check AWS credentials and bucket permissions"
        exit 1
    fi
}

# Function to package and upload all Lambda functions
package_and_upload_lambdas() {
    print_status "Packaging and uploading Lambda functions..."
    
    # Package each Lambda function
    print_status "Packaging video-processor..."
    local video_processor_zip=$(package_lambda "video-processor" "video_processor.py")
    print_status "Debug: video_processor_zip = '$video_processor_zip'"
    
    print_status "Packaging video-streamer..."
    local video_streamer_zip=$(package_lambda "video-streamer" "video_streamer.py")
    print_status "Debug: video_streamer_zip = '$video_streamer_zip'"
    
    print_status "Packaging video-lister..."
    local video_lister_zip=$(package_lambda "video-lister" "video_lister.py")
    print_status "Debug: video_lister_zip = '$video_lister_zip'"
    
    print_status "Packaging mediaconvert-completion-handler..."
    local completion_handler_zip=$(package_lambda "mediaconvert-completion-handler" "mediaconvert_completion_handler.py")
    print_status "Debug: completion_handler_zip = '$completion_handler_zip'"
    
    print_status "Starting S3 uploads..."
    
    # Upload packages to S3
    print_status "Uploading video-processor..."
    upload_lambda_package "$video_processor_zip"
    print_status "Uploading video-streamer..."
    upload_lambda_package "$video_streamer_zip"
    print_status "Uploading video-lister..."
    upload_lambda_package "$video_lister_zip"
    print_status "Uploading mediaconvert-completion-handler..."
    upload_lambda_package "$completion_handler_zip"
    
    print_success "All Lambda functions packaged and uploaded"
    
    # Clean up local zip files after successful upload
    print_status "Cleaning up local Lambda packages..."
    rm -rf lambda-packages
}

# Function to check if AWS CLI is installed and configured
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --profile $AWS_PROFILE &> /dev/null; then
        print_error "AWS credentials not configured or invalid for profile: $AWS_PROFILE"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to deploy a CloudFormation stack
deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local description=$3
    local update_exit_code=0
    
    print_status "Deploying $description..."
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $stack_name --profile $AWS_PROFILE --region $AWS_REGION &> /dev/null; then
        print_status "Stack $stack_name exists. Updating..."
        
        # Capture the update command output and exit code
        # Temporarily disable exit on error to handle "No updates" case
        set +e
        update_output=$(aws cloudformation update-stack \
            --stack-name $stack_name \
            --template-body file://$template_file \
            --parameters ParameterKey=AppName,ParameterValue=$APP_NAME \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile $AWS_PROFILE \
            --region $AWS_REGION 2>&1)
        update_exit_code=$?
        set -e
        
        # Check if the update failed due to no changes
        if [ $update_exit_code -ne 0 ]; then
            if echo "$update_output" | grep -q "No updates are to be performed"; then
                print_status "No updates needed for $stack_name"
                print_success "$description is up to date"
                return 0
            else
                print_error "Failed to update $stack_name: $update_output"
                exit 1
            fi
        fi
    else
        print_status "Creating new stack $stack_name..."
        set +e
        aws cloudformation create-stack \
            --stack-name $stack_name \
            --template-body file://$template_file \
            --parameters ParameterKey=AppName,ParameterValue=$APP_NAME \
            --capabilities CAPABILITY_NAMED_IAM \
            --disable-rollback \
            --profile $AWS_PROFILE \
            --region $AWS_REGION
        update_exit_code=$?
        set -e
        
        if [ $update_exit_code -ne 0 ]; then
            print_error "Failed to create $stack_name"
            exit 1
        fi
    fi
    
    # Wait for stack operation to complete (only if an operation was actually performed)
    if [ $update_exit_code -eq 0 ]; then
        print_status "Waiting for stack operation to complete..."
        set +e
        aws cloudformation wait stack-create-complete --stack-name $stack_name --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || \
        aws cloudformation wait stack-update-complete --stack-name $stack_name --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null
        wait_exit_code=$?
        set -e
        
        if [ $wait_exit_code -eq 0 ]; then
            print_success "$description deployed successfully"
        else
            print_error "Failed to deploy $description"
            debug_stack $stack_name
            exit 1
        fi
    fi
}

# Function to get stack output value
get_stack_output() {
    local stack_name=$1
    local output_key=$2
    
    aws cloudformation describe-stacks \
        --stack-name $stack_name \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text
}

# Function to debug failed stack
debug_stack() {
    local stack_name=$1
    print_status "Debugging failed stack: $stack_name"
    
    echo
    print_status "Stack Status:"
    aws cloudformation describe-stacks \
        --stack-name $stack_name \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --query 'Stacks[0].{Status:StackStatus,Reason:StackStatusReason}' \
        --output table
    
    echo
    print_status "Failed Resources:"
    aws cloudformation describe-stack-events \
        --stack-name $stack_name \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].{Resource:LogicalResourceId,Status:ResourceStatus,Reason:ResourceStatusReason,Type:ResourceType}' \
        --output table
    
    echo
    print_warning "To continue fixing this stack, you can:"
    echo "  1. Fix the template and run: ./deploy.sh deploy"
    echo "  2. Debug specific resource in AWS Console"
    echo "  3. Delete the stack and start over: ./deploy.sh cleanup"
}

# Function to generate and update frontend configuration
generate_and_update_frontend_config() {
    print_status "Updating frontend configuration with deployment values..."
    
    # Get stack outputs
    USER_POOL_ID=$(get_stack_output "${APP_NAME}-Cognito" "UserPoolId")
    USER_POOL_CLIENT_ID=$(get_stack_output "${APP_NAME}-Cognito" "UserPoolClientId")
    IDENTITY_POOL_ID=$(get_stack_output "${APP_NAME}-Cognito" "IdentityPoolId")
    API_URL=$(get_stack_output "${APP_NAME}-API" "APIGatewayURL")
    CLOUDFRONT_DOMAIN=$(get_stack_output "${APP_NAME}-Storage" "CloudFrontDomainName")
    CONTENT_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "ContentBucketName")
    WEB_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "WebBucketName")
    
    # Validate that we got all required outputs
    if [[ -z "$USER_POOL_ID" || -z "$USER_POOL_CLIENT_ID" || -z "$IDENTITY_POOL_ID" || -z "$API_URL" || -z "$CLOUDFRONT_DOMAIN" ]]; then
        print_error "Failed to retrieve all required stack outputs"
        print_error "USER_POOL_ID: $USER_POOL_ID"
        print_error "USER_POOL_CLIENT_ID: $USER_POOL_CLIENT_ID"
        print_error "IDENTITY_POOL_ID: $IDENTITY_POOL_ID"
        print_error "API_URL: $API_URL"
        print_error "CLOUDFRONT_DOMAIN: $CLOUDFRONT_DOMAIN"
        exit 1
    fi
    
    # Check if frontend config file exists
    if [[ ! -f "frontend/config.js" ]]; then
        print_error "Frontend configuration file not found: frontend/config.js"
        exit 1
    fi
    
    # Create backup of original config
    cp frontend/config.js frontend/config.js.backup
    
    # Update configuration values using sed
    print_status "Updating AWS configuration values..."
    
    # Update AWS region
    sed -i.tmp "s/region: '[^']*'/region: '${AWS_REGION}'/g" frontend/config.js
    
    # Update Cognito configuration
    sed -i.tmp "s/userPoolId: '[^']*'/userPoolId: '${USER_POOL_ID}'/g" frontend/config.js
    sed -i.tmp "s/userPoolWebClientId: '[^']*'/userPoolWebClientId: '${USER_POOL_CLIENT_ID}'/g" frontend/config.js
    sed -i.tmp "s/identityPoolId: '[^']*'/identityPoolId: '${IDENTITY_POOL_ID}'/g" frontend/config.js
    
    # Update API Gateway URL
    sed -i.tmp "s|baseUrl: '[^']*'|baseUrl: '${API_URL}'|g" frontend/config.js
    
    # Update CloudFront domain
    sed -i.tmp "s/domain: '[^']*'/domain: '${CLOUDFRONT_DOMAIN}'/g" frontend/config.js
    
    # Update S3 content bucket
    sed -i.tmp "s/contentBucket: '[^']*'/contentBucket: '${CONTENT_BUCKET}'/g" frontend/config.js
    
    # Update CloudFront domain in thumbnail URLs
    sed -i.tmp "s|https://[^/]*/thumbnails/|https://${CLOUDFRONT_DOMAIN}/thumbnails/|g" frontend/config.js
    
    # Clean up temporary files
    rm -f frontend/config.js.tmp
    
    print_success "Frontend configuration updated with deployment values"
    
    # Store values for upload function
    export WEB_BUCKET_NAME="$WEB_BUCKET"
}

# Function to upload frontend files to S3
upload_frontend_to_s3() {
    print_status "Uploading frontend files to S3..."
    
    if [[ -z "$WEB_BUCKET_NAME" ]]; then
        print_error "Web bucket name not found. Cannot upload frontend files."
        exit 1
    fi
    
    # Create a temporary directory for processed files
    TEMP_DIR=$(mktemp -d)
    
    # Copy frontend files to temp directory
    cp -r frontend/* "$TEMP_DIR/"
    
    # Upload files to S3 with appropriate content types
    print_status "Uploading HTML files..."
    aws s3 cp "$TEMP_DIR/index.html" "s3://$WEB_BUCKET_NAME/" \
        --content-type "text/html" \
        --profile $AWS_PROFILE \
        --region $AWS_REGION
    
    print_status "Uploading CSS files..."
    for css_file in styles.css toast.css; do
        if [[ -f "$TEMP_DIR/$css_file" ]]; then
            aws s3 cp "$TEMP_DIR/$css_file" "s3://$WEB_BUCKET_NAME/" \
                --content-type "text/css" \
                --profile $AWS_PROFILE \
                --region $AWS_REGION
        fi
    done
    
    print_status "Uploading JavaScript files..."
    for js_file in utils.js config.js auth.js player.js app.js video-list.js; do
        if [[ -f "$TEMP_DIR/$js_file" ]]; then
            aws s3 cp "$TEMP_DIR/$js_file" "s3://$WEB_BUCKET_NAME/" \
                --content-type "application/javascript" \
                --profile $AWS_PROFILE \
                --region $AWS_REGION
        fi
    done
    
    # Upload SVG files
    print_status "Uploading SVG files..."
    for svg_file in *.svg; do
        if [[ -f "$TEMP_DIR/$svg_file" ]]; then
            aws s3 cp "$TEMP_DIR/$svg_file" "s3://$WEB_BUCKET_NAME/" \
                --content-type "image/svg+xml" \
                --profile $AWS_PROFILE \
                --region $AWS_REGION
        fi
    done
    
    # Upload any other files (like package.json)
    print_status "Uploading other files..."
    for file in "$TEMP_DIR"/*; do
        filename=$(basename "$file")
        if [[ "$filename" != "index.html" && "$filename" != *.css && "$filename" != *.js && "$filename" != *.svg ]]; then
            aws s3 cp "$file" "s3://$WEB_BUCKET_NAME/" \
                --profile $AWS_PROFILE \
                --region $AWS_REGION
        fi
    done
    
    # Clean up temp directory
    rm -rf "$TEMP_DIR"
    
    print_success "Frontend files uploaded to S3 bucket: $WEB_BUCKET_NAME"
}

# Function to configure CloudFront for web hosting
configure_cloudfront_web() {
    print_status "Web hosting will be served via CloudFront..."
    print_success "CloudFront distribution configured for web hosting"
}

# Function to display deployment summary
display_deployment_summary() {
    print_success "=== DEPLOYMENT SUMMARY ==="
    echo
    
    # Get final outputs
    USER_POOL_ID=$(get_stack_output "${APP_NAME}-Cognito" "UserPoolId")
    API_URL=$(get_stack_output "${APP_NAME}-API" "APIGatewayURL")
    CLOUDFRONT_DOMAIN=$(get_stack_output "${APP_NAME}-Storage" "CloudFrontDomainName")
    WEB_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "WebBucketName")
    UPLOAD_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "UploadBucketName")
    CONTENT_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "ContentBucketName")
    
    echo -e "${GREEN}Frontend Application:${NC}"
    echo -e "  Website URL: ${BLUE}https://$CLOUDFRONT_DOMAIN${NC}"
    echo -e "  CloudFront Distribution: ${BLUE}https://$CLOUDFRONT_DOMAIN${NC}"
    echo
    
    echo -e "${GREEN}AWS Resources:${NC}"
    echo -e "  User Pool ID: ${BLUE}$USER_POOL_ID${NC}"
    echo -e "  API Gateway URL: ${BLUE}$API_URL${NC}"
    echo -e "  Upload Bucket: ${BLUE}$UPLOAD_BUCKET${NC}"
    echo -e "  Content Bucket: ${BLUE}$CONTENT_BUCKET${NC}"
    echo -e "  Web Bucket: ${BLUE}$WEB_BUCKET${NC}"
    echo
    
    echo -e "${GREEN}Next Steps:${NC}"
    echo -e "  1. Upload test videos to: ${BLUE}s3://$UPLOAD_BUCKET/${NC}"
    echo -e "  2. Wait for MediaConvert processing to complete"
    echo -e "  3. Access the application at: ${BLUE}https://$CLOUDFRONT_DOMAIN${NC}"
    echo -e "  4. Create user accounts and test different subscription types"
    echo
    
    echo -e "${YELLOW}Manual Upload Instructions:${NC}"
    echo -e "  aws s3 cp your-video.mp4 s3://$UPLOAD_BUCKET/ --profile $AWS_PROFILE"
    echo
}

# Main deployment function
main() {
    print_status "Starting deployment of Video Streaming App..."
    print_status "App Name: $APP_NAME"
    print_status "AWS Region: $AWS_REGION"
    print_status "AWS Profile: $AWS_PROFILE"
    echo
    
    # Check prerequisites
    check_prerequisites
    echo
    
    # Deploy stacks in order
    print_status "Deploying CloudFormation stacks..."
    echo
    
    # 0. Deploy Lambda Deployment Bucket (needed first for Lambda packages)
    deploy_stack \
        "${APP_NAME}-LambdaDeployment" \
        "cloudformation/00-lambda-deployment-bucket.yaml" \
        "Lambda Deployment Bucket Stack"
    echo
    
    # Package and upload Lambda functions
    package_and_upload_lambdas
    echo
    
    # 1. Deploy Cognito (Authentication)
    deploy_stack \
        "${APP_NAME}-Cognito" \
        "cloudformation/01-cognito-auth.yaml" \
        "Cognito Authentication Stack"
    echo
    
    # 2. Deploy Storage, Processing, and Database (merged stack)
    deploy_stack \
        "${APP_NAME}-Storage" \
        "cloudformation/02-storage-processing.yaml" \
        "Storage, Processing, and Database Stack"
    echo
    
    # 5. Deploy API Gateway and Lambda
    deploy_stack \
        "${APP_NAME}-API" \
        "cloudformation/04-api-backend.yaml" \
        "API Gateway and Lambda Stack"
    echo
    
    print_success "All CloudFormation stacks deployed successfully!"
    echo
    
    # Generate and update frontend configuration
    generate_and_update_frontend_config
    echo
    
    # Upload frontend to S3
    upload_frontend_to_s3
    echo
    
    # Configure CloudFront for web hosting
    configure_cloudfront_web
    echo
    
    # Display deployment summary
    display_deployment_summary
    
    print_success "Deployment completed successfully!"
}

# Function to clean up (delete all stacks)
cleanup() {
    print_warning "This will delete all deployed resources. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_status "Deleting stacks..."
        
        # Empty S3 buckets first
        WEB_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "WebBucketName" 2>/dev/null || echo "")
        UPLOAD_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "UploadBucketName" 2>/dev/null || echo "")
        CONTENT_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "ContentBucketName" 2>/dev/null || echo "")
        LAMBDA_BUCKET=$(get_stack_output "${APP_NAME}-LambdaDeployment" "LambdaDeploymentBucketName" 2>/dev/null || echo "")
        
        if [[ -n "$WEB_BUCKET" ]]; then
            print_status "Emptying web bucket: $WEB_BUCKET"
            aws s3 rm "s3://$WEB_BUCKET" --recursive --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        fi
        
        if [[ -n "$UPLOAD_BUCKET" ]]; then
            print_status "Emptying upload bucket: $UPLOAD_BUCKET"
            aws s3 rm "s3://$UPLOAD_BUCKET" --recursive --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        fi
        
        if [[ -n "$CONTENT_BUCKET" ]]; then
            print_status "Emptying content bucket: $CONTENT_BUCKET"
            aws s3 rm "s3://$CONTENT_BUCKET" --recursive --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        fi
        
        if [[ -n "$LAMBDA_BUCKET" ]]; then
            print_status "Emptying Lambda deployment bucket: $LAMBDA_BUCKET"
            aws s3 rm "s3://$LAMBDA_BUCKET" --recursive --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        fi
        
        # Delete stacks in reverse order
        aws cloudformation delete-stack --stack-name "${APP_NAME}-API" --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        aws cloudformation delete-stack --stack-name "${APP_NAME}-Storage" --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        aws cloudformation delete-stack --stack-name "${APP_NAME}-Cognito" --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        aws cloudformation delete-stack --stack-name "${APP_NAME}-LambdaDeployment" --profile $AWS_PROFILE --region $AWS_REGION 2>/dev/null || true
        
        print_success "Cleanup initiated. Check AWS Console for progress."
    else
        print_status "Cleanup cancelled."
    fi
}

# Function to just update frontend
update_frontend() {
    print_status "Updating frontend files only..."
    
    # Get existing stack outputs
    WEB_BUCKET=$(get_stack_output "${APP_NAME}-Storage" "WebBucketName")
    
    if [[ -z "$WEB_BUCKET" ]]; then
        print_error "Cannot find web bucket. Make sure stacks are deployed first."
        exit 1
    fi
    
    export WEB_BUCKET_NAME="$WEB_BUCKET"
    
    # Generate config and upload
    generate_and_update_frontend_config
    upload_frontend_to_s3
    
    print_success "Frontend updated successfully!"
    echo -e "Access your application at: ${BLUE}https://$CLOUDFRONT_DOMAIN${NC}"
}

# Function to debug all stacks
debug_all_stacks() {
    print_status "Debugging all VideoStreamingApp stacks..."
    
    local stacks=("${APP_NAME}-LambdaDeployment" "${APP_NAME}-Cognito" "${APP_NAME}-Storage" "${APP_NAME}-API")
    
    for stack in "${stacks[@]}"; do
        if aws cloudformation describe-stacks --stack-name $stack --profile $AWS_PROFILE --region $AWS_REGION &> /dev/null; then
            debug_stack $stack
            echo
        else
            print_warning "Stack $stack does not exist"
        fi
    done
}

# Parse command line arguments
case "${1:-deploy}" in
    deploy)
        main
        ;;
    cleanup)
        cleanup
        ;;
    config)
        generate_and_update_frontend_config
        ;;
    frontend)
        update_frontend
        ;;
    debug)
        if [[ -n "$2" ]]; then
            debug_stack "$2"
        else
            debug_all_stacks
        fi
        ;;
    *)
        echo "Usage: $0 {deploy|cleanup|config|frontend|debug}"
        echo "  deploy   - Deploy all stacks and upload frontend (default)"
        echo "  cleanup  - Delete all stacks and resources"
        echo "  config   - Generate frontend configuration only"
        echo "  frontend - Update frontend files only"
        echo "  debug    - Debug failed stacks (optionally specify stack name)"
        exit 1
        ;;
esac
