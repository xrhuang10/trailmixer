from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime
from fastapi import UploadFile

# === Twelve Labs Response Models ===
class TwelveLabsResponse(BaseModel):
    pass

# === Video Segment Models (matching new JSON schema) ===
class VideoSegment(BaseModel):
    """Represents a video segment with timing and mood information"""
    start_time: float = Field(..., description="Start time of the segment in seconds")
    end_time: float = Field(..., description="End time of the segment in seconds")
    sentiment: str = Field(..., description="The sentiment/mood of this segment")
    music_style: str = Field(..., description="Recommended music style/genre for this segment")
    intensity: str = Field(..., description="Intensity level of the segment (low, medium, high)")
    
    @validator('intensity')
    def validate_intensity(cls, v):
        allowed_values = ['low', 'medium', 'high']
        if v.lower() not in allowed_values:
            raise ValueError(f'Intensity must be one of: {allowed_values}')
        return v.lower()
    
    @validator('end_time')
    def validate_times(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v

class SentimentAnalysisData(BaseModel):
    """Complete sentiment analysis data structure"""
    video_id: str = Field(..., description="The ID of the video")
    video_title: str = Field(..., description="The title of the video")
    video_description: str = Field(..., description="The description of the video")
    video_length: float = Field(..., description="The length of the video in seconds")
    overall_mood: str = Field(..., description="The overall mood of the video")
    segments: List[VideoSegment] = Field(..., description="Array of video segments with mood and timing information")
    
    @validator('video_length')
    def validate_video_length(cls, v):
        if v <= 0:
            raise ValueError('video_length must be positive')
        return v

# === Sentiment Analysis Request/Response Models ===
class SentimentAnalysisRequest(BaseModel):
    """Request for sentiment analysis"""
    video_id: str = Field(..., description="Twelve Labs video ID")
    prompt: Optional[str] = Field(None, description="Custom prompt for analysis")

class SentimentAnalysisResponse(BaseModel):
    """Response from sentiment analysis"""
    sentiment_analysis: Union[str, SentimentAnalysisData] = Field(..., description="Analysis result or error message")
    file_path: Optional[str] = Field(None, description="Path to saved JSON file")
    success: bool = Field(True, description="Whether analysis was successful")
    error_message: Optional[str] = Field(None, description="Error message if analysis failed")

# === Job Status Models ===
class JobStatus(str, Enum):
    UPLOADING = "uploading"
    INDEXING = "indexing"
    ANALYZING = "analyzing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobInfo(BaseModel):
    """Job information and status tracking"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path to uploaded file")
    created_at: str = Field(..., description="Job creation timestamp")
    twelve_labs_video_id: Optional[str] = Field(None, description="Twelve Labs video ID")
    sentiment_analysis: Optional[SentimentAnalysisResponse] = Field(None, description="Sentiment analysis result")
    processed_video: Optional[Dict[str, Any]] = Field(None, description="Processed video information")

# === Video Processing Models ===
class VideoProcessingRequest(BaseModel):
    """Request for video processing with sentiment data"""
    file_path: str = Field(..., description="Path to input video file")
    sentiment_data: SentimentAnalysisData = Field(..., description="Sentiment analysis data")
    output_path: str = Field(..., description="Path for output video")
    job_id: str = Field(..., description="Job identifier")

class VideoProcessingResult(BaseModel):
    """Result of video processing"""
    output_path: str = Field(..., description="Path to processed video")
    segments: List[VideoSegment] = Field(..., description="Processed segments")
    duration: str = Field(..., description="Video duration")
    success: bool = Field(True, description="Whether processing was successful")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")

# === API Request/Response Models ===
class VideoUploadResponse(BaseModel):
    """Response from video upload endpoint"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Initial job status")
    message: str = Field(..., description="Status message")

class JobStatusResponse(BaseModel):
    """Response for job status queries"""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current status")
    message: str = Field(..., description="Status message")
    filename: str = Field(..., description="Original filename")
    created_at: str = Field(..., description="Creation timestamp")
    twelve_labs_video_id: Optional[str] = Field(None, description="Twelve Labs video ID")
    progress_percentage: Optional[float] = Field(None, description="Processing progress (0-100)")

class SentimentResultResponse(BaseModel):
    """Response for sentiment analysis results"""
    job_id: str = Field(..., description="Job identifier")
    sentiment_analysis: SentimentAnalysisData = Field(..., description="Sentiment analysis data")
    twelve_labs_video_id: str = Field(..., description="Twelve Labs video ID")
    status: JobStatus = Field(..., description="Job status")

class ProcessedVideoResponse(BaseModel):
    """Response for processed video information"""
    job_id: str = Field(..., description="Job identifier")
    original_filename: str = Field(..., description="Original filename")
    processed_video: Dict[str, Any] = Field(..., description="Processed video info")
    sentiment_analysis: SentimentAnalysisData = Field(..., description="Sentiment analysis data")
    twelve_labs_video_id: str = Field(..., description="Twelve Labs video ID")
    status: JobStatus = Field(..., description="Job status")

