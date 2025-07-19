#!/usr/bin/env python3
"""
Quick test script for TrailMixer FFmpeg pipeline

This script provides a simple way to test the basic functionality
without running the full test suite.

Usage:
    python quick_test.py                      # Run with generated test files
    python quick_test.py --audio input.mp3    # Test with custom audio file
    python quick_test.py --video input.mp4    # Test with custom video file
    python quick_test.py --audio in.mp3 --video in.mp4  # Test with both
    
Time format: HH:MM:SS or HH:MM:SS.mmm
Examples:
    --audio-start 00:00:10 --audio-end 00:01:30  # Trim audio from 10s to 1m30s
    --video-start 00:01:00 --video-end 00:02:00  # Trim video from 1m to 2m
"""

import os
import sys
import tempfile
import subprocess
import argparse
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test TrailMixer FFmpeg pipeline")
    parser.add_argument('--audio', type=str, help='Path to input audio file')
    parser.add_argument('--video', type=str, help='Path to input video file')
    parser.add_argument('--audio-start', type=str, default="00:00:00", 
                       help='Start time for audio (format: HH:MM:SS or HH:MM:SS.mmm)')
    parser.add_argument('--audio-end', type=str, default="23:59:59", 
                       help='End time for audio (format: HH:MM:SS or HH:MM:SS.mmm)')
    parser.add_argument('--video-start', type=str, default="00:00:00", 
                       help='Start time for video (format: HH:MM:SS or HH:MM:SS.mmm)')
    parser.add_argument('--video-end', type=str, default="23:59:59", 
                       help='End time for video (format: HH:MM:SS or HH:MM:SS.mmm)')
    return parser.parse_args()

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
    """Create simple test files if no input files provided"""
    print(f"📁 Creating test files in: {test_dir}")
    
    # Create a simple audio file (1 second of silence)
    audio_path = test_dir / "test_audio.mp3"
    try:
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
            '-t', '1', '-c:a', 'libmp3lame', '-b:a', '128k', str(audio_path), '-y', '-loglevel', 'error'
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

def setup_test_files(args, temp_dir):
    """Set up test files based on command line args or create new ones"""
    test_files = {}
    
    if args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            print(f"⚠️  Audio file not found: {audio_path}")
        else:
            test_files['audio'] = str(audio_path)
            print(f"✅ Using audio file: {audio_path}")
            
    if args.video:
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"⚠️  Video file not found: {video_path}")
        else:
            test_files['video'] = str(video_path)
            print(f"✅ Using video file: {video_path}")
            
    # If no valid files provided, create test files
    if not test_files:
        print("ℹ️  No input files provided, creating test files...")
        test_files = create_test_files(temp_dir)
        
    return test_files

def test_imports():
    """Test if we can import the required modules"""
    print("\n🔍 Testing imports...")
    
    try:
        from app.ffmpeg import stitch_ffmpeg_request
        from app.models import FfmpegRequest, InputSegment, AudioCodec, VideoCodec
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_audio_processing(test_files, args):
    """Test basic audio processing"""
    print("\n🎵 Testing audio processing...")
    
    if not test_files or 'audio' not in test_files:
        print("⚠️  Skipping audio test - no test file available")
        return False
    
    try:
        from app.ffmpeg import stitch_ffmpeg_request
        from app.models import FfmpegRequest, InputSegment, AudioCodec, VideoCodec
        
        output_path = Path(test_files['audio']).parent / "output_audio.mp3"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=test_files['audio'],
                    file_type='audio',
                    start_time=args.audio_start,
                    end_time=args.audio_end,
                    volume=0.5,
                    fade_in=None,
                    fade_out=None,
                    metadata=None
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.MP3,
            audio_bitrate="128k",  # Added bitrate for MP3
            quiet=False,  # Keep FFmpeg output visible
            video_codec=VideoCodec.H264,  # This won't be used for audio-only
            video_bitrate=None,
            crf=None,
            preset="medium",
            scale=None,
            fps=None,
            audio_channels=2,
            audio_sample_rate=44100,
            global_volume=1.0,
            normalize_audio=False,
            crossfade_duration=None,
            gap_duration="00:00:00",
            overwrite=True,
            progress=True,
            request_id=None,
            priority=1
        )
        
        result = stitch_ffmpeg_request(request)
        print(f"✅ Audio processing successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Audio processing failed:\n{str(e)}")
        return False

