#!/usr/bin/env python3
"""
Test script to verify TrailMixer FFmpeg setup

This script tests the basic functionality of the FFmpeg integration
without requiring actual media files.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

def test_ffmpeg_installation():
    """Test if FFmpeg is properly installed"""
    print("🔍 Testing FFmpeg installation...")
    
    try:
        # Try to run ffmpeg -version
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, check=True)
        print("✅ FFmpeg is installed and accessible")
        print(f"   Version: {result.stdout.split('ffmpeg version')[1].split()[0]}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found or not accessible")
        print("   Please install FFmpeg and ensure it's in your PATH")
        return False

def test_ffprobe_installation():
    """Test if FFprobe is properly installed"""
    print("\n🔍 Testing FFprobe installation...")
    
    try:
        # Try to run ffprobe -version
        result = subprocess.run(['ffprobe', '-version'], 
                              capture_output=True, text=True, check=True)
        print("✅ FFprobe is installed and accessible")
        print(f"   Version: {result.stdout.split('ffprobe version')[1].split()[0]}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFprobe not found or not accessible")
        print("   FFprobe should be included with FFmpeg installation")
        return False

def test_ffmpeg_module():
    """Test the FFmpeg module imports and basic functionality"""
    print("\n🔍 Testing FFmpeg module...")
    
    try:
        from app.ffmpeg_stitch import stitch_ffmpeg_request
        from app.models import FfmpegRequest, InputSegment, AudioCodec, VideoCodec
        print("✅ FFmpeg module imports successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import FFmpeg module: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_fastapi_imports():
    """Test FastAPI imports"""
    print("\n🔍 Testing FastAPI imports...")
    
    try:
        import fastapi
        from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
        from fastapi.responses import JSONResponse, FileResponse
        from pydantic import BaseModel
        print("✅ FastAPI imports successful")
        return True
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        print("   Run: pip install fastapi uvicorn python-multipart")
        return False

def test_directory_structure():
    """Test if required directories exist or can be created"""
    print("\n🔍 Testing directory structure...")
    
    required_dirs = ['uploads', 'outputs']
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"✅ Directory exists: {dir_name}")
        else:
            try:
                dir_path.mkdir(exist_ok=True)
                print(f"✅ Directory created: {dir_name}")
            except Exception as e:
                print(f"❌ Failed to create directory {dir_name}: {e}")
                return False
    
    return True

def test_silent_audio_creation():
    """Test creating silent audio (doesn't require input files)"""
    print("\n🔍 Testing silent audio creation...")
    
    try:
        from app.ffmpeg_stitch import stitch_ffmpeg_request
        from app.models import FfmpegRequest, InputSegment, AudioCodec
        
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
            temp_path = tmp_file.name
        
        try:
            # Create 2 seconds of silent audio using ffmpeg directly
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-t', '2', '-c:a', 'libmp3lame', '-b:a', '128k', temp_path, '-y', '-loglevel', 'error'
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            file_size = os.path.getsize(temp_path)
            print(f"✅ Silent audio created successfully ({file_size} bytes)")
            return True
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except Exception as e:
        print(f"❌ Silent audio test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 TrailMixer Setup Test")
    print("=" * 50)
    
    tests = [
        ("FFmpeg Installation", test_ffmpeg_installation),
        ("FFprobe Installation", test_ffprobe_installation),
        ("FFmpeg Module", test_ffmpeg_module),
        ("FastAPI Imports", test_fastapi_imports),
        ("Directory Structure", test_directory_structure),
        ("Silent Audio Creation", test_silent_audio_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! TrailMixer is ready to use.")
        print("\nNext steps:")
        print("1. Start the server: uvicorn app.main:app --reload")
        print("2. Visit: http://localhost:8000/docs")
        print("3. Try the example usage: python app/example_usage.py")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon solutions:")
        print("- Install FFmpeg: https://ffmpeg.org/download.html")
        print("- Install Python dependencies: pip install -r requirements.txt")
        print("- Check file permissions for upload/output directories")

if __name__ == "__main__":
    main() 