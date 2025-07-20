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
from pipeline import process_video_pipeline, process_multi_video_pipeline, upload_video_pipeline, stitch_videos_together
from video_processor import extract_segments

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

    file_paths = []

    orig_filename = video_file.filename
    file_path = os.path.join(upload_dir, f"{job_id}_{orig_filename}")
    try:
        with open(file_path, "wb") as buffer:
            content = video_file.file.read()
            buffer.write(content)
        
        # If it's a .mov, convert to .mp4 and use the new path
        if orig_filename.lower().endswith('.mov'):
            try:
                converted_path = convert_mov_to_mp4(file_path)
                os.remove(file_path)  # Optional: remove original .mov
                file_path = converted_path
                # Also update filename for the rest of the pipeline
                video_file.filename = os.path.basename(converted_path)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"FFmpeg conversion failed: {str(e)}")
        
        file_paths.append(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file {i+1}: {str(e)}")
    finally:
        video_file.file.close()
    
    # Save uploaded files as temporary files
    temp_files = []
    uploaded_filenames = []
    
    try:
        for i, video_file in enumerate(video_files):
            if not video_file.content_type or not video_file.content_type.startswith('video/'):
                raise HTTPException(status_code=400, detail=f"File {i+1} must be a video")
            if not video_file.filename:
                raise HTTPException(status_code=400, detail=f"Filename for file {i+1} is required")
            
            # Create temporary file with proper extension
            file_extension = os.path.splitext(video_file.filename)[1] or '.mp4'
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_extension,
                prefix=f"upload_{job_id}_{i}_"
            )
            
            try:
                # Save uploaded content to temporary file
                content = video_file.file.read()
                temp_file.write(content)
                temp_file.flush()
                
                temp_files.append(temp_file.name)
                uploaded_filenames.append(video_file.filename)
                print(f"📁 Saved temp video {i+1}/{len(video_files)}: {video_file.filename}")
                print(f"   Temp path: {temp_file.name}")
                
            finally:
                temp_file.close()
                video_file.file.close()
        
        # Stitch videos together if multiple videos uploaded
        if len(temp_files) > 1:
            print(f"🔗 Stitching {len(temp_files)} videos together...")
            
            # Create temporary output file for stitched result
            stitched_temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.mp4',
                prefix=f"stitched_{job_id}_"
            )
            stitched_temp_file.close()  # Close file handle so FFmpeg can write to it
            
            try:
                final_video_path = stitch_videos_together(temp_files, stitched_temp_file.name)
                final_filename = f"stitched_{len(temp_files)}_videos.mp4"
                print(f"✅ Videos stitched successfully: {final_filename}")
                
            except Exception as e:
                print(f"❌ Video stitching failed: {str(e)}")
                # Clean up stitched temp file on error
                try:
                    os.unlink(stitched_temp_file.name)
                except:
                    pass
                raise HTTPException(status_code=500, detail=f"Failed to stitch videos: {str(e)}")
        else:
            # Single video - use temp file as is
            final_video_path = temp_files[0]
            final_filename = uploaded_filenames[0]
            print(f"📹 Single video uploaded: {final_filename}")
        
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
                processed_video=None
            )
            
            # Use upload pipeline as helper function (runs steps 1-3)
            upload_video_pipeline(temp_job_id, temp_job_status)
            
            # Get results from the pipeline
            temp_job = temp_job_status[temp_job_id]
            
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
        
        print(f"🎵 Returning simplified upload response")
        
        # Extract music file paths from the first video result
        music_file_paths = {}
        if video_results and len(video_results) > 0:
            video_result = video_results[0]
            music_file_paths = video_result.get("music_file_paths", {})
        
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
            "processing_errors": video_results[0].get("audio_error") if video_results and not video_results[0].get("success", True) else None
        }
        
        # Return simplified response
        return VideoUploadSimpleResponse(
            job_id=job_id,
            music_file_paths=music_file_paths,
            debug_info=debug_info
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Unexpected error during upload processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")
    
    finally:
        # Clean up all temporary files including the stitched video
        all_temp_files = temp_files.copy()
        
        # Add the final stitched video to cleanup if it exists and was created
        if 'final_video_path' in locals() and len(temp_files) > 1:
            # Only clean up stitched video if it was created (multiple videos)
            all_temp_files.append(final_video_path)
        
        for temp_file_path in all_temp_files:
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    if temp_file_path in temp_files:
                        print(f"🧹 Cleaned up temp input file: {os.path.basename(temp_file_path)}")
                    else:
                        print(f"🧹 Cleaned up stitched temp file: {os.path.basename(temp_file_path)}")
            except Exception as cleanup_error:
                print(f"⚠️ Failed to clean up temp file {temp_file_path}: {cleanup_error}")

# Request model for video processing with timestamps
class VideoProcessingTimestampsRequest(BaseModel):
    """Request for processing video with specific timestamps and clips"""
    timestamps: List[Dict[str, Any]] = Field(..., description="List of timestamp segments to process")
    music_file_paths: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Music file paths with timing info")
    output_filename: Optional[str] = Field(None, description="Custom output filename")
    crop_settings: Optional[Dict[str, Any]] = Field(None, description="Video cropping settings")
    audio_settings: Optional[Dict[str, Any]] = Field(None, description="Audio processing settings")

@app.post('/api/video/process/{job_id}')
def process_video(job_id: str, request: VideoProcessingTimestampsRequest):
    """
    Create/recreate video with provided audio timestamps
    Synchronous processing - can be called multiple times for the same job when user edits audio timestamps
    """
    print(f"🎬 Creating video for job: {job_id}")
    print(f"📊 Processing {len(request.timestamps)} timestamp segments")
    print(f"🎵 Processing {len(request.music_file_paths)} music tracks")
    
    # Validate input
    if not request.timestamps:
        raise HTTPException(status_code=400, detail="No timestamps provided for processing")
    
    if not request.music_file_paths:
        raise HTTPException(status_code=400, detail="No music file paths provided for processing")
    
    # Get upload results to find the source video
    if job_id not in upload_results:
        raise HTTPException(status_code=404, detail="Job not found. Must upload video first.")
    
    upload_result = upload_results[job_id]
    if not upload_result["success"]:
        raise HTTPException(status_code=400, detail="Cannot process video - upload failed")
    
    # Get video info from upload results
    video_info = upload_result["videos"][0] if upload_result["videos"] else {}
    source_video_path = video_info.get("file_path")
    if not source_video_path:
        raise HTTPException(status_code=404, detail="Source video file path not found")
    
    try:
        print(f"🎯 Starting synchronous video processing for job: {job_id}")
        print(f"📁 Source video: {video_info.get('filename', 'unknown')}")
        
        # TODO: Implement video cropping logic
        # Extract specific time segments from the original video based on timestamps
        # Use FFmpeg to crop video segments: ffmpeg -i input.mp4 -ss START_TIME -t DURATION -c copy output_segment.mp4
        cropped_clips = []
        for i, timestamp in enumerate(request.timestamps):
            start_time = timestamp.get('start_time', 0)
            end_time = timestamp.get('end_time', 0)
            duration = end_time - start_time
            
            print(f"   📹 Clip {i+1}: {start_time}s - {end_time}s (duration: {duration}s)")
            print(f"       Sentiment: {timestamp.get('sentiment', 'unknown')}")
            print(f"       Style: {timestamp.get('music_style', 'unknown')}")
            
            cropped_clip = {
                "clip_index": i,
                "source_file": source_video_path,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "temp_output": f"temp_clip_{i}_{job_id}.mp4",
                "sentiment": timestamp.get('sentiment', 'unknown'),
                "music_style": timestamp.get('music_style', 'unknown')
            }
            cropped_clips.append(cropped_clip)
        
        print(f"✅ Prepared {len(cropped_clips)} video clips for processing")
        
        # TODO: Implement audio processing and synchronization
        # Process audio tracks to match the video segments timing
        # Apply volume, fade in/out, and timing adjustments
        processed_audio = []
        for audio_file, timing_info in request.music_file_paths.items():
            start_time = timing_info.get('start', 0)
            end_time = timing_info.get('end', 0)
            volume = timing_info.get('volume', 0.3)
            
            print(f"   🎵 Audio: {audio_file}")
            print(f"       Timing: {start_time}s - {end_time}s")
            print(f"       Volume: {volume}")
            
            audio_segment = {
                "audio_file": audio_file,
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "volume": volume,
                "fade_in": timing_info.get('fade_in', '0.5'),
                "fade_out": timing_info.get('fade_out', '0.5')
            }
            processed_audio.append(audio_segment)
        
        print(f"✅ Prepared {len(processed_audio)} audio segments for processing")
        
        # TODO: Implement final video assembly and stitching
        # 1. Crop video segments using FFmpeg based on timestamps
        # 2. Prepare audio tracks with proper timing and effects
        # 3. Concatenate video clips in sequence
        # 4. Mix background audio with video audio
        # 5. Apply transitions and effects between segments
        # 6. Render final output video
        
        output_filename = request.output_filename or f"{job_id}_final.mp4"
        output_path = f"../processed_videos/{output_filename}"
        
        print(f"🎬 TODO: Final video assembly")
        print(f"   📹 Input clips: {len(cropped_clips)}")
        print(f"   🎵 Audio tracks: {len(processed_audio)}")
        print(f"   📁 Output: {output_filename}")
        
        # Calculate total duration
        total_duration = sum(clip["duration"] for clip in cropped_clips)
        
        # Create or update job status with results
        if job_id not in job_status:
            job_status[job_id] = JobInfo(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                message="Video processing completed with custom timestamps",
                filename=video_info.get('filename', f"video_{job_id}.mp4"),
                file_path=source_video_path,
                created_at=datetime.datetime.now().isoformat(),
                twelve_labs_video_id=video_info.get('twelve_labs_video_id'),
                sentiment_analysis=None,
                processed_video={
                    "output_path": output_path,
                    "output_filename": output_filename,
                    "cropped_clips": cropped_clips,
                    "audio_segments": processed_audio,
                    "total_duration": total_duration,
                    "processing_complete": True,
                    "created_with_custom_timestamps": True
                }
            )
        else:
            # Update existing job
            job = job_status[job_id]
            job.status = JobStatus.COMPLETED
            job.message = "Video processing completed with custom timestamps"
            job.processed_video = {
                "output_path": output_path,
                "output_filename": output_filename,
                "cropped_clips": cropped_clips,
                "audio_segments": processed_audio,
                "total_duration": total_duration,
                "processing_complete": True,
                "created_with_custom_timestamps": True
            }
        
        print(f"✅ Video processing completed synchronously for job: {job_id}")
        
        return {
            "job_id": job_id,
            "status": JobStatus.COMPLETED.value,
            "message": f"Video processing completed with {len(cropped_clips)} clips and {len(processed_audio)} audio tracks",
            "output_filename": output_filename,
            "processing_details": {
                "timestamp_segments": len(request.timestamps),
                "audio_tracks": len(request.music_file_paths),
                "total_duration": total_duration,
                "cropped_clips": cropped_clips,
                "audio_segments": processed_audio
            }
        }
        
    except Exception as e:
        error_msg = f"Video processing failed: {str(e)}"
        print(f"❌ {error_msg}")
        
        # Update job status with error
        if job_id in job_status:
            job_status[job_id].status = JobStatus.FAILED
            job_status[job_id].message = error_msg
        
        raise HTTPException(status_code=500, detail=error_msg)

@app.get('/api/video/timestamps/{job_id}', response_model=MusicTimestampsResponse)
def get_music_timestamps(job_id: str):
    """
    Get music timestamps and processing results for uploaded video with resolved file paths
    Call this after /api/video/upload to get the JSON metadata including actual music file paths
    """
    if job_id not in upload_results:
        raise HTTPException(status_code=404, detail="Upload results not found for this job_id")
    
    result = upload_results[job_id]
    
    print(f"🎵 Returning music timestamps for job: {job_id}")
    print(f"   Videos processed: {result['video_count']}")
    print(f"   Success: {result['success']}")
    
    # The music_file_paths are already resolved by upload_video_pipeline -> get_music_file_paths()
    # No need to recreate the logic - just return the pre-resolved file paths
    for video in result["videos"]:
        if video.get("music_file_paths") and video.get("audio_selection_complete"):
            print(f"   🎵 Video: {video['filename']}")
            print(f"       Music tracks with resolved file paths: {len(video['music_file_paths'])}")
            
            # Log the resolved file paths for debugging
            for track_name, track_info in video["music_file_paths"].items():
                if isinstance(track_info, dict) and 'start' in track_info:
                    start_time = track_info.get('start', 0)
                    end_time = track_info.get('end', 0)
                    duration = end_time - start_time
                    print(f"       🎼 {track_name}: {start_time}s-{end_time}s ({duration:.1f}s)")
                    # track_name is already the resolved file path from get_music_file_paths()
                    print(f"           File: {track_name}")
                    print(f"           Exists: {'✓' if os.path.exists(track_name) else '✗'}")
        else:
            print(f"   ⚠️ Video: {video['filename']} - No resolved music file paths")
    
    # Extract filepath from the first video result
    main_filepath = None
    if result["videos"] and len(result["videos"]) > 0:
        main_filepath = result["videos"][0].get("file_path")
    
    return MusicTimestampsResponse(
        job_id=result["job_id"],
        video_count=result["video_count"],
        videos=result["videos"],
        success=result["success"],
        message=result["message"],
        filepath=main_filepath
    )

@app.get('/api/video/status/{job_id}')
def get_processing_status(job_id: str):
    """
    Get current status of video processing job
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": job.message,
        "filename": job.filename,
        "created_at": job.created_at,
        "twelve_labs_video_id": job.twelve_labs_video_id,
        "processed_video": job.processed_video
    }

@app.get('/api/video/download/{job_id}')
def download_processed_video(job_id: str):
    """
    Download the final processed video file
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.processed_video
    if not processed_data or not os.path.exists(processed_data["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        path=processed_data["output_path"],
        media_type='video/mp4',
        filename=f"processed_{job.filename}"
    )



@app.get('/api/video/stream/{job_id}')
def stream_processed_video(job_id: str):
    """
    Stream the processed video for in-browser playback
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_status[job_id]
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
    processed_data = job.processed_video
    if not processed_data or not os.path.exists(processed_data["output_path"]):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        path=processed_data["output_path"],
        media_type='video/mp4',
        headers={"Accept-Ranges": "bytes"}
    )

# Health check endpoint
@app.get('/health')
def health_check():
    return {"status": "healthy", "service": "TrailMixer Video Processing API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)