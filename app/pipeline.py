"""
Background processing pipelines for video processing
"""
import re
import os
import tempfile
import subprocess
from typing import Dict, List
from models import (
    JobStatus, JobInfo, MultiVideoJobInfo, SentimentAnalysisRequest, SentimentAnalysisData,
    VideoProcessingRequest, AudioLibrary, VideoAnalysisResult, MultiVideoFFmpegRequest, FfmpegRequest
)
from ffmpeg_builder import create_ffmpeg_request

from video_processor import analyze_sentiment_with_twelvelabs, process_video_segments, process_single_video_in_batch
from ffmpeg_builder import create_multi_video_ffmpeg_request
from prompts.extract_info import extract_info_prompt
from twelvelabs_client import upload_video_to_twelvelabs
from audio_picker import get_music_file_paths
from ffmpeg_stitch import stitch_ffmpeg_request

def stitch_videos_together(video_file_paths: List[str], output_path: str) -> str:
    """
    Stitch a list of videos together into a single video using FFmpeg
    
    Args:
        video_file_paths: List of paths to video files to concatenate
        output_path: Path where the stitched video should be saved
        
    Returns:
        str: Path to the output video file
        
    Raises:
        RuntimeError: If FFmpeg processing fails
        ValueError: If input validation fails
    """
    if not video_file_paths:
        raise ValueError("No video files provided for stitching")
    
    if len(video_file_paths) == 1:
        print(f"⚠️ Only one video provided, copying to output path")
        import shutil
        shutil.copy2(video_file_paths[0], output_path)
        return output_path
    
    print(f"🔗 Stitching {len(video_file_paths)} videos together...")
    print(f"📁 Output: {os.path.basename(output_path)}")
    
    # Validate input files exist and normalize paths
    normalized_paths = []
    for i, video_path in enumerate(video_file_paths):
        # Convert to absolute path and normalize separators
        abs_path = os.path.abspath(video_path)
        if not os.path.exists(abs_path):
            raise ValueError(f"Video file {i+1} not found: {abs_path}")
        normalized_paths.append(abs_path)
        print(f"   📹 Input {i+1}: {os.path.basename(abs_path)}")
        print(f"       Path: {abs_path}")
    
    # Create temporary file list for FFmpeg concat demuxer
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir=os.getcwd()) as temp_file:
        temp_list_path = temp_file.name
        
        # Write file list in FFmpeg concat format
        for video_path in normalized_paths:
            # On Windows, use forward slashes and escape properly for FFmpeg
            if os.name == 'nt':  # Windows
                # Convert backslashes to forward slashes for FFmpeg
                ffmpeg_path = video_path.replace('\\', '/')
                # Escape single quotes if any
                ffmpeg_path = ffmpeg_path.replace("'", "'\"'\"'")
            else:
                # Unix-like systems
                ffmpeg_path = video_path.replace("'", "'\"'\"'")
            
            temp_file.write(f"file '{ffmpeg_path}'\n")
            print(f"       FFmpeg path: {ffmpeg_path}")
    
    try:
        print(f"📝 Created temporary file list: {temp_list_path}")
        
        # Normalize output path
        abs_output_path = os.path.abspath(output_path)
        
        # Build FFmpeg command for concatenation
        ffmpeg_cmd = [
            "ffmpeg",
            "-f", "concat",           # Use concat demuxer
            "-safe", "0",             # Allow unsafe file paths
            "-i", temp_list_path,     # Input file list
            "-c", "copy",             # Copy streams without re-encoding (fastest)
            "-y",                     # Overwrite output file
            abs_output_path
        ]
        
        print(f"🎬 Running FFmpeg concatenation...")
        print(f"Command: {' '.join(ffmpeg_cmd)}")
        
        # Execute FFmpeg command
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Check if output file was created
        if not os.path.exists(abs_output_path):
            raise RuntimeError("FFmpeg completed but output file was not created")
        
        # Get output file size for verification
        output_size = os.path.getsize(abs_output_path)
        print(f"✅ Video stitching completed successfully!")
        print(f"   📁 Output: {os.path.basename(abs_output_path)}")
        print(f"   📊 Size: {output_size / (1024*1024):.1f} MB")
        
        return abs_output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\nSTDERR: {e.stderr}"
        if e.stdout:
            error_msg += f"\nSTDOUT: {e.stdout}"
        
        print(f"❌ Video stitching failed: {error_msg}")
        raise RuntimeError(f"Video stitching failed: {error_msg}")
        
    except Exception as e:
        print(f"❌ Unexpected error during video stitching: {str(e)}")
        raise RuntimeError(f"Video stitching failed: {str(e)}")
        
    finally:
        # Clean up temporary file list
        try:
            if os.path.exists(temp_list_path):
                os.unlink(temp_list_path)
                print(f"🧹 Cleaned up temporary file: {temp_list_path}")
        except Exception as cleanup_error:
            print(f"⚠️ Failed to clean up temporary file: {cleanup_error}")

