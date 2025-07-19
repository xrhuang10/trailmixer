#!/usr/bin/env python3
"""
Quick test script for TrailMixer FFmpeg pipeline

This script provides a simple way to test the basic functionality
without running the full test suite.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, check=True)
        version = result.stdout.split('ffmpeg version')[1].split()[0]
        print(f"✅ FFmpeg found: {version}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found. Please install FFmpeg first.")
        print("   Download from: https://ffmpeg.org/download.html")
        return False

def create_test_files(test_dir):
    """Create simple test files"""
    print(f"📁 Creating test files in: {test_dir}")
    
    # Create a simple audio file (1 second of silence)
    audio_path = test_dir / "test_audio.wav"
    try:
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
            '-t', '1', '-c:a', 'pcm_s16le', str(audio_path), '-y', '-loglevel', 'error'
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Created test audio: {audio_path}")
    except subprocess.CalledProcessError:
        print(f"⚠️  Could not create test audio file")
        return None
    
    # Create a simple video file (1 second of black video)
    video_path = test_dir / "test_video.mp4"
    try:
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=320x240:r=30',
            '-t', '1', '-c:v', 'libx264', '-preset', 'ultrafast',
            str(video_path), '-y', '-loglevel', 'error'
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Created test video: {video_path}")
    except subprocess.CalledProcessError:
        print(f"⚠️  Could not create test video file")
        return None
    
    return {
        'audio': str(audio_path),
        'video': str(video_path)
    }

def test_imports():
    """Test if we can import the required modules"""
    print("\n🔍 Testing imports...")
    
    try:
        from ffmpeg import stitch_ffmpeg_request
        from models import FfmpegRequest, InputSegment, AudioCodec, VideoCodec
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_audio_processing(test_files):
    """Test basic audio processing"""
    print("\n🎵 Testing audio processing...")
    
    if not test_files or 'audio' not in test_files:
        print("⚠️  Skipping audio test - no test file available")
        return False
    
    try:
        from ffmpeg import stitch_ffmpeg_request
        from models import FfmpegRequest, InputSegment, AudioCodec
        
        output_path = Path(test_files['audio']).parent / "output_audio.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=test_files['audio'],
                    file_type='audio',
                    start_time="00:00:00",
                    end_time="00:00:01",  # 1 second
                    volume=0.5
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            quiet=True
        )
        
        result = stitch_ffmpeg_request(request)
        print(f"✅ Audio processing successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Audio processing failed: {e}")
        return False

def test_video_processing(test_files):
    """Test basic video processing"""
    print("\n🎬 Testing video processing...")
    
    if not test_files or 'video' not in test_files:
        print("⚠️  Skipping video test - no test file available")
        return False
    
    try:
        from ffmpeg import stitch_ffmpeg_request
        from models import FfmpegRequest, InputSegment, VideoCodec
        
        output_path = Path(test_files['video']).parent / "output_video.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=test_files['video'],
                    file_type='video',
                    start_time="00:00:00",
                    end_time="00:00:01",  # 1 second
                    fade_in="0.1",
                    fade_out="0.1"
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            quiet=True
        )
        
        result = stitch_ffmpeg_request(request)
        print(f"✅ Video processing successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Video processing failed: {e}")
        return False

def test_combined_processing(test_files):
    """Test combining video and audio"""
    print("\n🎭 Testing video + audio processing...")
    
    if not test_files or 'video' not in test_files or 'audio' not in test_files:
        print("⚠️  Skipping combined test - missing test files")
        return False
    
    try:
        from ffmpeg import stitch_ffmpeg_request
        from models import FfmpegRequest, InputSegment, VideoCodec, AudioCodec
        
        output_path = Path(test_files['video']).parent / "output_combined.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=test_files['video'],
                    file_type='video',
                    start_time="00:00:00",
                    end_time="00:00:01"  # 1 second
                ),
                InputSegment(
                    file_path=test_files['audio'],
                    file_type='audio',
                    start_time="00:00:00",
                    end_time="00:00:01"  # 1 second
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            quiet=True
        )
        
        result = stitch_ffmpeg_request(request)
        print(f"✅ Combined processing successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Combined processing failed: {e}")
        return False

def main():
    """Run quick tests"""
    print("🚀 TrailMixer Quick Test")
    print("=" * 40)
    
    # Check FFmpeg installation
    if not check_ffmpeg():
        return
    
    # Test imports
    if not test_imports():
        return
    
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory(prefix="trailmixer_quick_") as temp_dir:
        test_dir = Path(temp_dir)
        
        # Create test files
        test_files = create_test_files(test_dir)
        
        if not test_files:
            print("⚠️  Could not create test files. Some tests will be skipped.")
        
        # Run tests
        tests = [
            ("Audio Processing", lambda: test_audio_processing(test_files)),
            ("Video Processing", lambda: test_video_processing(test_files)),
            ("Combined Processing", lambda: test_combined_processing(test_files)),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                print(f"❌ {test_name} crashed: {e}")
        
        print("\n" + "=" * 40)
        print(f"📊 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Your FFmpeg pipeline is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the output above for details.")
        
        print("\n💡 Next steps:")
        print("1. Run the full test suite: python test_ffmpeg_pipeline.py")
        print("2. Try the example usage: python app/example_usage.py")
        print("3. Start the API server: uvicorn app.main:app --reload")

if __name__ == "__main__":
    main() 