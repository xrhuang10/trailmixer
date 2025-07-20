import os
import uuid
import datetime
import tempfile
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from video_processor import convert_mov_to_mp4
# Import models
from models import (
    VideoSegment, SentimentAnalysisData, SentimentAnalysisRequest, SentimentAnalysisResponse,
    JobStatus, JobInfo, VideoProcessingRequest, VideoProcessingResult,
    VideoUploadResponse, JobStatusResponse, SentimentResultResponse, ProcessedVideoResponse, JobListResponse,
    AudioLibrary, AudioSelection, VideoSegmentWithAudio, EnhancedSentimentAnalysisData, AudioPickingRequest,
    FfmpegRequest, InputSegment, VideoCodec, AudioCodec,
    MultiVideoUploadResponse, VideoAnalysisResult, MultiVideoJobInfo, MultiVideoFFmpegRequest
)

# Import processing modules
from pipeline import stitch_videos_together, crop_and_stitch_video_segments, add_music_to_video, upload_video_pipeline
from video_processor import extract_segments
from prompts.extract_info import extract_info_prompt
from twelvelabs_client import prompt_twelvelabs

app = FastAPI(title="TrailMixer Video Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],                      # Allow all HTTP methods
    allow_headers=["*"],                      # Allow all headers
)


# Serve static files for processed videos
app.mount("/static", StaticFiles(directory="../processed_videos"), name="static")

# In-memory storage for job status (in production, use Redis or database)
job_status: Dict[str, JobInfo] = {}
multi_video_job_status: Dict[str, MultiVideoJobInfo] = {}
# Storage for upload results (music timestamps, etc.)
upload_results: Dict[str, Dict[str, Any]] = {}

# Response model for music timestamps
class MusicTimestampsResponse(BaseModel):
    """Response containing music timestamps for uploaded video(s)"""
    job_id: str = Field(..., description="Unique job identifier")
    video_count: int = Field(..., description="Number of videos processed")
    videos: List[Dict[str, Any]] = Field(..., description="List of video analysis results")
    success: bool = Field(..., description="Whether processing was successful")
    message: str = Field(..., description="Status message")
    filepath: Optional[str] = Field(None, description="Path to the main processed video file")

# Simplified response model for upload endpoint
class VideoUploadSimpleResponse(BaseModel):
    """Simplified response for video upload with just job_id and music file paths"""
    job_id: str = Field(..., description="Unique job identifier")
    music_file_paths: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Music file paths with timing information")
    audio_timestamps: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Audio timestamps ready for download endpoint")
    debug_info: Dict[str, Any] = Field(default_factory=dict, description="Miscellaneous debugging information")

# ==================== API ENDPOINTS ====================

