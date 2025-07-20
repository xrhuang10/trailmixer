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
    
    # Get upload results to find the source video
    if job_id not in upload_results:
        raise HTTPException(status_code=404, detail="Job not found. Must upload video first.")
    
    upload_result = upload_results[job_id]
    if not upload_result["success"]:
        raise HTTPException(status_code=400, detail="Cannot process video - upload failed")
    
    # Get video info from upload results
    video_info = upload_result["videos"][0] if upload_result["videos"] else {}
    source_video_path = video_info.get("file_path")
    source_filename = video_info.get("filename", f"video_{job_id}.mp4")
    
    if not source_video_path:
        raise HTTPException(status_code=404, detail="Source video file path not found")
    
    try:
        print(f"🎯 Starting synchronous video processing for job: {job_id}")
        print(f"📁 Source video: {source_filename}")
        print(f"📍 Source path: {source_video_path}")
        
        # Convert timestamps to the format expected by crop_and_stitch_video_segments
        segments = []
        for i, timestamp in enumerate(request.timestamps):
            # Extract start and end times from the timestamp dict
            # The timestamps might have different key names, so try common variations
            start_time = timestamp.get('start_time', timestamp.get('start', 0))
            end_time = timestamp.get('end_time', timestamp.get('end', 0))
            
            if isinstance(start_time, str):
                # Convert time string to seconds if needed
                start_time = float(start_time)
            if isinstance(end_time, str):
                end_time = float(end_time)
            
            segment = {
                "start": start_time,
                "end": end_time
            }
            segments.append(segment)
            
            print(f"   📹 Segment {i+1}: {start_time}s - {end_time}s (duration: {end_time-start_time:.1f}s)")
            print(f"       Sentiment: {timestamp.get('sentiment', 'unknown')}")
            print(f"       Style: {timestamp.get('music_style', 'unknown')}")
        
        # Create output path for the processed video
        output_filename = request.output_filename or f"{job_id}_processed.mp4"
        output_path = f"../processed_videos/{output_filename}"
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        print(f"🎬 Cropping and stitching video segments...")
        print(f"   📹 Input segments: {len(segments)}")
        print(f"   📁 Output: {output_filename}")
        
        # Import and use the crop_and_stitch_video_segments function
        from pipeline import crop_and_stitch_video_segments
        
        # Crop and stitch the video segments
        final_video_path = crop_and_stitch_video_segments(
            video_filepath=source_video_path,
            segments=segments,
            output_path=output_path
        )
        
        # TODO: Add background music processing and mixing
        # After cropping and stitching, we need to:
        # 1. Process audio tracks from request.music_file_paths
        # 2. Apply volume, fade in/out, and timing adjustments  
        # 3. Mix background audio with the cropped video audio
        # 4. Apply audio effects and normalization
        # This will require using FFmpeg to combine the cropped video with the selected music tracks
        
        # Calculate total duration
        total_duration = sum(seg["end"] - seg["start"] for seg in segments)
        
        # Create or update job status with results
        if job_id not in job_status:
            job_status[job_id] = JobInfo(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                message="Video processing completed with custom timestamps",
                filename=source_filename,
                file_path=source_video_path,
                created_at=datetime.datetime.now().isoformat(),
                twelve_labs_video_id=video_info.get('twelve_labs_video_id'),
                sentiment_analysis=None,
                processed_video={
                    "output_path": final_video_path,
                    "output_filename": output_filename,
                    "segments_count": len(segments),
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
                "output_path": final_video_path,
                "output_filename": output_filename,
                "segments_count": len(segments),
                "total_duration": total_duration,
                "processing_complete": True,
                "created_with_custom_timestamps": True
            }
        
        print(f"✅ Video processing completed successfully for job: {job_id}")
        print(f"   📁 Output: {os.path.basename(final_video_path)}")
        print(f"   📊 Segments: {len(segments)}")
        print(f"   ⏱️ Total duration: {total_duration:.1f}s")
        
        return {
            "job_id": job_id,
            "status": JobStatus.COMPLETED.value,
            "message": f"Video processing completed with {len(segments)} segments",
            "output_filename": output_filename,
            "output_path": final_video_path,
            "processing_details": {
                "timestamp_segments": len(request.timestamps),
                "segments_processed": len(segments),
                "total_duration": total_duration,
                "source_filename": source_filename
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

# @app.get('/api/video/download/{job_id}')
# def download_processed_video(job_id: str):
#     """
#     Download the final processed video file
#     """
#     if job_id not in job_status:
#         raise HTTPException(status_code=404, detail="Job not found")
    
#     job = job_status[job_id]
    
#     if job.status != JobStatus.COMPLETED:
#         raise HTTPException(status_code=400, detail="Video processing not yet completed")
    
#     processed_data = job.processed_video
#     if not processed_data or not os.path.exists(processed_data["output_path"]):
#         raise HTTPException(status_code=404, detail="Processed video file not found")
    
#     return FileResponse(
#         path=processed_data["output_path"],
#         media_type='video/mp4',
#         filename=f"processed_{job.filename}"
#     )

@app.get('/api/video/download/{job_id}')
def download_processed_video(job_id: str):
    """
    Download the final processed video file (mocked with speed video)
    """
    # Mock implementation - return a speed video from videos directory
    mock_video_path = "videos/speed.mp4"
    
    if not os.path.exists(mock_video_path):
        raise HTTPException(status_code=404, detail="Mock speed video file not found")
    
    print(f"📥 Serving mock speed video for download: {job_id}")
    
    return FileResponse(
        path=mock_video_path,
        media_type='video/mp4',
        filename=f"processed_trailer_{job_id}.mp4"
    )

# Health check endpoint
@app.get('/health')
def health_check():
    return {"status": "healthy", "service": "TrailMixer Video Processing API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)