class JobListResponse(BaseModel):
    """Response for job listing"""
    jobs: List[Dict[str, Union[str, JobStatus]]] = Field(..., description="List of all jobs")

# === FFmpeg Models (existing, kept for compatibility) ===
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
    start_time: str = Field("00:00:00", description="Time in the output where this segment should start (format: HH:MM:SS or HH:MM:SS.mmm)")
    end_time: str = Field(..., description="Time in the output where this segment should end (format: HH:MM:SS or HH:MM:SS.mmm)")
    clip_start: Optional[str] = Field("00:00:00", description="Start time in the input file to use (format: HH:MM:SS or HH:MM:SS.mmm)")
    clip_end: Optional[str] = Field(None, description="End time in the input file to use (format: HH:MM:SS or HH:MM:SS.mmm)")
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

# === Audio Library and Selection Models ===
class AudioLibrary(BaseModel):
    """Audio library mapping for different music styles and moods"""
    happy_files: List[str] = Field(default=["music/happy.mp3"], description="Audio files for happy/positive moods")
    sad_files: List[str] = Field(default=["music/sad.mp3"], description="Audio files for sad/negative moods")
    neutral_files: List[str] = Field(default=["music/output_audio.mp3"], description="Audio files for neutral moods")
    energetic_files: List[str] = Field(default=["music/happy.mp3"], description="Audio files for energetic moods")
    calm_files: List[str] = Field(default=["music/sad.mp3"], description="Audio files for calm moods")

class AudioSelection(BaseModel):
    """Selected audio file for a video segment"""
    audio_file: str = Field(..., description="Path to selected audio file")
    volume: float = Field(1.0, description="Volume level (0.0-2.0)")
    fade_in: Optional[str] = Field(None, description="Fade in duration")
    fade_out: Optional[str] = Field(None, description="Fade out duration")

class VideoSegmentWithAudio(VideoSegment):
    """Extended video segment with audio selection"""
    audio_selection: Optional[AudioSelection] = Field(None, description="Selected audio for this segment")

class EnhancedSentimentAnalysisData(SentimentAnalysisData):
    """Enhanced sentiment analysis data with audio selections"""
    segments: List[VideoSegmentWithAudio] = Field(..., description="Video segments with audio selections")
    audio_library: AudioLibrary = Field(default_factory=AudioLibrary, description="Available audio library")

# === Audio Processing Request ===
class AudioPickingRequest(BaseModel):
    """Request for picking audio based on sentiment analysis"""
    sentiment_data: SentimentAnalysisData = Field(..., description="Original sentiment analysis data")
    original_video_path: str = Field(..., description="Path to original video file")
    output_video_path: str = Field(..., description="Path for output video file")
    audio_library: Optional[AudioLibrary] = Field(default_factory=AudioLibrary, description="Audio library to choose from")
    global_volume: float = Field(0.3, description="Global background music volume")
    crossfade_duration: str = Field("1.0", description="Crossfade duration between audio segments")

# === Multi-Video Processing Models ===
class MultiVideoUploadResponse(BaseModel):
    """Response from multi-video upload endpoint"""
    job_id: str = Field(..., description="Unique job identifier for multi-video processing")
    status: JobStatus = Field(..., description="Initial job status")
    message: str = Field(..., description="Status message")
    video_count: int = Field(..., description="Number of videos uploaded")
    video_files: List[str] = Field(..., description="List of uploaded video filenames")

class VideoAnalysisResult(BaseModel):
    """Result of analysis for a single video"""
    video_index: int = Field(..., description="Index of video in the batch")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path to video file")
    twelve_labs_video_id: Optional[str] = Field(None, description="Twelve Labs video ID")
    sentiment_analysis: Optional[SentimentAnalysisResponse] = Field(None, description="Sentiment analysis result")
    segments_with_audio: Optional[List[VideoSegmentWithAudio]] = Field(None, description="Video segments with audio selections")
    video_length: Optional[float] = Field(None, description="Video length in seconds")
    success: bool = Field(True, description="Whether analysis was successful")
    error_message: Optional[str] = Field(None, description="Error message if analysis failed")

class MultiVideoJobInfo(JobInfo):
    """Extended job info for multi-video processing"""
    video_count: int = Field(..., description="Number of videos being processed")
    video_files: List[str] = Field(..., description="List of video filenames")
    video_results: List[VideoAnalysisResult] = Field(default_factory=list, description="Results for each video")
    aggregated_ffmpeg_request: Optional[Dict[str, Any]] = Field(None, description="Final aggregated FFmpeg request")

class MultiVideoFFmpegRequest(BaseModel):
    """Request for creating FFmpeg configuration from multiple videos"""
    video_results: List[VideoAnalysisResult] = Field(..., description="Analysis results for all videos")
    output_video_path: str = Field(..., description="Path for final output video")
    global_volume: float = Field(0.3, description="Global background music volume")
    crossfade_duration: str = Field("1.0", description="Crossfade duration between segments")
    video_transition_duration: str = Field("0.5", description="Transition duration between videos")