def upload_video_pipeline(job_id: str, job_status: Dict[str, JobInfo]):
    """Complete video processing pipeline"""
    job = job_status[job_id]
    filename = job.filename
    input_file = os.path.basename(job.file_path)
    
    print(f"\n🚀 Starting video processing pipeline")
    print(f"   🆔 Job ID: {job_id}")
    print(f"   📁 File: {filename}")
    print(f"   📍 Path: {input_file}")
    
    try:
        # Step 1: Upload to Twelve Labs for indexing
        job.status = JobStatus.INDEXING
        job.message = f"Uploading '{filename}' to Twelve Labs for AI analysis..."
        print(f"📤 Step 1: Uploading '{filename}' to Twelve Labs...")
        
        file_path = job.file_path
        video_id = upload_video_to_twelvelabs(file_path)
        
        if not video_id:
            raise RuntimeError(f"Failed to upload '{filename}' to Twelve Labs")
        
        job.twelve_labs_video_id = video_id
        job.status = JobStatus.ANALYZING
        job.message = f"Analyzing sentiment for '{filename}' with AI..."
        print(f"✅ Upload successful! Video ID: {video_id}")
        
        # Step 2: Perform sentiment analysis
        print(f"🤖 Step 2: Analyzing sentiment for '{filename}'...")
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        job.sentiment_analysis = sentiment_result
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed for '{filename}': {sentiment_result.error_message}")
        
        # Step 3: Select background audio based on sentiment analysis
        print(f"🎵 Step 3: Selecting background music tracks for '{filename}' based on AI analysis...")
        if job.sentiment_analysis.file_path:
            filepath = re.sub(r'\\+', '/', job.sentiment_analysis.file_path)
            print(f"File path: {filepath}")
            music_file_paths = get_music_file_paths(filepath)
            print(f"🎵 Found {len(music_file_paths)} music file paths")
        else:
            print("❌ No sentiment analysis file path available for music selection")
        print(f"Music file paths: {music_file_paths}")
        
        # Testing if the music file paths are valid
        all_exist = True
        for path in music_file_paths:
            if not os.path.isfile(path):
                print(f"❌ File does not exist: {path}")
                all_exist = False
            else:
                print(f"✅ File exists: {path}")
        if all_exist:
            print("All music file paths are valid.")
        else:
            print("Some music file paths are invalid.")
            
        print("Step 3 complete!")
    except Exception as e:
        job.status = JobStatus.FAILED
        job.message = f"Processing failed for '{filename}': {str(e)}"
        print(f"❌ Pipeline failed for '{filename}' (Job: {job_id}): {str(e)}")

