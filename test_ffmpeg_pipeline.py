#!/usr/bin/env python3
"""
Comprehensive test suite for TrailMixer FFmpeg pipeline

This test suite covers:
- Unit tests for individual functions
- Integration tests for the complete pipeline
- Sample media file generation for testing
- Error handling and edge cases
"""

import os
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from typing import List, Dict, Any
import json

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

from ffmpeg import stitch_ffmpeg_request
from models import FfmpegRequest, InputSegment, AudioCodec, VideoCodec

class TestFFmpegPipeline(unittest.TestCase):
    """Test suite for FFmpeg pipeline functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="trailmixer_test_"))
        self.sample_files = {}
        
        # Create sample media files for testing
        self._create_sample_files()
    
    def tearDown(self):
        """Clean up test environment"""
        # Remove test directory and all files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_sample_files(self):
        """Create sample audio and video files for testing"""
        print(f"Creating sample files in: {self.test_dir}")
        
        # Create sample audio file (1 second of silence)
        audio_path = self.test_dir / "sample_audio.wav"
        self._create_silent_audio(audio_path, duration=1.0)
        self.sample_files['audio'] = str(audio_path)
        
        # Create sample video file (1 second of black video)
        video_path = self.test_dir / "sample_video.mp4"
        self._create_test_video(video_path, duration=1.0)
        self.sample_files['video'] = str(video_path)
        
        # Create longer audio file for testing
        long_audio_path = self.test_dir / "long_audio.wav"
        self._create_silent_audio(long_audio_path, duration=3.0)
        self.sample_files['long_audio'] = str(long_audio_path)
        
        # Create longer video file for testing
        long_video_path = self.test_dir / "long_video.mp4"
        self._create_test_video(long_video_path, duration=3.0)
        self.sample_files['long_video'] = str(long_video_path)
    
    def _create_silent_audio(self, output_path: Path, duration: float):
        """Create a silent audio file using FFmpeg"""
        try:
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-t', str(duration), '-c:a', 'pcm_s16le', str(output_path), '-y'
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not create sample audio file: {e}")
            # Create a dummy file for testing
            output_path.write_bytes(b'dummy audio file')
    
    def _create_test_video(self, output_path: Path, duration: float):
        """Create a test video file using FFmpeg"""
        try:
            cmd = [
                'ffmpeg', '-f', 'lavfi', '-i', f'color=c=black:s=320x240:r=30',
                '-t', str(duration), '-c:v', 'libx264', '-preset', 'ultrafast',
                str(output_path), '-y'
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not create sample video file: {e}")
            # Create a dummy file for testing
            output_path.write_bytes(b'dummy video file')
    
    def test_ffmpeg_installation(self):
        """Test if FFmpeg is properly installed"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, check=True)
            self.assertIn('ffmpeg version', result.stdout)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("FFmpeg not installed or not in PATH")
    
    def test_basic_audio_processing(self):
        """Test basic audio processing with volume adjustment"""
        output_path = self.test_dir / "output_audio.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='audio',
                    volume=0.5,
                    fade_in="0.1",
                    fade_out="0.1"
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
        except Exception as e:
            self.fail(f"Audio processing failed: {e}")
    
    def test_basic_video_processing(self):
        """Test basic video processing with scaling"""
        output_path = self.test_dir / "output_video.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['video'],
                    file_type='video',
                    fade_in="0.1",
                    fade_out="0.1"
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            scale="640:480",
            fps=30.0,
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
        except Exception as e:
            self.fail(f"Video processing failed: {e}")
    
    def test_audio_mixing(self):
        """Test mixing multiple audio streams"""
        output_path = self.test_dir / "mixed_audio.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='audio',
                    volume=0.7
                ),
                InputSegment(
                    file_path=self.sample_files['long_audio'],
                    file_type='audio',
                    volume=0.3
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            global_volume=1.0,
            normalize_audio=True,
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
        except Exception as e:
            self.fail(f"Audio mixing failed: {e}")
    
    def test_video_with_audio(self):
        """Test combining video with audio"""
        output_path = self.test_dir / "video_with_audio.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['video'],
                    file_type='video'
                ),
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='audio'
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            crf=23,
            preset="ultrafast",
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
        except Exception as e:
            self.fail(f"Video with audio processing failed: {e}")
    
    def test_segment_timing(self):
        """Test segment timing with start_time and end_time"""
        output_path = self.test_dir / "timed_segment.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['long_audio'],
                    file_type='audio',
                    start_time="00:00:01",  # Start at 1 second
                    end_time="00:00:02",    # End at 2 seconds (1 second duration)
                    volume=0.8
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
        except Exception as e:
            self.fail(f"Segment timing failed: {e}")
    
    def test_error_handling_invalid_file(self):
        """Test error handling with invalid input file"""
        output_path = self.test_dir / "error_test.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path="nonexistent_file.wav",
                    file_type='audio'
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            quiet=True
        )
        
        with self.assertRaises(RuntimeError):
            stitch_ffmpeg_request(request)
    
    def test_error_handling_invalid_segment_type(self):
        """Test error handling with invalid segment type"""
        output_path = self.test_dir / "error_test.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='invalid_type'  # Invalid type
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            quiet=True
        )
        
        # This should still work as the filter logic handles unknown types
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
        except Exception as e:
            self.fail(f"Unexpected error with invalid segment type: {e}")
    
    def test_quality_settings(self):
        """Test different quality settings"""
        output_path = self.test_dir / "quality_test.mp4"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['video'],
                    file_type='video'
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            crf=18,  # High quality
            preset="slow",
            video_bitrate="1M",
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
        except Exception as e:
            self.fail(f"Quality settings test failed: {e}")
    
    def test_audio_settings(self):
        """Test audio-specific settings"""
        output_path = self.test_dir / "audio_settings.wav"
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='audio'
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            audio_bitrate="256k",
            audio_channels=1,  # Mono
            audio_sample_rate=48000,
            quiet=True
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
        except Exception as e:
            self.fail(f"Audio settings test failed: {e}")


