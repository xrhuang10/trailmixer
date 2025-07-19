import os
import subprocess
import json
import logging
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MediaSegment:
    """Represents a segment of media with timing information"""
    file_path: str
    start_time: float  # Start time in seconds
    end_time: float    # End time in seconds
    media_type: str    # 'video', 'audio', or 'both'
    
    @property
    def duration(self) -> float:
        """Calculate duration of the segment"""
        return self.end_time - self.start_time

@dataclass
class StitchRequest:
    """Request for stitching multiple media segments"""
    segments: List[MediaSegment]
    output_path: str
    output_format: str = 'mp4'
    video_codec: str = 'libx264'
    audio_codec: str = 'aac'
    video_bitrate: str = '2M'
    audio_bitrate: str = '128k'
    resolution: Optional[Tuple[int, int]] = None
    fps: Optional[int] = None

class FFmpegProcessor:
    """Main class for handling FFmpeg operations"""
    
    def __init__(self, ffmpeg_path: Optional[str] = None):
        """
        Initialize FFmpeg processor
        
        Args:
            ffmpeg_path: Path to ffmpeg executable. If None, will try to find it in PATH
        """
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Please install FFmpeg and ensure it's in your PATH.")
        
        logger.info(f"FFmpeg found at: {self.ffmpeg_path}")
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find ffmpeg executable in system PATH"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, check=True)
            return 'ffmpeg'
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try common installation paths
            common_paths = [
                r'C:\ffmpeg\bin\ffmpeg.exe',  # Windows
                '/usr/bin/ffmpeg',            # Linux
                '/usr/local/bin/ffmpeg',      # macOS
                '/opt/homebrew/bin/ffmpeg'    # macOS Homebrew
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return path
            
            return None
    
    def get_media_info(self, file_path: str) -> Dict:
        """
        Get detailed information about a media file
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary containing media information
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        cmd = [
            self.ffmpeg_path,
            '-i', file_path,
            '-f', 'null',
            '-'
        ]
        
        try:
            # Get media info using ffprobe
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe') if self.ffmpeg_path else None
            if not ffprobe_path:
                raise RuntimeError("FFprobe not found")
                
            probe_cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting media info: {e}")
            raise RuntimeError(f"Failed to get media info for {file_path}: {e}")
    
    def extract_segment(self, input_path: str, output_path: str, 
                       start_time: float, duration: float,
                       video_codec: str = 'libx264', audio_codec: str = 'aac') -> bool:
        """
        Extract a segment from a media file
        
        Args:
            input_path: Input file path
            output_path: Output file path
            start_time: Start time in seconds
            duration: Duration in seconds
            video_codec: Video codec to use
            audio_codec: Audio codec to use
            
        Returns:
            True if successful, False otherwise
        """
        cmd = [
            self.ffmpeg_path,
            '-i', input_path,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c:v', video_codec,
            '-c:a', audio_codec,
            '-avoid_negative_ts', 'make_zero',
            '-y',  # Overwrite output file
            output_path
        ]
        
        try:
            logger.info(f"Extracting segment: {start_time}s to {start_time + duration}s")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Segment extracted successfully: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error extracting segment: {e}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            return False
    
    def create_concat_file(self, segments: List[MediaSegment], temp_dir: str) -> str:
        """
        Create a concat file for FFmpeg
        
        Args:
            segments: List of media segments
            temp_dir: Temporary directory for segment files
            
        Returns:
            Path to the concat file
        """
        concat_file = os.path.join(temp_dir, 'concat.txt')
        
        with open(concat_file, 'w') as f:
            for segment in segments:
                # Extract segment to temporary file
                temp_segment_path = os.path.join(temp_dir, f"segment_{segments.index(segment)}.mp4")
                
                if self.extract_segment(
                    segment.file_path, 
                    temp_segment_path, 
                    segment.start_time, 
                    segment.duration
                ):
                    f.write(f"file '{temp_segment_path}'\n")
                else:
                    raise RuntimeError(f"Failed to extract segment from {segment.file_path}")
        
        return concat_file
    
    def stitch_segments(self, request: StitchRequest) -> bool:
        """
        Stitch multiple media segments together based on timestamps
        
        Args:
            request: StitchRequest containing segments and output configuration
            
        Returns:
            True if successful, False otherwise
        """
        if not request.segments:
            raise ValueError("No segments provided for stitching")
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Create concat file
                concat_file = self.create_concat_file(request.segments, temp_dir)
                
                # Build FFmpeg command for concatenation
                cmd = [
                    self.ffmpeg_path,
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file,
                    '-c', 'copy',  # Copy streams without re-encoding for speed
                    '-y',
                    request.output_path
                ]
                
                # Add custom encoding options if specified
                if request.video_codec != 'copy' or request.audio_codec != 'copy':
                    cmd = [
                        self.ffmpeg_path,
                        '-f', 'concat',
                        '-safe', '0',
                        '-i', concat_file,
                        '-c:v', request.video_codec,
                        '-c:a', request.audio_codec,
                        '-b:v', request.video_bitrate,
                        '-b:a', request.audio_bitrate,
                        '-y',
                        request.output_path
                    ]
                
                # Add resolution and FPS if specified
                if request.resolution:
                    cmd.extend(['-vf', f'scale={request.resolution[0]}:{request.resolution[1]}'])
                
                if request.fps:
                    cmd.extend(['-r', str(request.fps)])
                
                logger.info(f"Stitching {len(request.segments)} segments to {request.output_path}")
                logger.info(f"FFmpeg command: {' '.join(cmd)}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                logger.info(f"Stitching completed successfully: {request.output_path}")
                return True
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Error during stitching: {e}")
                logger.error(f"FFmpeg stderr: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error during stitching: {e}")
                return False
    
    def add_audio_to_video(self, video_path: str, audio_path: str, 
                          output_path: str, audio_start_time: float = 0.0) -> bool:
        """
        Add audio to a video file with specified start time
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Output file path
            audio_start_time: When to start the audio (in seconds)
            
        Returns:
            True if successful, False otherwise
        """
        cmd = [
            self.ffmpeg_path,
            '-i', video_path,
            '-i', audio_path,
            '-filter_complex', f'[1:a]adelay={int(audio_start_time * 1000)}|{int(audio_start_time * 1000)}[delayed_audio];[0:a][delayed_audio]amix=inputs=2:duration=longest',
            '-c:v', 'copy',
            '-y',
            output_path
        ]
        
        try:
            logger.info(f"Adding audio to video: {audio_path} -> {video_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Audio added successfully: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error adding audio: {e}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            return False
    
    def create_silent_audio(self, duration: float, output_path: str, 
                           sample_rate: int = 44100) -> bool:
        """
        Create a silent audio file of specified duration
        
        Args:
            duration: Duration in seconds
            output_path: Output file path
            sample_rate: Audio sample rate
            
        Returns:
            True if successful, False otherwise
        """
        cmd = [
            self.ffmpeg_path,
            '-f', 'lavfi',
            '-i', f'anullsrc=channel_layout=stereo:sample_rate={sample_rate}',
            '-t', str(duration),
            '-c:a', 'aac',
            '-y',
            output_path
        ]
        
        try:
            logger.info(f"Creating silent audio: {duration}s")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"Silent audio created: {output_path}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error creating silent audio: {e}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            return False

# Utility functions for common operations
def create_stitch_request_from_timestamps(
    video_path: str,
    audio_segments: List[Dict[str, Union[str, float]]],
    output_path: str,
    **kwargs
) -> StitchRequest:
    """
    Create a StitchRequest from video and audio timestamps
    
    Args:
        video_path: Path to the main video file
        audio_segments: List of dicts with 'file_path', 'start_time', 'end_time'
        output_path: Output file path
        **kwargs: Additional arguments for StitchRequest
        
    Returns:
        StitchRequest object
    """
    segments = []
    
    # Add video segment (full duration)
    video_info = FFmpegProcessor().get_media_info(video_path)
    video_duration = float(video_info['format']['duration'])
    
    segments.append(MediaSegment(
        file_path=video_path,
        start_time=0.0,
        end_time=video_duration,
        media_type='video'
    ))
    
    # Add audio segments
    for audio_seg in audio_segments:
        segments.append(MediaSegment(
            file_path=audio_seg['file_path'],
            start_time=audio_seg['start_time'],
            end_time=audio_seg['end_time'],
            media_type='audio'
        ))
    
    return StitchRequest(segments=segments, output_path=output_path, **kwargs)

def validate_media_files(file_paths: List[str]) -> List[str]:
    """
    Validate that all media files exist and are readable
    
    Args:
        file_paths: List of file paths to validate
        
    Returns:
        List of valid file paths
    """
    valid_files = []
    processor = FFmpegProcessor()
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                # Try to get media info to validate it's a valid media file
                processor.get_media_info(file_path)
                valid_files.append(file_path)
            else:
                logger.warning(f"File not found: {file_path}")
        except Exception as e:
            logger.warning(f"Invalid media file {file_path}: {e}")
    
    return valid_files