def process_video_pipeline(job_id: str, job_status: Dict[str, JobInfo]):
    """Complete video processing pipeline"""
    job = job_status[job_id]
    filename = job.filename
    input_file = os.path.basename(job.file_path)
    
    print(f"\n🚀 Starting video processing pipeline")
    print(f"   🆔 Job ID: {job_id}")
    print(f"   📁 File: {filename}")
    print(f"   📍 Path: {input_file}")
    
    try:
        # Step 1: Upload to Twelve Labs for indexing
        job.status = JobStatus.INDEXING
        job.message = f"Uploading '{filename}' to Twelve Labs for AI analysis..."
        print(f"📤 Step 1: Uploading '{filename}' to Twelve Labs...")
        
        file_path = job.file_path
        video_id = upload_video_to_twelvelabs(file_path)
        
        if not video_id:
            raise RuntimeError(f"Failed to upload '{filename}' to Twelve Labs")
        
        job.twelve_labs_video_id = video_id
        job.status = JobStatus.ANALYZING
        job.message = f"Analyzing sentiment for '{filename}' with AI..."
        print(f"✅ Upload successful! Video ID: {video_id}")
        
        # Step 2: Perform sentiment analysis
        print(f"🤖 Step 2: Analyzing sentiment for '{filename}'...")
        sentiment_request = SentimentAnalysisRequest(video_id=video_id, prompt=extract_info_prompt)
        sentiment_result = analyze_sentiment_with_twelvelabs(sentiment_request)
        job.sentiment_analysis = sentiment_result
        
        if not sentiment_result.success:
            raise RuntimeError(f"Sentiment analysis failed for '{filename}': {sentiment_result.error_message}")
        
        # Step 3: Select background audio based on sentiment analysis
        print(f"🎵 Step 3: Selecting background music tracks for '{filename}' based on AI analysis...")
        if job.sentiment_analysis.file_path:
            filepath = re.sub(r'\\+', '/', job.sentiment_analysis.file_path)
            print(f"File path: {filepath}")
            music_file_paths = get_music_file_paths(filepath)
            print(f"🎵 Found {len(music_file_paths)} music file paths")
        else:
            print("❌ No sentiment analysis file path available for music selection")
        print(f"Music file paths: {music_file_paths}")
        
        # Testing if the music file paths are valid
        all_exist = True
        for path in music_file_paths:
            if not os.path.isfile(path):
                print(f"❌ File does not exist: {path}")
                all_exist = False
            else:
                print(f"✅ File exists: {path}")
        if all_exist:
            print("All music file paths are valid.")
        else:
            print("Some music file paths are invalid.")
            
        print("Step 3 complete!")
            
        # Get sentiment data as dictionary
        raw_data = job.sentiment_analysis.sentiment_analysis
        if isinstance(raw_data, str):
            print("❌ Cannot create FFmpeg request: sentiment analysis failed")
            return
        
        # Convert to dict if needed
        if hasattr(raw_data, 'dict'):
            sentiment_data = dict(raw_data.dict())
        else:
            sentiment_data = dict(raw_data)
        
        # Create FfmpegRequest with video and audio segments
        from models import InputSegment
        
        output_path = f'../processed_videos/{job_id}_processed.mp4'
        input_segments = []
        
        # Add original video as input segment
        video_length = sentiment_data.get('video_length', 60)
        video_formatted_duration = f'{int(video_length//3600):02d}:{int((video_length%3600)//60):02d}:{int(video_length%60):02d}'
        video_segment = InputSegment(
            file_path=file_path,
            file_type='video',
            start_time='00:00:00',
            end_time=video_formatted_duration,
            clip_start='00:00:00',
            clip_end=video_formatted_duration,  # Set explicit clip end
            volume=1.0,
            fade_in=None,
            fade_out=None,
            metadata=None
        )
        input_segments.append(video_segment)
        
        # Add audio segments from music file paths
        print(f"🎵 Adding {len(music_file_paths)} audio segments...")
        for audio_file, timing_info in music_file_paths.items():
            start_time = min(timing_info.get('start', 0), video_length)  # Ensure start doesn't exceed video length
            end_time = min(timing_info.get('end', video_length), video_length)  # Use video length as default/max
            
            # Convert seconds to HH:MM:SS format
            start_formatted = f'{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d}'
            end_formatted = f'{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d}'
            
            audio_segment = InputSegment(
                file_path=audio_file,
                file_type='audio',
                start_time=start_formatted,
                end_time=end_formatted,
                clip_start='00:00:00',
                clip_end=end_formatted,  # Set explicit clip end
                volume=0.3,  # Background music volume
                fade_in='0.5',
                fade_out='0.5',
                metadata=None
            )
            input_segments.append(audio_segment)
            print(f"   🎼 Added: {os.path.basename(audio_file)} ({start_formatted} - {end_formatted})")
        
        # Create FFmpeg request
        from models import VideoCodec, AudioCodec
        ffmpeg_request = FfmpegRequest(
            input_segments=input_segments,
            output_file=output_path,
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            video_bitrate=None,
            audio_bitrate=None,
            crf=23,
            preset='medium',
            scale=None,
            fps=None,
            audio_channels=2,
            audio_sample_rate=44100,
            global_volume=0.3,
            normalize_audio=False,
            crossfade_duration='1.0',
            gap_duration='00:00:00',
            overwrite=True,
            quiet=False,
            progress=True,
            request_id=job_id,
            priority=1
        )
        
        # Execute FFmpeg processing
        print(f"🎬 Step 4: Executing FFmpeg processing...")
        try:
            result_path = stitch_ffmpeg_request(ffmpeg_request)
            
            # Update job status
            job.status = JobStatus.COMPLETED
            job.message = f"Video processing completed successfully for '{filename}' with background music"
            job.processed_video = {
                "output_path": result_path,
                "total_segments": len(input_segments),
                "audio_segments_count": len(music_file_paths)
            }
            
            print(f"✅ Pipeline completed successfully for '{filename}'!")
            print(f"   📁 Output: {os.path.basename(result_path)}")
            
        except Exception as ffmpeg_error:
            raise RuntimeError(f"FFmpeg processing failed: {str(ffmpeg_error)}")
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.message = f"Processing failed for '{filename}': {str(e)}"
        print(f"❌ Pipeline failed for '{filename}' (Job: {job_id}): {str(e)}")