@app.post('/api/video/upload', response_model=VideoUploadSimpleResponse)
def upload_video(video_files: List[UploadFile] = File(...)):
    """
    Upload videos, stitch them together, process with TwelveLabs, and return music timestamps
    Use /api/video/download-result/{job_id} to get the actual stitched video file
    """
    if not video_files:
        raise HTTPException(status_code=400, detail="No video files provided")
    
    print(f"🚀 Processing {len(video_files)} video(s) for stitching")
    
    # Create upload directory
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded files to upload directory with MOV conversion support
    temp_files = []
    uploaded_filenames = []
    
    try:
        for i, video_file in enumerate(video_files):
            if not video_file.content_type or not video_file.content_type.startswith('video/'):
                raise HTTPException(status_code=400, detail=f"File {i+1} must be a video")
            if not video_file.filename:
                raise HTTPException(status_code=400, detail=f"Filename for file {i+1} is required")
            
            orig_filename = video_file.filename
            file_path = os.path.join(upload_dir, f"{job_id}_{i+1}_{orig_filename}")
            
            try:
                # Save uploaded content to file
                with open(file_path, "wb") as buffer:
                    content = video_file.file.read()
                    buffer.write(content)
                
                # If it's a .mov, convert to .mp4 and use the new path
                if orig_filename.lower().endswith('.mov'):
                    try:
                        converted_path = convert_mov_to_mp4(file_path)
                        os.remove(file_path)  # Remove original .mov
                        file_path = converted_path
                        # Update filename for the rest of the pipeline
                        orig_filename = os.path.basename(converted_path)
                        print(f"🔄 Converted MOV to MP4: {orig_filename}")
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"FFmpeg conversion failed: {str(e)}")
                
                temp_files.append(file_path)
                uploaded_filenames.append(orig_filename)
                print(f"📁 Saved video {i+1}/{len(video_files)}: {orig_filename}")
                print(f"   Path: {file_path}")
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to save file {i+1}: {str(e)}")
            finally:
                video_file.file.close()
        
        # Stitch videos together if multiple videos uploaded
        if len(temp_files) > 1:
            print(f"🔗 Stitching {len(temp_files)} videos together...")
            
            # Create permanent output file for stitched result in uploads directory
            final_filename = f"stitched_{job_id}_{len(temp_files)}_videos.mp4"
            stitched_output_path = os.path.join(upload_dir, final_filename)
            
            try:
                final_video_path = stitch_videos_together(temp_files, stitched_output_path)
                print(f"✅ Videos stitched successfully: {final_filename}")
                print(f"   📁 Permanent path: {final_video_path}")
                
            except Exception as e:
                print(f"❌ Video stitching failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to stitch videos: {str(e)}")
        else:
            # Single video - copy to permanent location in uploads directory
            original_temp_path = temp_files[0] 
            final_filename = f"{job_id}_{uploaded_filenames[0]}"
            final_video_path = os.path.join(upload_dir, final_filename)
            
            # Copy single video to permanent location
            import shutil
            shutil.copy2(original_temp_path, final_video_path)
            print(f"📹 Single video copied to permanent location: {final_filename}")
            print(f"   📁 Permanent path: {final_video_path}")
        
        # Verify final video exists
        if not os.path.exists(final_video_path):
            raise HTTPException(status_code=500, detail="Final video file not found after processing")
        
        # Get file size for logging
        file_size = os.path.getsize(final_video_path)
        print(f"🎬 Final stitched video ready: {final_filename}")
        print(f"   Size: {file_size / (1024*1024):.1f} MB")
        print(f"   Path: {final_video_path}")
        
        # Process the final video through TwelveLabs pipeline for music timestamps
        print(f"🚀 Processing stitched video through TwelveLabs pipeline: {final_filename}")
        
        try:
            # Create a temporary job for the upload pipeline
            temp_job_id = job_id
            temp_job_status = {}
            
            temp_job_status[temp_job_id] = JobInfo(
                job_id=temp_job_id,
                status=JobStatus.UPLOADING,
                message="Processing stitched video...",
                filename=final_filename,
                file_path=final_video_path,
                created_at=datetime.datetime.now().isoformat(),
                twelve_labs_video_id=None,
                sentiment_analysis=None,
                processed_video=None,
                segment_timestamps=None
            )
            
            # Use upload pipeline as helper function (runs steps 1-3)
            upload_video_pipeline(temp_job_id, temp_job_status)
            
            # Get results from the pipeline
            temp_job = temp_job_status[temp_job_id]
            
            # IMPORTANT: Store the job in global job_status so crop_video can find it
            job_status[temp_job_id] = temp_job
            
            # Debug: Check what sentiment analysis data was stored
            print(f"🔍 DEBUG: Job stored in global job_status")
            print(f"   Job ID: {temp_job_id}")
            print(f"   Status: {temp_job.status}")
            print(f"   Has sentiment_analysis: {temp_job.sentiment_analysis is not None}")
            if temp_job.sentiment_analysis:
                print(f"   Sentiment analysis file_path: {temp_job.sentiment_analysis.file_path}")
                print(f"   Has segment_timestamps: {hasattr(temp_job, 'segment_timestamps')}")
                if hasattr(temp_job, 'segment_timestamps'):
                    print(f"   Segment timestamps count: {len(temp_job.segment_timestamps) if temp_job.segment_timestamps else 0}")
            
            if temp_job.status == JobStatus.FAILED:
                raise RuntimeError(temp_job.message)
            
            # Extract music timestamps from pipeline results
            music_file_paths = {}
            audio_selection_complete = False
            audio_error = None
            
            if temp_job.sentiment_analysis and temp_job.sentiment_analysis.file_path:
                try:
                    from audio_picker import get_music_file_paths
                    music_file_paths = get_music_file_paths(temp_job.sentiment_analysis.file_path)
                    audio_selection_complete = True
                    print(f"🎵 Music timestamps extracted: {len(music_file_paths)} tracks")
                except Exception as e:
                    audio_error = str(e)
                    print(f"❌ Audio selection failed: {audio_error}")
            else:
                audio_error = "No sentiment analysis file path available"
                print(f"❌ {audio_error}")
                raise HTTPException(status_code=500, detail=audio_error)
            
            # Get basic video info if available
            video_title = ""
            video_length = 0
            overall_mood = ""
            
            if temp_job.sentiment_analysis and isinstance(temp_job.sentiment_analysis.sentiment_analysis, SentimentAnalysisData):
                sentiment_data = temp_job.sentiment_analysis.sentiment_analysis
                video_title = sentiment_data.video_title
                video_length = sentiment_data.video_length
                overall_mood = sentiment_data.overall_mood
            
            # Create video result for the final processed video
            video_result = {
                "video_index": 0,
                "filename": final_filename,
                "file_path": final_video_path,
                "original_files": uploaded_filenames,
                "stitched": len(temp_files) > 1,
                "twelve_labs_video_id": temp_job.twelve_labs_video_id,
                "video_title": video_title,
                "video_length": video_length,
                "overall_mood": overall_mood,
                "music_file_paths": music_file_paths,
                "audio_selection_complete": audio_selection_complete,
                "audio_error": audio_error,
                "success": True,
                "error_message": None
            }
            
            video_results = [video_result]
            print(f"✅ Successfully processed stitched video - music selection: {'✓' if audio_selection_complete else '✗'}")

        except Exception as processing_error:
            print(f"❌ Error processing stitched video with TwelveLabs: {str(processing_error)}")
            
            # Create failed video result but still return the stitched file info
            video_result = {
                "video_index": 0,
                "filename": final_filename,
                "file_path": final_video_path,
                "original_files": uploaded_filenames,
                "stitched": len(temp_files) > 1,
                "twelve_labs_video_id": None,
                "video_title": "",
                "video_length": 0,
                "overall_mood": "",
                "music_file_paths": {},
                "audio_selection_complete": False,
                "audio_error": str(processing_error),
                "success": False,
                "error_message": str(processing_error)
            }
            video_results = [video_result]
        
        # Count successful videos
        successful_videos = [v for v in video_results if v["success"]]
        failed_videos = [v for v in video_results if not v["success"]]
        
        print(f"\n📊 PROCESSING COMPLETE:")
        if len(temp_files) > 1:
            print(f"   🔗 Stitched {len(temp_files)} videos into 1")
            print(f"   ✅ TwelveLabs processing: {'Success' if successful_videos else 'Failed'}")
        else:
            print(f"   ✅ Single video TwelveLabs processing: {'Success' if successful_videos else 'Failed'}")
        
        # Store upload results for timestamps endpoint and video download
        success = len(failed_videos) == 0
        if len(temp_files) > 1:
            message = f"Successfully stitched {len(temp_files)} videos and processed through TwelveLabs"
        else:
            message = f"Successfully processed 1 video through TwelveLabs"
        
        if failed_videos:
            message += " (with processing errors)"
        
        upload_results[job_id] = {
            "job_id": job_id,
            "video_count": len(video_files),
            "original_file_count": len(temp_files),
            "final_video_count": 1,
            "videos": video_results,
            "success": success,
            "message": message
        }
        
        # Extract music file paths from the first video result
        music_file_paths = {}
        audio_timestamps = {}
        if video_results and len(video_results) > 0:
            video_result = video_results[0]
            music_file_paths = video_result.get("music_file_paths", {})
            
            # Convert music_file_paths to audio_timestamps format for download endpoint
            for audio_file, timing_info in music_file_paths.items():
                # Extract only start and end times for the download endpoint format
                audio_timestamps[audio_file] = {
                    "start": timing_info.get("start", 0),
                    "end": timing_info.get("end", 10)
                }
            
            print(f"🎵 Generated audio_timestamps for download: {len(audio_timestamps)} tracks")
            for i, (audio_file, timing) in enumerate(audio_timestamps.items()):
                print(f"   Track {i+1}: {os.path.basename(audio_file)} ({timing['start']}s - {timing['end']}s)")
        
        # Create debug info with miscellaneous details
        debug_info = {
            "video_count": len(video_files),
            "original_file_count": len(temp_files),
            "stitched": len(temp_files) > 1,
            "success": success,
            "message": message,
            "filepath": final_video_path,
            "audio_selection_complete": video_results[0].get("audio_selection_complete", False) if video_results else False,
            "twelve_labs_video_id": video_results[0].get("twelve_labs_video_id") if video_results else None,
            "video_title": video_results[0].get("video_title", "") if video_results else "",
            "video_length": video_results[0].get("video_length", 0) if video_results else 0,
            "overall_mood": video_results[0].get("overall_mood", "") if video_results else "",
            "original_filenames": uploaded_filenames,
            "audio_timestamps_count": len(audio_timestamps),
            "processing_errors": video_results[0].get("audio_error") if video_results and not video_results[0].get("success", True) else None
        }
        
        print(f"🎵 Returning simplified upload response")
        print(f"   📋 Job ID: {job_id}")
        print(f"   🎼 Music file paths: {len(music_file_paths)}")
        print(f"   🎯 Audio timestamps (ready for download): {len(audio_timestamps)}")
        print(f"   💾 Debug info fields: {len(debug_info)}")
        
        # Return simplified response
        return VideoUploadSimpleResponse(
            job_id=job_id,
            music_file_paths=music_file_paths,
            audio_timestamps=audio_timestamps,
            debug_info=debug_info
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Unexpected error during upload processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")
    
    finally:
        # Clean up only the original temporary input files (NOT the final video)
        # The final video is now stored permanently in uploads directory
        cleanup_count = 0
        for temp_file_path in temp_files:
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    cleanup_count += 1
                    print(f"🧹 Cleaned up temp input file: {os.path.basename(temp_file_path)}")
            except Exception as cleanup_error:
                print(f"⚠️ Failed to clean up temp file {temp_file_path}: {cleanup_error}")
        
        if cleanup_count > 0:
            print(f"🧹 Cleaned up {cleanup_count} temporary input files")
            if 'final_video_path' in locals():
                print(f"✅ Final video preserved at: {final_video_path}")
        else:
            print(f"🧹 No temporary files to clean up")

# Request model for video processing with timestamps
class VideoProcessingTimestampsRequest(BaseModel):
    """Request for processing video with specific timestamps and clips"""
    timestamps: List[Dict[str, Any]] = Field(..., description="List of timestamp segments to process")
    music_file_paths: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Music file paths with timing info")
    output_filename: Optional[str] = Field(None, description="Custom output filename")
    crop_settings: Optional[Dict[str, Any]] = Field(None, description="Video cropping settings")
    audio_settings: Optional[Dict[str, Any]] = Field(None, description="Audio processing settings")

# Request model for download processed video
class DownloadProcessedVideoRequest(BaseModel):
    """Request for downloading processed video with audio timestamps"""
    job_id: str = Field(..., description="Unique job identifier for the video to download")
    audio_timestamps: Dict[str, Dict[str, Any]] = Field(
        ..., 
        description="Dictionary where keys are audio file paths and values contain timing info",
        example={
            "../music/pop/exciting.mp3": {"start": 0, "end": 10},
            "../music/classical/dramatic.mp3": {"start": 10, "end": 20},
            "../music/pop/calm.mp3": {"start": 20, "end": 30}
        }
    )
    video_volume: Optional[float] = Field(0.8, ge=0.0, le=2.0, description="Volume level for original video audio (0.0 to 2.0)")
    music_volume: Optional[float] = Field(0.3, ge=0.0, le=2.0, description="Volume level for background music (0.0 to 2.0)")
    output_filename: Optional[str] = Field(None, description="Custom output filename (without extension)")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "abc123-def456-ghi789",
                "audio_timestamps": {
                    "../music/pop/exciting.mp3": {
                        "start": 0,
                        "end": 10
                    },
                    "../music/classical/dramatic.mp3": {
                        "start": 10,
                        "end": 20
                    },
                    "../music/pop/calm.mp3": {
                        "start": 20,
                        "end": 30
                    }
                },
                "video_volume": 0.8,
                "music_volume": 0.3,
                "output_filename": "my_processed_trailer"
            }
        }

