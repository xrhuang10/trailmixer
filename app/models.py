from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class TwelveLabsResponse(BaseModel):
    pass

class AudioCodec(str, Enum):
    AAC = "aac"
    MP3 = "mp3"
    WAV = "pcm_s16le"  # Changed from "wav" to "pcm_s16le"
    FLAC = "flac"

class VideoCodec(str, Enum):
    H264 = "libx264"
    H265 = "libx265"
    VP9 = "libvpx-vp9"
    AV1 = "libaom-av1"

class InputSegment(BaseModel):
    """Represents a single input segment with timing information"""
    file_path: str = Field(..., description="Path to the input file (video or audio)")
    file_type: str = Field(..., description="Type of file: 'video' or 'audio'")
    start_time: str = Field("00:00:00", description="Start time in the input file (format: HH:MM:SS or HH:MM:SS.mmm)")
    end_time: str = Field(..., description="End time in the input file (format: HH:MM:SS or HH:MM:SS.mmm)")
    volume: Optional[float] = Field(1.0, description="Volume multiplier for this segment")
    fade_in: Optional[str] = Field(None, description="Fade in duration for this segment")
    fade_out: Optional[str] = Field(None, description="Fade out duration for this segment")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for this segment")

class FfmpegRequest(BaseModel):
    """Request model for FFmpeg video/audio stitching with multiple input files"""
    
    # Input segments
    input_segments: List[InputSegment] = Field(..., description="List of input video and audio segments to stitch together")
    output_file: str = Field(..., description="Path for the output stitched file")
    
    # Output configuration
    video_codec: VideoCodec = Field(VideoCodec.H264, description="Video codec for output")
    audio_codec: AudioCodec = Field(AudioCodec.AAC, description="Audio codec for output")
    video_bitrate: Optional[str] = Field(None, description="Video bitrate (e.g., '2M', '5000k')")
    audio_bitrate: Optional[str] = Field(None, description="Audio bitrate (e.g., '128k', '256k')")
    
    # Quality and performance settings
    crf: Optional[int] = Field(None, ge=0, le=51, description="Constant Rate Factor for quality (0-51, lower is better)")
    preset: Optional[str] = Field("medium", description="Encoding preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)")
    
    # Advanced options
    scale: Optional[str] = Field(None, description="Video scale (e.g., '1920:1080', '1280:720')")
    fps: Optional[float] = Field(None, description="Output frame rate")
    audio_channels: Optional[int] = Field(2, description="Number of audio channels")
    audio_sample_rate: Optional[int] = Field(44100, description="Audio sample rate in Hz")
    
    # Global audio settings
    global_volume: Optional[float] = Field(1.0, description="Global audio volume multiplier")
    normalize_audio: bool = Field(False, description="Normalize audio levels across all segments")
    
    # Stitching options
    crossfade_duration: Optional[str] = Field(None, description="Crossfade duration between segments (e.g., '0.5')")
    gap_duration: Optional[str] = Field("00:00:00", description="Gap duration between segments")
    
    # Additional parameters
    overwrite: bool = Field(True, description="Overwrite output file if it exists")
    quiet: bool = Field(False, description="Suppress FFmpeg output")
    progress: bool = Field(True, description="Show progress during encoding")
    
    # FastAPI specific
    request_id: Optional[str] = Field(None, description="Unique request ID for tracking")
    priority: Optional[int] = Field(1, ge=1, le=10, description="Processing priority (1-10, higher is more urgent)")
    
    class Config:
        use_enum_values = True
        schema_extra = {
            "example": {
                "input_segments": [
                    {
                        "file_path": "video1.mp4",
                        "file_type": "video",
                        "start_time": "00:00:10",
                        "end_time": "00:01:40",
                        "volume": 1.0,
                        "fade_in": "0.5"
                    },
                    {
                        "file_path": "audio1.wav",
                        "file_type": "audio",
                        "start_time": "00:00:00",
                        "end_time": "00:01:30",
                        "volume": 0.8
                    },
                    {
                        "file_path": "video2.mp4",
                        "file_type": "video",
                        "start_time": "00:02:00",
                        "end_time": "00:04:15",
                        "fade_out": "1.0"
                    }
                ],
                "output_file": "stitched_output.mp4",
                "video_codec": "libx264",
                "audio_codec": "aac",
                "crf": 23,
                "preset": "medium",
                "scale": "1920:1080",
                "fps": 30.0,
                "global_volume": 1.1,
                "normalize_audio": True,
                "crossfade_duration": "0.5",
                "request_id": "req_12345",
                "priority": 5
            }
        }