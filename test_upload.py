#!/usr/bin/env python3
"""
Test script for video upload functionality
"""

import requests
import json
import time
import os

# Configuration
API_BASE_URL = "http://localhost:8000"
VIDEO_FILE_PATH = "videos/speed.mp4"  # Using existing test video

def test_video_upload():
    """Test the complete video upload and processing pipeline"""
    
    print("🎬 Testing Video Upload API")
    print("=" * 50)
    
    # Check if video file exists
    if not os.path.exists(VIDEO_FILE_PATH):
        print(f"❌ Video file not found: {VIDEO_FILE_PATH}")
        print("Please update VIDEO_FILE_PATH in the script or add a video file")
        return
    
    print(f"📹 Uploading video: {VIDEO_FILE_PATH}")
    
    # Step 1: Upload video
    try:
        with open(VIDEO_FILE_PATH, 'rb') as video_file:
            files = {'video_file': ('speed.mp4', video_file, 'video/mp4')}
            response = requests.post(f"{API_BASE_URL}/api/video/upload", files=files)
        
        if response.status_code == 202:
            data = response.json()
            job_id = data['job_id']
            print(f"✅ Upload successful! Job ID: {job_id}")
            print(f"📊 Initial status: {data['status']}")
            
            # Step 2: Monitor processing status
            monitor_processing(job_id)
            
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during upload: {e}")

def monitor_processing(job_id):
    """Monitor the processing status of a job"""
    
    print(f"\n🔄 Monitoring job: {job_id}")
    print("-" * 30)
    
    max_wait_time = 600  # 10 minutes
    check_interval = 5   # Check every 5 seconds
    elapsed_time = 0
    
    while elapsed_time < max_wait_time:
        try:
            response = requests.get(f"{API_BASE_URL}/api/video/status/{job_id}")
            
            if response.status_code == 200:
                data = response.json()
                status = data['status']
                message = data['message']
                
                print(f"⏱️  [{elapsed_time:03d}s] Status: {status} - {message}")
                
                if status == "completed":
                    print("🎉 Processing completed!")
                    show_results(job_id)
                    break
                elif status == "failed":
                    print("❌ Processing failed!")
                    print(f"Error: {message}")
                    break
                    
            else:
                print(f"❌ Status check failed: {response.status_code}")
                break
                
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            break
        
        time.sleep(check_interval)
        elapsed_time += check_interval
    
    if elapsed_time >= max_wait_time:
        print("⏰ Timeout reached - processing is taking longer than expected")

def show_results(job_id):
    """Show the final results of processing"""
    
    print(f"\n📋 Final Results for Job: {job_id}")
    print("-" * 40)
    
    try:
        # Get sentiment analysis
        response = requests.get(f"{API_BASE_URL}/api/video/sentiment/{job_id}")
        if response.status_code == 200:
            sentiment_data = response.json()
            print("🧠 Sentiment Analysis:")
            print(json.dumps(sentiment_data, indent=2))
        
        # Get processed video info
        response = requests.get(f"{API_BASE_URL}/api/video/result/{job_id}")
        if response.status_code == 200:
            result_data = response.json()
            print("\n🎬 Processed Video Info:")
            print(json.dumps(result_data, indent=2))
            
            print(f"\n📥 Download URL: {API_BASE_URL}{result_data['processed_video']['download_url']}")
            print(f"🎥 Stream URL: {API_BASE_URL}{result_data['processed_video']['stream_url']}")
        
    except Exception as e:
        print(f"❌ Error getting results: {e}")

def test_health_check():
    """Test if the API is running"""
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ API is healthy and running")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Make sure the server is running: uvicorn app.main:app --reload")
        return False

def list_all_jobs():
    """List all current jobs"""
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/jobs")
        if response.status_code == 200:
            jobs = response.json()
            print("\n📋 All Jobs:")
            print(json.dumps(jobs, indent=2))
        else:
            print(f"❌ Failed to get jobs: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting jobs: {e}")

if __name__ == "__main__":
    # Test API health first
    if test_health_check():
        print()
        test_video_upload()
        print()
        list_all_jobs()
    
    print("\n" + "=" * 50)
    print("🎉 Test completed!")
    print("\nUseful endpoints:")
    print(f"📖 API Docs: {API_BASE_URL}/docs")
    print(f"📋 All Jobs: {API_BASE_URL}/api/jobs")
    print(f"❤️  Health: {API_BASE_URL}/health") 