# Request model for custom video analysis with prompt parameters
class CustomAnalysisRequest(BaseModel):
    """Request for analyzing a video with custom prompt parameters"""
    job_id: str = Field(..., description="Job ID of the uploaded video to analyze")
    desired_length: int = Field(..., ge=10, le=300, description="Target trailer length in seconds (10-300)")
    num_tracks: int = Field(..., ge=1, le=10, description="Number of music tracks to generate (1-10)")
    music_style: List[str] = Field(
        ..., 
        description="List of allowed music styles (subset of allowed styles)",
        example=["pop", "electronic", "classical"]
    )
    sentiment_list: Optional[List[str]] = Field(
        None,
        description="List of allowed sentiments (optional, uses defaults if not provided)",
        example=["happy", "energetic", "dramatic"]
    )
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "abc123-def456-ghi789",
                "desired_length": 60,
                "num_tracks": 3,
                "music_style": ["pop", "electronic", "classical"],
                "sentiment_list": ["happy", "energetic", "dramatic", "calm"]
            }
        }

# Response model for custom analysis
class CustomAnalysisResponse(BaseModel):
    """Response from custom video analysis"""
    job_id: str = Field(..., description="Job ID of the analyzed video")
    analysis_complete: bool = Field(..., description="Whether analysis completed successfully")
    message: str = Field(..., description="Status message")
    prompt_parameters: Dict[str, Any] = Field(..., description="Parameters used for the analysis prompt")
    analysis_data: Optional[Dict[str, Any]] = Field(None, description="Raw analysis data from TwelveLabs")
    segment_timestamps: Optional[List[Dict[str, Any]]] = Field(None, description="Extracted segment timestamps")
    music_file_paths: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Generated music file paths")
    error_message: Optional[str] = Field(None, description="Error message if analysis failed")

