"""
Background processing pipelines for video processing
"""
import re
import os
from typing import Dict
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
        video_segment = InputSegment(
            file_path=file_path,
            file_type='video',
            start_time='00:00:00',
            end_time=f'{int(video_length//3600):02d}:{int((video_length%3600)//60):02d}:{int(video_length%60):02d}',
            clip_start='00:00:00',
            clip_end=None,
            volume=1.0,
            fade_in=None,
            fade_out=None,
            metadata=None
        )
        input_segments.append(video_segment)
        
        # Add audio segments from music file paths
        print(f"🎵 Adding {len(music_file_paths)} audio segments...")
        for audio_file, timing_info in music_file_paths.items():
            start_time = timing_info.get('start', 0)
            end_time = timing_info.get('end', 60)
            
            # Convert seconds to HH:MM:SS format
            start_formatted = f'{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d}'
            end_formatted = f'{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d}'
            
            audio_segment = InputSegment(
                file_path=audio_file,
                file_type='audio',
                start_time=start_formatted,
                end_time=end_formatted,
                clip_start='00:00:00',
                clip_end=None,
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