def run_performance_test():
    """Run performance tests with larger files"""
    print("\n🚀 Running Performance Tests...")
    
    # Create larger test files
    test_dir = Path(tempfile.mkdtemp(prefix="trailmixer_perf_"))
    
    try:
        # Create 10-second test files
        audio_path = test_dir / "perf_audio.wav"
        video_path = test_dir / "perf_video.mp4"
        
        # Create test files
        cmd_audio = [
            'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
            '-t', '10', '-c:a', 'pcm_s16le', str(audio_path), '-y'
        ]
        cmd_video = [
            'ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=30',
            '-t', '10', '-c:v', 'libx264', '-preset', 'ultrafast', str(video_path), '-y'
        ]
        
        subprocess.run(cmd_audio, check=True, capture_output=True)
        subprocess.run(cmd_video, check=True, capture_output=True)
        
        # Test processing time
        import time
        
        output_path = test_dir / "perf_output.mp4"
        request = FfmpegRequest(
            input_segments=[
                InputSegment(file_path=str(video_path), file_type='video'),
                InputSegment(file_path=str(audio_path), file_type='audio')
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            crf=23,
            preset="medium"
        )
        
        start_time = time.time()
        result = stitch_ffmpeg_request(request)
        end_time = time.time()
        
        processing_time = end_time - start_time
        print(f"✅ Performance test completed in {processing_time:.2f} seconds")
        print(f"   Output file: {result}")
        
        if output_path.exists():
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            print(f"   Output size: {file_size:.2f} MB")
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
    finally:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


def main():
    """Run all tests"""
    print("🧪 TrailMixer FFmpeg Pipeline Test Suite")
    print("=" * 60)
    
    # Check FFmpeg installation first
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True)
        print("✅ FFmpeg is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found. Please install FFmpeg first.")
        print("   Download from: https://ffmpeg.org/download.html")
        return
    
    # Run unit tests
    print("\n📋 Running Unit Tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run performance tests
    run_performance_test()
    
    print("\n" + "=" * 60)
    print("🎉 Test suite completed!")
    print("\nTo run specific tests:")
    print("  python test_ffmpeg_pipeline.py -k test_basic_audio_processing")
    print("\nTo run with more verbose output:")
    print("  python test_ffmpeg_pipeline.py -v")


if __name__ == "__main__":
    main() 