@app.post('/api/video/analyze-custom', response_model=CustomAnalysisResponse)
def analyze_video_custom(request: CustomAnalysisRequest):
    """
    Analyze an uploaded video with custom prompt parameters.
    This allows customization of trailer length, number of tracks, and music styles.
    """
    job_id = request.job_id
    
    # Check if job exists
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found. Must upload video first.")
    
    job = job_status[job_id]
    
    # Check if video has been uploaded to TwelveLabs
    if not job.twelve_labs_video_id:
        raise HTTPException(status_code=400, detail="Video not yet uploaded to TwelveLabs. Wait for upload to complete.")
    
    try:
        print(f"🔍 Starting custom analysis for job: {job_id}")
        print(f"   🎯 Desired length: {request.desired_length}s")
        print(f"   🎵 Music tracks: {request.num_tracks}")
        print(f"   🎼 Music styles: {request.music_style}")
        print(f"   💭 Sentiments: {request.sentiment_list}")
        
        # Validate music styles
        allowed_styles = ["pop", "hiphop", "electronic", "classical", "meme"]
        for style in request.music_style:
            if style.lower() not in allowed_styles:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid music style '{style}'. Must be one of: {allowed_styles}"
                )
        
        # Generate custom prompt with provided parameters
        custom_prompt = extract_info_prompt
        
        print(f"✨ Generated custom prompt with {len(custom_prompt)} characters")
        
        # Analyze video with custom prompt
        print(f"🤖 Sending custom analysis request to TwelveLabs...")
        response = prompt_twelvelabs(job.twelve_labs_video_id, custom_prompt)
        
        if not response:
            raise RuntimeError("No response from TwelveLabs analysis")
        
        print(f"✅ TwelveLabs analysis completed")
        
        # Parse and clean the response
        from twelvelabs_client import clean_llm_string_output_to_json
        analysis_data = clean_llm_string_output_to_json(response.data)
        
        print(f"📊 Parsed analysis data with {len(analysis_data.get('segments', []))} segments")
        
        # Extract segment timestamps from analysis
        segments = analysis_data.get('segments', [])
        segment_timestamps = []
        for seg in segments:
            if seg.get('include', False):  # Only include segments marked as True
                segment_timestamps.append({
                    'start_time': seg.get('start_time', 0),
                    'end_time': seg.get('end_time', 10),
                    'sentiment': seg.get('sentiment', 'happy'),
                    'intensity': seg.get('intensity', 'medium')
                })
        
        print(f"🎬 Extracted {len(segment_timestamps)} included segments")
        
        # Calculate total duration
        total_duration = sum(seg['end_time'] - seg['start_time'] for seg in segment_timestamps)
        print(f"⏱️ Total segment duration: {total_duration}s (target: {request.desired_length}s)")
        
        # Generate music file paths from analysis
        music_file_paths = {}
        try:
            # Save analysis to temporary file for audio picker
            import tempfile
            import json
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                json.dump(analysis_data, temp_file, indent=2)
                temp_analysis_path = temp_file.name
            
            # Get music file paths
            from audio_picker import get_music_file_paths
            music_file_paths = get_music_file_paths(temp_analysis_path)
            
            # Clean up temp file
            os.unlink(temp_analysis_path)
            
            print(f"🎵 Generated {len(music_file_paths)} music track assignments")
            
        except Exception as audio_error:
            print(f"⚠️ Audio selection failed: {audio_error}")
            music_file_paths = {}
        
        # Update job with custom analysis results
        job.sentiment_analysis = SentimentAnalysisResponse(
            file_path=f"custom_analysis_{job_id}.json",
            sentiment_analysis=analysis_data  # Store raw analysis data
        )
        job.segment_timestamps = segment_timestamps
        job.status = JobStatus.PROCESSING
        job.message = f"Custom analysis completed with {len(segment_timestamps)} segments"
        
        # Store analysis parameters for reference
        prompt_parameters = {
            "desired_length": request.desired_length,
            "num_tracks": request.num_tracks,
            "music_style": request.music_style,
            "sentiment_list": request.sentiment_list,
            "total_segment_duration": total_duration,
            "segments_included": len(segment_timestamps)
        }
        
        print(f"✅ Custom analysis completed successfully")
        print(f"   📊 Segments: {len(segment_timestamps)}")
        print(f"   🎵 Music tracks: {len(music_file_paths)}")
        print(f"   ⏱️ Duration: {total_duration}s / {request.desired_length}s")
        
        return CustomAnalysisResponse(
            job_id=job_id,
            analysis_complete=True,
            message=f"Custom analysis completed with {len(segment_timestamps)} segments totaling {total_duration}s",
            prompt_parameters=prompt_parameters,
            analysis_data=analysis_data,
            segment_timestamps=segment_timestamps,
            music_file_paths=music_file_paths,
            error_message=None
        )
        
    except ValueError as ve:
        # Validation errors
        error_msg = f"Invalid parameters: {str(ve)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
        
    except Exception as e:
        # General processing errors
        error_msg = f"Custom analysis failed: {str(e)}"
        print(f"❌ {error_msg}")
        
        return CustomAnalysisResponse(
            job_id=job_id,
            analysis_complete=False,
            message="Custom analysis failed",
            prompt_parameters={
                "desired_length": request.desired_length,
                "num_tracks": request.num_tracks,
                "music_style": request.music_style,
                "sentiment_list": request.sentiment_list
            },
            analysis_data=None,
            segment_timestamps=None,
            music_file_paths=None,
            error_message=error_msg
        )

