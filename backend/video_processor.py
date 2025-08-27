import json
import boto3
import os
import urllib.parse

# Initialize AWS clients
mediaconvert = boto3.client('mediaconvert')
s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Lambda function to process uploaded videos using MediaConvert
    Creates different versions for free, standard, and premium users
    Also generates thumbnails
    """
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # Get MediaConvert endpoint
        endpoints = mediaconvert.describe_endpoints()
        endpoint_url = endpoints['Endpoints'][0]['Url']
        mc_client = boto3.client('mediaconvert', endpoint_url=endpoint_url)
        
        # Parse S3 event
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = urllib.parse.unquote_plus(record['s3']['object']['key'])
            
            print(f"Processing file: s3://{bucket}/{key}")
            
            # Skip if not a video file
            if not key.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                print(f"Skipping non-video file: {key}")
                continue
            
            input_uri = f's3://{bucket}/{key}'
            output_bucket = os.environ['OUTPUT_BUCKET']
            
            # Extract filename without extension
            filename = key.split('/')[-1].split('.')[0]
            
            # Create separate MediaConvert jobs for free version (clipped) and full versions
            
            # Job 1: Free version with 10-second clipping
            free_job_settings = create_free_job_settings(input_uri, output_bucket, filename)
            free_job_settings['UserMetadata'] = {
                'originalFilename': filename,
                'originalKey': key,
                'inputBucket': bucket,
                'jobType': 'free'
            }
            
            free_response = mc_client.create_job(**free_job_settings)
            free_job_id = free_response['Job']['Id']
            print(f"MediaConvert free job created: {free_job_id} for file: {filename}")
            
            # Job 2: Full versions (standard, premium, thumbnail)
            full_job_settings = create_full_job_settings(input_uri, output_bucket, filename)
            full_job_settings['UserMetadata'] = {
                'originalFilename': filename,
                'originalKey': key,
                'inputBucket': bucket,
                'jobType': 'full'
            }
            
            full_response = mc_client.create_job(**full_job_settings)
            full_job_id = full_response['Job']['Id']
            print(f"MediaConvert full job created: {full_job_id} for file: {filename}")
            
            # Return both job IDs
            job_id = f"{free_job_id},{full_job_id}"
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Video processing initiated successfully',
                'jobId': job_id
            })
        }
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to process video: {str(e)}'
            })
        }

def create_free_job_settings(input_uri, output_bucket, filename):
    """
    Create MediaConvert job settings for free version (10-second preview)
    """
    
    return {
        "Role": os.environ['MEDIACONVERT_ROLE'],
        "Settings": {
            "Inputs": [{
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "Offset": 0,
                        "DefaultSelection": "DEFAULT",
                        "ProgramSelection": 1
                    }
                },
                "VideoSelector": {
                    "ColorSpace": "FOLLOW"
                },
                "FilterEnable": "AUTO",
                "PsiControl": "USE_PSI",
                "FilterStrength": 0,
                "DeblockFilter": "DISABLED",
                "DenoiseFilter": "DISABLED",
                "TimecodeSource": "ZEROBASED",
                "FileInput": input_uri,
                "InputClippings": [{
                    "StartTimecode": "00:00:00;00",
                    "EndTimecode": "00:00:10;00"
                }]
            }],
            "OutputGroups": [
                # Free version (480p, 10 seconds preview)
                {
                    "Name": "Free_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/free/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_free_480p",
                        "VideoDescription": {
                            "TimecodeInsertion": "DISABLED", 
                            "ScalingBehavior": "DEFAULT",
                            "AntiAlias": "ENABLED",
                            "Sharpness": 50,

                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "InterlaceMode": "PROGRESSIVE",
                                    "NumberReferenceFrames": 3,
                                    "Syntax": "DEFAULT",
                                    "Softness": 0,
                                    "GopClosedCadence": 1,
                                    "GopSize": 90,
                                    "Slices": 1,
                                    "GopBReference": "DISABLED",
                                    "SlowPal": "DISABLED",
                                    "SpatialAdaptiveQuantization": "ENABLED",
                                    "TemporalAdaptiveQuantization": "ENABLED",
                                    "FlickerAdaptiveQuantization": "DISABLED",
                                    "EntropyEncoding": "CABAC",
                                    "Bitrate": 1000000,
                                    "FramerateControl": "INITIALIZE_FROM_SOURCE",
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "MAIN",
                                    "Telecine": "NONE",
                                    "MinIInterval": 0,
                                    "AdaptiveQuantization": "HIGH",
                                    "CodecLevel": "AUTO",
                                    "FieldEncoding": "PAFF",
                                    "SceneChangeDetect": "ENABLED",
                                    "QualityTuningLevel": "SINGLE_PASS",
                                    "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                                    "UnregisteredSeiTimecode": "DISABLED",
                                    "GopSizeUnits": "FRAMES",
                                    "ParControl": "INITIALIZE_FROM_SOURCE",
                                    "NumberBFramesBetweenReferenceFrames": 2,
                                    "RepeatPps": "DISABLED"
                                }
                            },
                            "AfdSignaling": "NONE",
                            "DropFrameTimecode": "ENABLED",
                            "RespondToAfd": "NONE",
                            "ColorMetadata": "INSERT",
                            "Width": 854,
                            "Height": 480
                        },
                        "AudioDescriptions": [{
                            "AudioTypeControl": "FOLLOW_INPUT",
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "AudioDescriptionBroadcasterMix": "NORMAL",
                                    "Bitrate": 64000,
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "LC",
                                    "CodingMode": "CODING_MODE_2_0",
                                    "RawFormat": "NONE",
                                    "SampleRate": 48000,
                                    "Specification": "MPEG4"
                                }
                            },
                            "LanguageCodeControl": "FOLLOW_INPUT"
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                }
            ]
        }
    }

def create_full_job_settings(input_uri, output_bucket, filename):
    """
    Create MediaConvert job settings for standard, premium versions and thumbnails
    """
    
    return {
        "Role": os.environ['MEDIACONVERT_ROLE'],
        "Settings": {
            "Inputs": [{
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "Offset": 0,
                        "DefaultSelection": "DEFAULT",
                        "ProgramSelection": 1
                    }
                },
                "VideoSelector": {
                    "ColorSpace": "FOLLOW"
                },
                "FilterEnable": "AUTO",
                "PsiControl": "USE_PSI",
                "FilterStrength": 0,
                "DeblockFilter": "DISABLED",
                "DenoiseFilter": "DISABLED",
                "TimecodeSource": "EMBEDDED",
                "FileInput": input_uri
            }],
            "OutputGroups": [
                # Standard version (480p, full video)
                {
                    "Name": "Standard_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/standard/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_standard_480p",
                        "VideoDescription": {
                            "ScalingBehavior": "DEFAULT",
                            "TimecodeInsertion": "DISABLED",
                            "AntiAlias": "ENABLED",
                            "Sharpness": 50,
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "InterlaceMode": "PROGRESSIVE",
                                    "NumberReferenceFrames": 3,
                                    "Syntax": "DEFAULT",
                                    "Softness": 0,
                                    "GopClosedCadence": 1,
                                    "GopSize": 90,
                                    "Slices": 1,
                                    "GopBReference": "DISABLED",
                                    "SlowPal": "DISABLED",
                                    "SpatialAdaptiveQuantization": "ENABLED",
                                    "TemporalAdaptiveQuantization": "ENABLED",
                                    "FlickerAdaptiveQuantization": "DISABLED",
                                    "EntropyEncoding": "CABAC",
                                    "Bitrate": 2000000,
                                    "FramerateControl": "INITIALIZE_FROM_SOURCE",
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "MAIN",
                                    "Telecine": "NONE",
                                    "MinIInterval": 0,
                                    "AdaptiveQuantization": "HIGH",
                                    "CodecLevel": "AUTO",
                                    "FieldEncoding": "PAFF",
                                    "SceneChangeDetect": "ENABLED",
                                    "QualityTuningLevel": "SINGLE_PASS",
                                    "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                                    "UnregisteredSeiTimecode": "DISABLED",
                                    "GopSizeUnits": "FRAMES",
                                    "ParControl": "INITIALIZE_FROM_SOURCE",
                                    "NumberBFramesBetweenReferenceFrames": 2,
                                    "RepeatPps": "DISABLED"
                                }
                            },
                            "AfdSignaling": "NONE",
                            "DropFrameTimecode": "ENABLED",
                            "RespondToAfd": "NONE",
                            "ColorMetadata": "INSERT",
                            "Width": 854,
                            "Height": 480
                        },
                        "AudioDescriptions": [{
                            "AudioTypeControl": "FOLLOW_INPUT",
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "AudioDescriptionBroadcasterMix": "NORMAL",
                                    "Bitrate": 96000,
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "LC",
                                    "CodingMode": "CODING_MODE_2_0",
                                    "RawFormat": "NONE",
                                    "SampleRate": 48000,
                                    "Specification": "MPEG4"
                                }
                            },
                            "LanguageCodeControl": "FOLLOW_INPUT"
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                },
                # Premium 720p version (full video)
                {
                    "Name": "Premium_720p_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/premium/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_premium_720p",
                        "VideoDescription": {
                            "ScalingBehavior": "DEFAULT",
                            "TimecodeInsertion": "DISABLED",
                            "AntiAlias": "ENABLED",
                            "Sharpness": 50,
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "InterlaceMode": "PROGRESSIVE",
                                    "NumberReferenceFrames": 3,
                                    "Syntax": "DEFAULT",
                                    "Softness": 0,
                                    "GopClosedCadence": 1,
                                    "GopSize": 90,
                                    "Slices": 1,
                                    "GopBReference": "DISABLED",
                                    "SlowPal": "DISABLED",
                                    "SpatialAdaptiveQuantization": "ENABLED",
                                    "TemporalAdaptiveQuantization": "ENABLED",
                                    "FlickerAdaptiveQuantization": "DISABLED",
                                    "EntropyEncoding": "CABAC",
                                    "Bitrate": 4000000,
                                    "FramerateControl": "INITIALIZE_FROM_SOURCE",
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "HIGH",
                                    "Telecine": "NONE",
                                    "MinIInterval": 0,
                                    "AdaptiveQuantization": "HIGH",
                                    "CodecLevel": "AUTO",
                                    "FieldEncoding": "PAFF",
                                    "SceneChangeDetect": "ENABLED",
                                    "QualityTuningLevel": "SINGLE_PASS",
                                    "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                                    "UnregisteredSeiTimecode": "DISABLED",
                                    "GopSizeUnits": "FRAMES",
                                    "ParControl": "INITIALIZE_FROM_SOURCE",
                                    "NumberBFramesBetweenReferenceFrames": 2,
                                    "RepeatPps": "DISABLED"
                                }
                            },
                            "AfdSignaling": "NONE",
                            "DropFrameTimecode": "ENABLED",
                            "RespondToAfd": "NONE",
                            "ColorMetadata": "INSERT",
                            "Width": 1280,
                            "Height": 720
                        },
                        "AudioDescriptions": [{
                            "AudioTypeControl": "FOLLOW_INPUT",
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "AudioDescriptionBroadcasterMix": "NORMAL",
                                    "Bitrate": 128000,
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "LC",
                                    "CodingMode": "CODING_MODE_2_0",
                                    "RawFormat": "NONE",
                                    "SampleRate": 48000,
                                    "Specification": "MPEG4"
                                }
                            },
                            "LanguageCodeControl": "FOLLOW_INPUT"
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                },
                # Premium 1080p version (full video)
                {
                    "Name": "Premium_1080p_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/premium/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_premium_1080p",
                        "VideoDescription": {
                            "ScalingBehavior": "DEFAULT",
                            "TimecodeInsertion": "DISABLED",
                            "AntiAlias": "ENABLED",
                            "Sharpness": 50,
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "InterlaceMode": "PROGRESSIVE",
                                    "NumberReferenceFrames": 3,
                                    "Syntax": "DEFAULT",
                                    "Softness": 0,
                                    "GopClosedCadence": 1,
                                    "GopSize": 90,
                                    "Slices": 1,
                                    "GopBReference": "DISABLED",
                                    "SlowPal": "DISABLED",
                                    "SpatialAdaptiveQuantization": "ENABLED",
                                    "TemporalAdaptiveQuantization": "ENABLED",
                                    "FlickerAdaptiveQuantization": "DISABLED",
                                    "EntropyEncoding": "CABAC",
                                    "Bitrate": 6000000,
                                    "FramerateControl": "INITIALIZE_FROM_SOURCE",
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "HIGH",
                                    "Telecine": "NONE",
                                    "MinIInterval": 0,
                                    "AdaptiveQuantization": "HIGH",
                                    "CodecLevel": "AUTO",
                                    "FieldEncoding": "PAFF",
                                    "SceneChangeDetect": "ENABLED",
                                    "QualityTuningLevel": "SINGLE_PASS",
                                    "FramerateConversionAlgorithm": "DUPLICATE_DROP",
                                    "UnregisteredSeiTimecode": "DISABLED",
                                    "GopSizeUnits": "FRAMES",
                                    "ParControl": "INITIALIZE_FROM_SOURCE",
                                    "NumberBFramesBetweenReferenceFrames": 2,
                                    "RepeatPps": "DISABLED"
                                }
                            },
                            "AfdSignaling": "NONE",
                            "DropFrameTimecode": "ENABLED",
                            "RespondToAfd": "NONE",
                            "ColorMetadata": "INSERT",
                            "Width": 1920,
                            "Height": 1080
                        },
                        "AudioDescriptions": [{
                            "AudioTypeControl": "FOLLOW_INPUT",
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "AudioDescriptionBroadcasterMix": "NORMAL",
                                    "Bitrate": 192000,
                                    "RateControlMode": "CBR",
                                    "CodecProfile": "LC",
                                    "CodingMode": "CODING_MODE_2_0",
                                    "RawFormat": "NONE",
                                    "SampleRate": 48000,
                                    "Specification": "MPEG4"
                                }
                            },
                            "LanguageCodeControl": "FOLLOW_INPUT"
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                },
                # Thumbnail generation
                {
                    "Name": "Thumbnail_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/thumbnails/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_thumbnail",
                        "VideoDescription": {
                            "ScalingBehavior": "DEFAULT",
                            "TimecodeInsertion": "DISABLED",
                            "AntiAlias": "ENABLED",
                            "Sharpness": 50,
                            "CodecSettings": {
                                "Codec": "FRAME_CAPTURE",
                                "FrameCaptureSettings": {
                                    "FramerateNumerator": 1,
                                    "FramerateDenominator": 10,
                                    "MaxCaptures": 1,
                                    "Quality": 80
                                }
                            },
                            "Width": 1280,
                            "Height": 720
                        },
                        "ContainerSettings": {
                            "Container": "RAW"
                        }
                    }]
                }
            ]
        }
    }
    
    return job_settings

# All video metadata handling is now done by the MediaConvert completion handler
# This Lambda only creates MediaConvert jobs

# MediaConvert job completion is now handled by a separate Lambda function
# triggered by EventBridge events when jobs complete
    """Create MediaConvert job settings for all three user types"""
    
    return {
        "Role": os.environ['MEDIACONVERT_ROLE'],
        "Settings": {
            "Inputs": [{
                "FileInput": input_uri,
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "DefaultSelection": "DEFAULT"
                    }
                },
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED"
            }],
            "OutputGroups": [
                # Premium quality (full video, highest quality)
                {
                    "Name": "Premium_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/premium/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_premium_1080p",
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "Bitrate": 8000000,  # 8 Mbps
                                    "RateControlMode": "CBR",
                                    "Profile": "HIGH",
                                    "Level": "H264_LEVEL_4_1",
                                    "GopSize": 30,
                                    "NumberBFramesBetweenReferenceFrames": 2
                                }
                            },
                            "Width": 1920,
                            "Height": 1080,
                            "RespondToAfd": "NONE",
                            "ScalingBehavior": "DEFAULT"
                        },
                        "AudioDescriptions": [{
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "Bitrate": 128000,
                                    "SampleRate": 48000,
                                    "CodingMode": "CODING_MODE_2_0"
                                }
                            }
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                },
                
                # Saving plan (medium quality, with ad insertion points)
                {
                    "Name": "Saving_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/saving/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_saving_720p",
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "Bitrate": 4000000,  # 4 Mbps
                                    "RateControlMode": "CBR",
                                    "Profile": "HIGH",
                                    "Level": "H264_LEVEL_3_1",
                                    "GopSize": 30,
                                    "NumberBFramesBetweenReferenceFrames": 2
                                }
                            },
                            "Width": 1280,
                            "Height": 720,
                            "RespondToAfd": "NONE",
                            "ScalingBehavior": "DEFAULT"
                        },
                        "AudioDescriptions": [{
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "Bitrate": 96000,
                                    "SampleRate": 48000,
                                    "CodingMode": "CODING_MODE_2_0"
                                }
                            }
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                },
                
                # Trial (15 seconds, lower quality)
                {
                    "Name": "Trial_Output",
                    "OutputGroupSettings": {
                        "Type": "FILE_GROUP_SETTINGS",
                        "FileGroupSettings": {
                            "Destination": f"s3://{output_bucket}/trial/"
                        }
                    },
                    "Outputs": [{
                        "NameModifier": "_trial_480p",
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "Bitrate": 2000000,  # 2 Mbps
                                    "RateControlMode": "CBR",
                                    "Profile": "MAIN",
                                    "Level": "H264_LEVEL_3_0",
                                    "GopSize": 30
                                }
                            },
                            "Width": 854,
                            "Height": 480,
                            "RespondToAfd": "NONE",
                            "ScalingBehavior": "DEFAULT"
                        },
                        "AudioDescriptions": [{
                            "CodecSettings": {
                                "Codec": "AAC",
                                "AacSettings": {
                                    "Bitrate": 64000,
                                    "SampleRate": 48000,
                                    "CodingMode": "CODING_MODE_2_0"
                                }
                            }
                        }],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {
                                "CslgAtom": "INCLUDE",
                                "FreeSpaceBox": "EXCLUDE",
                                "MoovPlacement": "PROGRESSIVE_DOWNLOAD"
                            }
                        }
                    }]
                }
            ],
            "TimecodeConfig": {
                "Source": "ZEROBASED"
            }
        }
    }


