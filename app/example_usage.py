#!/usr/bin/env python3
"""
Example usage of the TrailMixer FFmpeg stitching functionality

This file demonstrates how to use the FFmpeg processor to stitch video and audio files
together based on timestamps.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from ffmpeg import FFmpegProcessor, StitchRequest, MediaSegment, create_stitch_request_from_timestamps

def example_basic_stitching():
    """
    Example of basic video and audio stitching
    """
    print("=== Basic Stitching Example ===")
    
    try:
        # Initialize FFmpeg processor
        processor = FFmpegProcessor()
        print("✓ FFmpeg processor initialized successfully")
        
        # Example file paths (replace with actual files)
        video_path = "example_video.mp4"
        audio_path = "example_audio.mp3"
        output_path = "output_stitched.mp4"
        
        # Check if files exist
        if not os.path.exists(video_path):
            print(f"⚠️  Video file not found: {video_path}")
            print("   Please provide a valid video file path")
            return
        
        if not os.path.exists(audio_path):
            print(f"⚠️  Audio file not found: {audio_path}")
            print("   Please provide a valid audio file path")
            return
        
        # Get media information
        print(f"\n📹 Getting media info for: {video_path}")
        video_info = processor.get_media_info(video_path)
        video_duration = float(video_info['format']['duration'])
        print(f"   Video duration: {video_duration:.2f} seconds")
        
        print(f"🎵 Getting media info for: {audio_path}")
        audio_info = processor.get_media_info(audio_path)
        audio_duration = float(audio_info['format']['duration'])
        print(f"   Audio duration: {audio_duration:.2f} seconds")
        
        # Create segments for stitching
        segments = [
            MediaSegment(
                file_path=video_path,
                start_time=0.0,
                end_time=video_duration,
                media_type='video'
            ),
            MediaSegment(
                file_path=audio_path,
                start_time=0.0,
                end_time=audio_duration,
                media_type='audio'
            )
        ]
        
        # Create stitch request
        stitch_request = StitchRequest(
            segments=segments,
            output_path=output_path,
            output_format='mp4',
            video_codec='libx264',
            audio_codec='aac',
            video_bitrate='2M',
            audio_bitrate='128k'
        )
        
        print(f"\n🔧 Starting stitching process...")
        print(f"   Output: {output_path}")
        
        # Perform stitching
        success = processor.stitch_segments(stitch_request)
        
        if success:
            print("✅ Stitching completed successfully!")
            print(f"   Output file: {output_path}")
        else:
            print("❌ Stitching failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def example_timestamp_based_stitching():
    """
    Example of stitching with specific timestamps
    """
    print("\n=== Timestamp-Based Stitching Example ===")
    
    try:
        processor = FFmpegProcessor()
        
        # Example: Add multiple audio segments at specific times
        video_path = "example_video.mp4"
        output_path = "output_timestamped.mp4"
        
        # Define audio segments with timestamps
        audio_segments = [
            {
                'file_path': 'audio1.mp3',
                'start_time': 0.0,    # Start at beginning
                'end_time': 10.0      # End at 10 seconds
            },
            {
                'file_path': 'audio2.mp3',
                'start_time': 15.0,   # Start at 15 seconds
                'end_time': 25.0      # End at 25 seconds
            },
            {
                'file_path': 'audio3.mp3',
                'start_time': 30.0,   # Start at 30 seconds
                'end_time': 40.0      # End at 40 seconds
            }
        ]
        
        # Create stitch request using utility function
        stitch_request = create_stitch_request_from_timestamps(
            video_path=video_path,
            audio_segments=audio_segments,
            output_path=output_path,
            video_codec='libx264',
            audio_codec='aac'
        )
        
        print(f"🔧 Stitching video with {len(audio_segments)} audio segments...")
        
        success = processor.stitch_segments(stitch_request)
        
        if success:
            print("✅ Timestamp-based stitching completed!")
        else:
            print("❌ Timestamp-based stitching failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def example_add_audio_to_video():
    """
    Example of adding audio to video with delay
    """
    print("\n=== Add Audio to Video Example ===")
    
    try:
        processor = FFmpegProcessor()
        
        video_path = "example_video.mp4"
        audio_path = "background_music.mp3"
        output_path = "output_with_audio.mp4"
        
        # Add audio starting at 5 seconds into the video
        audio_start_time = 5.0
        
        print(f"🔧 Adding audio to video with {audio_start_time}s delay...")
        
        success = processor.add_audio_to_video(
            video_path=video_path,
            audio_path=audio_path,
            output_path=output_path,
            audio_start_time=audio_start_time
        )
        
        if success:
            print("✅ Audio added successfully!")
        else:
            print("❌ Failed to add audio!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def example_create_silent_audio():
    """
    Example of creating silent audio
    """
    print("\n=== Create Silent Audio Example ===")
    
    try:
        processor = FFmpegProcessor()
        
        # Create 10 seconds of silent audio
        duration = 10.0
        output_path = "silent_audio.mp3"
        
        print(f"🔧 Creating {duration}s of silent audio...")
        
        success = processor.create_silent_audio(
            duration=duration,
            output_path=output_path,
            sample_rate=44100
        )
        
        if success:
            print("✅ Silent audio created successfully!")
        else:
            print("❌ Failed to create silent audio!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """
    Run all examples
    """
    print("🎬 TrailMixer FFmpeg Examples")
    print("=" * 50)
    
    # Check if FFmpeg is available
    try:
        processor = FFmpegProcessor()
        print("✓ FFmpeg is available")
    except RuntimeError as e:
        print(f"❌ FFmpeg not available: {e}")
        print("   Please install FFmpeg and ensure it's in your PATH")
        return
    
    # Run examples
    example_basic_stitching()
    example_timestamp_based_stitching()
    example_add_audio_to_video()
    example_create_silent_audio()
    
    print("\n" + "=" * 50)
    print("🎉 Examples completed!")
    print("\nTo use the FastAPI endpoints:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the server: uvicorn app.main:app --reload")
    print("3. Visit: http://localhost:8000/docs for API documentation")

if __name__ == "__main__":
    main() 