@app.post('/api/video/crop')
def crop_video(job_id: str):
    """
    Crop the video based on segment timestamps from sentiment analysis stored in job
    """
    # Check if job exists and has sentiment analysis
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found. Must upload and analyze video first.")
    
    job = job_status[job_id]
    
    # Debug: Check what's actually in the job
    print(f"🔍 DEBUG: Retrieved job from job_status")
    print(f"   Job ID: {job_id}")
    print(f"   Status: {job.status}")
    print(f"   Has sentiment_analysis: {job.sentiment_analysis is not None}")
    if job.sentiment_analysis:
        print(f"   Sentiment analysis file_path: {getattr(job.sentiment_analysis, 'file_path', 'NO FILE_PATH ATTR')}")
        print(f"   Sentiment analysis type: {type(job.sentiment_analysis)}")
    print(f"   Has segment_timestamps attr: {hasattr(job, 'segment_timestamps')}")
    if hasattr(job, 'segment_timestamps'):
        print(f"   Segment timestamps: {job.segment_timestamps}")
        print(f"   Segment timestamps type: {type(job.segment_timestamps)}")
    
    if not job.sentiment_analysis:
        raise HTTPException(status_code=400, detail="No sentiment analysis found. Must complete video analysis first.")
    
    # Get upload results to find the stitched video
    if job_id not in upload_results:
        raise HTTPException(status_code=404, detail="Upload results not found.")
    
    upload_result = upload_results[job_id]
    video_info = upload_result["videos"][0] if upload_result["videos"] else {}
    stitched_video_path = video_info.get("file_path")
    source_filename = video_info.get("filename", f"video_{job_id}.mp4")
    
    # Debug: Show what paths we're working with
    print(f"🔍 DEBUG: Video path resolution")
    print(f"   Expected path from upload_results: {stitched_video_path}")
    print(f"   Path exists: {os.path.exists(stitched_video_path) if stitched_video_path else 'PATH IS NONE'}")
    print(f"   Source filename: {source_filename}")
    
    # Also check if the job has the file_path stored
    if hasattr(job, 'file_path') and job.file_path:
        print(f"   Job file_path: {job.file_path}")
        print(f"   Job path exists: {os.path.exists(job.file_path)}")
        
        # Use job file_path if upload_results path is missing or doesn't exist
        if not stitched_video_path or not os.path.exists(stitched_video_path):
            if os.path.exists(job.file_path):
                print(f"   🔄 Using job.file_path instead of upload_results path")
                stitched_video_path = job.file_path
    
    if not stitched_video_path:
        raise HTTPException(status_code=404, detail="Stitched video file not found - no path available")
    
    if not os.path.exists(stitched_video_path):
        raise HTTPException(status_code=404, detail=f"Stitched video file not found at path: {stitched_video_path}")
    
    try:
        print(f"✂️ Cropping video for job: {job_id}")
        print(f"   📁 Stitched video: {source_filename}")
        
        # Extract segment timestamps from sentiment analysis
        segment_timestamps = job.segment_timestamps
        
        if not segment_timestamps:
            raise HTTPException(status_code=400, detail="No segment timestamps found in sentiment analysis")
        
        print(f"   📊 Using segments from analysis: {len(segment_timestamps)}")
        for i, seg in enumerate(segment_timestamps):
            start_time = seg.get('start_time', seg.get('start', 0))
            end_time = seg.get('end_time', seg.get('end', 10))
            print(f"       Segment {i+1}: {start_time}s - {end_time}s (duration: {end_time-start_time}s)")
        
        # Convert segment format if needed (ensure start/end keys)
        normalized_segments = []
        for seg in segment_timestamps:
            normalized_seg = {
                "start": seg.get('start_time', seg.get('start', 0)),
                "end": seg.get('end_time', seg.get('end', 10))
            }
            normalized_segments.append(normalized_seg)
        
        # Create output path for cropped video
        os.makedirs("../processed_videos", exist_ok=True)
        cropped_video_path = f"../processed_videos/{job_id}_cropped.mp4"
        
        # Crop and stitch video segments using extracted timestamps
        cropped_path = crop_and_stitch_video_segments(
            video_filepath=stitched_video_path,
            segments=normalized_segments,
            output_path=cropped_video_path
        )
        
        # Verify cropped output exists
        if not os.path.exists(cropped_path):
            raise RuntimeError("Cropped video was not created")
        
        file_size = os.path.getsize(cropped_path)
        print(f"✅ Video cropping completed successfully!")
        print(f"   📁 Cropped video: {os.path.basename(cropped_path)}")
        print(f"   📊 Size: {file_size / (1024*1024):.1f} MB")
        
        # Update job status with cropped video info
        job.status = JobStatus.PROCESSING
        job.message = "Video cropping completed"
        if not job.processed_video:
            job.processed_video = {}
        job.processed_video.update({
            "cropped_video_path": cropped_path,
            "cropped_filename": os.path.basename(cropped_path),
            "segments_count": len(normalized_segments),
            "total_duration": sum(seg["end"] - seg["start"] for seg in normalized_segments),
            "segments_used": normalized_segments,
            "cropping_complete": True
        })
        
        return {
            "job_id": job_id,
            "status": "cropping_completed", 
            "message": f"Video cropping completed with {len(normalized_segments)} segments from sentiment analysis",
            "cropped_video_path": cropped_path,
            "cropped_filename": os.path.basename(cropped_path),
            "segments_processed": len(normalized_segments),
            "segments_used": normalized_segments,
            "total_duration": sum(seg["end"] - seg["start"] for seg in normalized_segments)
        }
        
    except Exception as e:
        error_msg = f"Video cropping failed: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post('/api/video/download')
