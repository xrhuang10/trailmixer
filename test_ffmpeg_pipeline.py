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
import ffmpeg

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

from app.ffmpeg_stitch import stitch_ffmpeg_request
from app.models import FfmpegRequest, InputSegment, AudioCodec, VideoCodec

def _get_default_request_params():
    """Get default parameters for FfmpegRequest"""
    return {
        'video_codec': VideoCodec.H264,
        'video_bitrate': None,
        'audio_bitrate': None,
        'crf': None,
        'preset': "medium",
        'scale': None,
        'fps': None,
        'audio_channels': 2,
        'audio_sample_rate': 44100,
        'global_volume': 1.0,
        'normalize_audio': False,
        'crossfade_duration': None,
        'gap_duration': "00:00:00",
        'overwrite': True,
        'progress': True,
        'request_id': None,
        'priority': 1,
        'quiet': True
    }

def _get_default_segment_params():
    """Get default parameters for InputSegment"""
    return {
        'start_time': "00:00:00",
        'clip_start': "00:00:00",
        'clip_end': None,
        'volume': 1.0,
        'fade_in': None,
        'fade_out': None,
        'metadata': None
    }

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
            # Create a more reliable test video with both video and audio
            cmd = [
                'ffmpeg',
                # Video input
                '-f', 'lavfi', '-i', f'color=c=blue:s=320x240:r=30',
                # Audio input
                '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                # Duration
                '-t', str(duration),
                # Video codec settings
                '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage',
                # Audio codec settings
                '-c:a', 'aac', '-b:a', '128k',
                # Force overwrite and suppress output
                '-y', '-hide_banner', '-loglevel', 'error',
                str(output_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Verify the file was created and is valid
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("Failed to create valid test video")
                
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not create sample video file: {e}")
            print(f"FFmpeg stderr: {e.stderr.decode() if e.stderr else 'No error output'}")
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
                    fade_out="0.1",
                    end_time="00:00:01",  # 1 second duration
                    start_time="00:00:00",
                    clip_start="00:00:00",
                    clip_end="00:00:01",
                    metadata=None
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            video_codec=VideoCodec.H264,
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
            priority=1,
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
        
        # Start with default params
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        # Update specific parameters we want to change
        segment_params.update({
            'fade_in': "0.5",
            'fade_out': "0.5",
            'end_time': "00:00:01"
        })
        
        # Remove params that will be set directly
        params.pop('video_codec', None)
        params.pop('audio_codec', None)
        params.pop('scale', None)
        params.pop('fps', None)
        params.pop('preset', None)
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['video'],
                    file_type='video',
                    **segment_params
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            scale="320:240",  # Match input size
            fps=30.0,
            preset="ultrafast",  # Use fastest preset for testing
            **params
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
            
            # Verify the file is a valid video
            probe = ffmpeg.probe(str(output_path))
            self.assertIn('streams', probe)
            self.assertTrue(any(s['codec_type'] == 'video' for s in probe['streams']))
        except Exception as e:
            self.fail(f"Video processing failed: {e}")
    
    def test_audio_mixing(self):
        """Test mixing multiple audio streams"""
        output_path = self.test_dir / "mixed_audio.wav"
        
        # Start with default params
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        # Create first segment params
        first_segment_params = segment_params.copy()
        first_segment_params.update({
            'volume': 0.7,
            'end_time': "00:00:03"
        })
        
        # Create second segment params
        second_segment_params = segment_params.copy()
        second_segment_params.update({
            'volume': 0.3,
            'end_time': "00:00:03"
        })
        
        # Update request params
        params.update({
            'audio_codec': AudioCodec.WAV,
            'global_volume': 1.0,
            'normalize_audio': True
        })
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='audio',
                    **first_segment_params
                ),
                InputSegment(
                    file_path=self.sample_files['long_audio'],
                    file_type='audio',
                    **second_segment_params
                )
            ],
            output_file=str(output_path),
            **params
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
        except Exception as e:
            self.fail(f"Audio mixing failed: {e}")
    
    def test_video_with_audio(self):
        """Test combining video with audio"""
        output_path = self.test_dir / "video_with_audio.mp4"
        
        # Start with default params
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        # Create video segment params
        video_segment_params = segment_params.copy()
        video_segment_params.update({
            'end_time': "00:00:03",
            'volume': 0.0  # Mute original audio
        })
        
        # Create audio segment params
        audio_segment_params = segment_params.copy()
        audio_segment_params.update({
            'end_time': "00:00:03",
            'volume': 1.0,
            'fade_in': "0.5",
            'fade_out': "0.5"
        })
        
        # Update request params
        params.update({
            'video_codec': VideoCodec.H264,
            'audio_codec': AudioCodec.AAC,
            'normalize_audio': True
        })
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['long_video'],
                    file_type='video',
                    **video_segment_params
                ),
                InputSegment(
                    file_path=self.sample_files['long_audio'],
                    file_type='audio',
                    **audio_segment_params
                )
            ],
            output_file=str(output_path),
            **params
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
        except Exception as e:
            self.fail(f"Video with audio processing failed: {e}")
    
    def test_segment_timing(self):
        """Test segment timing with start_time and end_time"""
        output_path = self.test_dir / "timed_output.wav"
        
        # Start with default params
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        # Remove params that will be set directly
        params.pop('audio_codec', None)
        
        # Remove timing params that will be set directly
        segment_params.pop('start_time', None)
        segment_params.pop('clip_start', None)
        segment_params.pop('clip_end', None)
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['long_audio'],
                    file_type='audio',
                    start_time="00:00:00",  # Start at beginning of output
                    end_time="00:00:02",    # End at 2 seconds
                    clip_start="00:00:01",  # Start from 1 second in source
                    clip_end="00:00:03",    # Use 2 seconds from source
                    **segment_params
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,  # Use WAV for testing
            **params
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
            
            # Verify the file is a valid audio file
            probe = ffmpeg.probe(str(output_path))
            self.assertIn('streams', probe)
            self.assertTrue(any(s['codec_type'] == 'audio' for s in probe['streams']))
            
            # Verify duration is approximately 2 seconds
            duration = float(probe['format']['duration'])
            self.assertAlmostEqual(duration, 2.0, delta=0.1)
        except Exception as e:
            self.fail(f"Segment timing test failed: {e}")
    
    def test_error_handling_invalid_file(self):
        """Test error handling with invalid input file"""
        output_path = self.test_dir / "error_test.wav"
        
        params = _get_default_request_params()
        segment_params = _get_default_segment_params()
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path="nonexistent_file.wav",
                    file_type='audio',
                    end_time="00:00:01",  # 1 second duration
                    **segment_params
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.WAV,
            **params
        )
        
        with self.assertRaises(RuntimeError):
            stitch_ffmpeg_request(request)
    
    def test_error_handling_invalid_segment_type(self):
        """Test error handling with invalid segment type"""
        output_path = self.test_dir / "invalid_type.mp4"
        
        # Get default parameters
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['video'],
                    file_type='invalid_type',  # Invalid type
                    end_time="00:00:01",
                    **segment_params
                )
            ],
            output_file=str(output_path),
            **params
        )
        
        # Should raise ValueError with specific message
        with self.assertRaises(ValueError) as context:
            stitch_ffmpeg_request(request)
        
        self.assertIn("Invalid file type", str(context.exception))
        self.assertIn("Must be 'audio' or 'video'", str(context.exception))
    
    def test_quality_settings(self):
        """Test different quality settings"""
        output_path = self.test_dir / "quality_test.mp4"
        
        # Start with default params
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        # Remove params that will be set directly
        params.pop('video_codec', None)
        params.pop('audio_codec', None)
        params.pop('crf', None)
        params.pop('preset', None)
        params.pop('video_bitrate', None)
        
        # Create segment params
        segment_params.update({
            'end_time': "00:00:01"
        })
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['video'],
                    file_type='video',
                    **segment_params
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            crf=23,  # Standard quality
            preset="ultrafast",  # Use fastest preset for testing
            video_bitrate="1M",  # 1 Mbps
            **params
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
            
            # Verify the file is a valid video
            probe = ffmpeg.probe(str(output_path))
            self.assertIn('streams', probe)
            self.assertTrue(any(s['codec_type'] == 'video' for s in probe['streams']))
            
            # Verify video settings
            video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            self.assertEqual(video_stream['codec_name'], 'h264')
        except Exception as e:
            self.fail(f"Quality settings test failed: {e}")
    
    def test_audio_settings(self):
        """Test audio-specific settings"""
        output_path = self.test_dir / "audio_settings.wav"
        
        # Start with default params
        segment_params = _get_default_segment_params()
        params = _get_default_request_params()
        
        # Remove params that will be set directly
        params.pop('audio_codec', None)
        params.pop('audio_bitrate', None)
        params.pop('audio_channels', None)
        params.pop('audio_sample_rate', None)
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=self.sample_files['audio'],
                    file_type='audio',
                    end_time="00:00:01",
                    **segment_params
                )
            ],
            output_file=str(output_path),
            audio_codec=AudioCodec.AAC,
            audio_bitrate="192k",
            audio_channels=2,
            audio_sample_rate=48000,
            **params
        )
        
        try:
            result = stitch_ffmpeg_request(request)
            self.assertEqual(result, str(output_path))
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 0)
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
            'ffmpeg',
            # Video input
            '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=30',
            # Audio input (silent)
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            # Duration
            '-t', '10',
            # Video codec settings
            '-c:v', 'libx264', '-preset', 'ultrafast',
            # Audio codec settings
            '-c:a', 'aac', '-b:a', '128k',
            # Output
            str(video_path), '-y'
        ]
        
        subprocess.run(cmd_audio, check=True, capture_output=True)
        subprocess.run(cmd_video, check=True, capture_output=True)
        
        # Test processing time
        import time
        
        output_path = test_dir / "perf_output.mp4"
        params = _get_default_request_params()
        segment_params = _get_default_segment_params()
        
        # Remove params that will be set directly
        params.pop('video_codec', None)
        params.pop('audio_codec', None)
        params.pop('crf', None)
        params.pop('preset', None)
        
        # Create segment params for video and audio
        video_segment_params = segment_params.copy()
        video_segment_params.update({
            'end_time': "00:00:10",
            'volume': 0.0  # Mute original audio
        })
        
        audio_segment_params = segment_params.copy()
        audio_segment_params.update({
            'end_time': "00:00:10",
            'volume': 1.0
        })
        
        request = FfmpegRequest(
            input_segments=[
                InputSegment(
                    file_path=str(video_path),
                    file_type='video',
                    **video_segment_params
                ),
                InputSegment(
                    file_path=str(audio_path),
                    file_type='audio',
                    **audio_segment_params
                )
            ],
            output_file=str(output_path),
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            crf=23,
            preset="medium",
            **params
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