def test_video_processing(test_files, args):
    """Test basic video processing"""
    print("\n🎬 Testing video processing...")
    
    if not test_files or 'video' not in test_files:
        print("⚠️  Skipping video test - no test file available")
        return False
    
    try:
        from app.ffmpeg import stitch_ffmpeg_request
        from app.models import FfmpegRequest, InputSegment, VideoCodec, AudioCodec
        
        output_path = Path(test_files['video']).parent / "output_video.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=test_files['video'],
                    file_type='video',
                    start_time=args.video_start,
                    end_time=args.video_end,
                    fade_in="0.5",
                    fade_out="0.5",
                    volume=1.0,
                    metadata=None
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            quiet=False,  # Keep FFmpeg output visible
            audio_codec=AudioCodec.AAC,  # This won't be used for video-only
            video_bitrate=None,
            audio_bitrate=None,
            crf=None,
            preset="medium",
            scale=None,
            fps=None,
            audio_channels=2,
            audio_sample_rate=44100,
            global_volume=1.0,
            normalize_audio=False,
            crossfade_duration=None,
            gap_duration="00:00:00",
            overwrite=True,
            progress=True,
            request_id=None,
            priority=1
        )
        
        result = stitch_ffmpeg_request(request)
        print(f"✅ Video processing successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Video processing failed:\n{str(e)}")
        return False

def test_combined_processing(test_files, args):
    """Test combining video and audio"""
    print("\n🎭 Testing video + audio processing...")
    
    if not test_files or 'video' not in test_files or 'audio' not in test_files:
        print("⚠️  Skipping combined test - missing test files")
        return False
    
    try:
        from app.ffmpeg import stitch_ffmpeg_request
        from app.models import FfmpegRequest, InputSegment, VideoCodec, AudioCodec
        
        output_path = Path(test_files['video']).parent / "output_combined.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=test_files['video'],
                    file_type='video',
                    start_time=args.video_start,
                    end_time=args.video_end,
                    volume=0.5,  # Reduce volume of video's audio
                    fade_in=None,
                    fade_out=None,
                    metadata=None
                ),
                InputSegment(
                    file_path=test_files['video'],
                    file_type='audio',  # Extract audio from video
                    start_time=args.video_start,
                    end_time=args.video_end,
                    volume=0.5,  # Mix with the other audio at half volume
                    fade_in=None,
                    fade_out=None,
                    metadata=None
                ),
                InputSegment(
                    file_path=test_files['audio'],
                    file_type='audio',
                    start_time=args.audio_start,
                    end_time=args.audio_end,
                    volume=0.5,  # Mix at half volume
                    fade_in=None,
                    fade_out=None,
                    metadata=None
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            quiet=False,
            video_bitrate=None,
            audio_bitrate="192k",  # Higher quality for mixed audio
            crf=None,
            preset="medium",
            scale=None,
            fps=None,
            audio_channels=2,
            audio_sample_rate=44100,
            global_volume=1.0,
            normalize_audio=True,  # Normalize the mixed audio
            crossfade_duration=None,
            gap_duration="00:00:00",
            overwrite=True,
            progress=True,
            request_id=None,
            priority=1
        )
        
        result = stitch_ffmpeg_request(request)
        print(f"✅ Combined processing successful: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Combined processing failed:\n{str(e)}")
        return False

def main():
    """Run quick tests"""
    print("🚀 TrailMixer Quick Test")
    print("=" * 40)
    
    # Parse command line arguments
    args = parse_args()
    
    # Check FFmpeg installation
    if not check_ffmpeg():
        return
    
    # Test imports
    if not test_imports():
        return
    
    # Create temporary directory for test files and outputs
    with tempfile.TemporaryDirectory(prefix="trailmixer_quick_") as temp_dir:
        test_dir = Path(temp_dir)
        
        # Set up test files (from args or create new ones)
        test_files = setup_test_files(args, test_dir)
        
        if not test_files:
            print("⚠️  Could not set up test files. Tests will be skipped.")
            return
        
        # Run tests
        tests = []
        
        # Add tests based on available files
        if 'audio' in test_files:
            tests.append(("Audio Processing", lambda: test_audio_processing(test_files, args)))
        if 'video' in test_files:
            tests.append(("Video Processing", lambda: test_video_processing(test_files, args)))
        if 'audio' in test_files and 'video' in test_files:
            tests.append(("Combined Processing", lambda: test_combined_processing(test_files, args)))
        
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