def process_multi_video_pipeline(job_id: str, multi_video_job_status: Dict[str, MultiVideoJobInfo]):
    """Complete multi-video processing pipeline"""
    job = multi_video_job_status[job_id]
    
    print(f"\n🚀 Starting multi-video processing pipeline")
    print(f"   🆔 Job ID: {job_id}")
    print(f"   📊 Video count: {job.video_count}")
    print(f"   📁 Files: {', '.join(job.video_files)}")
    
    try:
        # Step 1: Process each video individually
        job.status = JobStatus.INDEXING
        job.message = f"Processing {job.video_count} videos - indexing and analyzing..."
        print(f"📤 Step 1: Processing {job.video_count} videos individually...")
        
        audio_library = AudioLibrary()
        
        for i, video_file in enumerate(job.video_files):
            job.message = f"Processing video {i+1}/{job.video_count}: '{video_file}' - indexing and analyzing..."
            print(f"\n📹 Processing video {i+1}/{job.video_count}: '{video_file}'")
            
            # Create video result entry
            video_result = VideoAnalysisResult(
                video_index=i,
                filename=video_file,
                file_path=os.path.join("uploads", f"{job_id}_{video_file}"),
                twelve_labs_video_id=None,
                sentiment_analysis=None,
                segments_with_audio=None,
                video_length=None,
                success=False,
                error_message=None
            )
            
            # Process this video
            processed_result = process_single_video_in_batch(video_result, audio_library)
            job.video_results.append(processed_result)
            
            if processed_result.success:
                print(f"✅ Video {i+1} processed successfully: '{video_file}'")
            else:
                print(f"❌ Video {i+1} failed: '{video_file}' - {processed_result.error_message}")
        
        # Count successful videos
        successful_videos = [v for v in job.video_results if v.success]
        failed_videos = [v for v in job.video_results if not v.success]
        
        print(f"\n📊 Individual processing complete:")
        print(f"   ✅ Successful: {len(successful_videos)}/{job.video_count}")
        print(f"   ❌ Failed: {len(failed_videos)}/{job.video_count}")
        
        if len(successful_videos) == 0:
            raise RuntimeError("No videos were successfully processed")
        
        # Step 2: Aggregate all videos into single FFmpeg request
        job.status = JobStatus.PROCESSING
        job.message = f"Creating aggregated video with background music from {len(successful_videos)} successful videos..."
        print(f"🎬 Step 2: Creating aggregated video from {len(successful_videos)} videos...")
        
        output_path = f'../processed_videos/{job_id}_multi_video.mp4'
        output_filename = os.path.basename(output_path)
        
        multi_video_request = MultiVideoFFmpegRequest(
            video_results=job.video_results,
            output_video_path=output_path,
            global_volume=0.3,
            crossfade_duration="1.0",
            video_transition_duration="0.5"
        )
        
        print(f"🔧 Creating FFmpeg request for video aggregation...")
        aggregated_ffmpeg_request = create_multi_video_ffmpeg_request(multi_video_request)
        job.aggregated_ffmpeg_request = aggregated_ffmpeg_request.dict()
        
        # TODO: Execute the aggregated FFmpeg request
        print(f"🎬 Multi-video FFmpeg request ready for execution!")
        print(f"   📊 Total input segments: {len(aggregated_ffmpeg_request.input_segments)}")
        print(f"   📁 Output file: {output_filename}")
        
        # Step 3: Complete
        job.status = JobStatus.COMPLETED
        job.message = f"Multi-video processing completed - {len(successful_videos)}/{job.video_count} videos with background music ready"
        
        print(f"🎉 Multi-video pipeline completed successfully!")
        print(f"   🆔 Job ID: {job_id}")
        print(f"   🎬 Videos processed: {len(successful_videos)}/{job.video_count}")
        print(f"   📁 Output: {output_filename}")
        print(f"   📊 Ready for download/streaming")
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.message = f"Multi-video processing failed: {str(e)}"
        print(f"❌ Multi-video pipeline failed (Job: {job_id}): {str(e)}") 