def download_processed_video(request: DownloadProcessedVideoRequest):
    """
    Download the final processed video file with music added to pre-cropped video
    Requires video to be cropped first via /api/video/crop
    """
    job_id = request.job_id
    
    # Check if video has been cropped first
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found. Must crop video first.")
    
    job = job_status[job_id]
    if not job.processed_video or not job.processed_video.get("cropping_complete"):
        raise HTTPException(status_code=400, detail="Video must be cropped first. Call /api/video/crop first.")
    
    # Get cropped video path from job status
    cropped_video_path = job.processed_video.get("cropped_video_path")
    if not cropped_video_path or not os.path.exists(cropped_video_path):
        raise HTTPException(status_code=404, detail="Cropped video file not found")
    
    try:
        print(f"🎵 Adding music to cropped video for job: {job_id}")
        print(f"   📁 Cropped video: {job.processed_video.get('cropped_filename')}")
        print(f"   🎵 Audio timestamps: {len(request.audio_timestamps)}")
        print(f"   🔊 Video volume: {request.video_volume}")
        print(f"   🎼 Music volume: {request.music_volume}")
        if request.output_filename:
            print(f"   📝 Custom filename: {request.output_filename}")
        
        # Create output path for final video
        os.makedirs("../processed_videos", exist_ok=True)
        
        # Use custom filename if provided
        if request.output_filename:
            final_filename = f"{request.output_filename}.mp4"
        else:
            final_filename = f"{job_id}_final.mp4"
        
        final_video_path = f"../processed_videos/{final_filename}"
        
        # Add music to the pre-cropped video
        final_path = add_music_to_video(
            video_filepath=cropped_video_path,
            music_tracks=request.audio_timestamps,
            output_path=final_video_path,
            video_volume=request.video_volume,
            music_volume=request.music_volume
        )
        
        # Update job status with final video info
        job.status = JobStatus.COMPLETED
        job.message = "Video processing completed with music"
        job.processed_video.update({
            "final_video_path": final_path,
            "final_filename": os.path.basename(final_path),
            "music_tracks_count": len(request.audio_timestamps),
            "video_volume": request.video_volume,
            "music_volume": request.music_volume,
            "custom_filename": request.output_filename,
            "processing_complete": True
        })
        
        # Verify final output exists
        if not os.path.exists(final_path):
            raise RuntimeError("Final processed video was not created")
        
        file_size = os.path.getsize(final_path)
        print(f"✅ Music processing completed successfully!")
        print(f"   📁 Final video: {os.path.basename(final_path)}")
        print(f"   📊 Size: {file_size / (1024*1024):.1f} MB")
        
        # Use custom filename for download if provided
        download_filename = f"{request.output_filename}.mp4" if request.output_filename else f"processed_trailer_{job_id}.mp4"
    
        return FileResponse(
                path=final_path,
            media_type='video/mp4',
                filename=download_filename
        )
        
    except Exception as e:
        error_msg = f"Music processing failed: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

# Health check endpoint
@app.get('/health')
def health_check():
    return {"status": "healthy", "service": "TrailMixer Video Processing API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)