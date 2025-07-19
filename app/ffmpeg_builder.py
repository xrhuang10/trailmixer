"""
FFmpeg request building utilities
"""
import os
import uuid
from typing import List
from models import (
    FfmpegRequest, InputSegment, VideoCodec, AudioCodec, VideoSegmentWithAudio,
    VideoAnalysisResult, MultiVideoFFmpegRequest, SentimentAnalysisData
)

def seconds_to_time_format(seconds: float) -> str:
    """Convert seconds to HH:MM:SS.mmm format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def create_ffmpeg_request(
    original_video_path: str,
    output_video_path: str,
    video_length: float,
    segments_with_audio: List[VideoSegmentWithAudio],
    global_volume: float = 0.3,
    crossfade_duration: str = "1.0"
) -> FfmpegRequest:
    """
    Create FFmpeg request from video file and segments with audio selections
    """
    input_filename = os.path.basename(original_video_path)
    output_filename = os.path.basename(output_video_path)
    
    print(f"🎬 Creating FFmpeg request:")
    print(f"   📁 Input: {input_filename}")
    print(f"   📁 Output: {output_filename}")
    print(f"   ⏱️ Duration: {video_length}s")
    print(f"   🎵 Audio segments: {len(segments_with_audio)}")
    print(f"   🔊 Global volume: {global_volume:.1%}")
    
    input_segments = []
    
    # Add the original video as the base track
    video_segment = InputSegment(
        file_path=original_video_path,
        file_type="video",
        start_time="00:00:00",
        end_time=seconds_to_time_format(video_length),
        clip_start="00:00:00",
        clip_end=None,  # Use full video
        volume=1.0,  # Keep original video audio at full volume
        fade_in=None,
        fade_out=None,
        metadata={"type": "original_video"}
    )
    input_segments.append(video_segment)
    
    print(f"📹 Added base video track: {input_filename} (0s - {video_length}s)")
    
    # Add audio tracks for each segment with selected music
    for i, segment in enumerate(segments_with_audio):
        if segment.audio_selection:
            audio_filename = os.path.basename(segment.audio_selection.audio_file)
            segment_duration = segment.end_time - segment.start_time
            final_volume = segment.audio_selection.volume * global_volume
            
            audio_input = InputSegment(
                file_path=segment.audio_selection.audio_file,
                file_type="audio",
                start_time=seconds_to_time_format(segment.start_time),
                end_time=seconds_to_time_format(segment.end_time),
                clip_start="00:00:00",  # Start from beginning of audio file
                clip_end=None,  # Let FFmpeg loop if needed
                volume=final_volume,
                fade_in=segment.audio_selection.fade_in,
                fade_out=segment.audio_selection.fade_out,
                metadata={
                    "type": "background_music",
                    "segment_index": i,
                    "sentiment": segment.sentiment,
                    "music_style": segment.music_style,
                    "intensity": segment.intensity
                }
            )
            input_segments.append(audio_input)
            
            print(f"🎵 Segment {i+1}: {audio_filename}")
            print(f"   📍 Time: {segment.start_time}s - {segment.end_time}s ({segment_duration:.1f}s)")
            print(f"   🎭 Style: {segment.sentiment} | {segment.music_style} | {segment.intensity}")
            print(f"   🔊 Volume: {final_volume:.3f} | Fade: {segment.audio_selection.fade_in}s/{segment.audio_selection.fade_out}s")
    
    # Create the FFmpeg request
    request_id = str(uuid.uuid4())
    ffmpeg_request = FfmpegRequest(
        input_segments=input_segments,
        output_file=output_video_path,
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        video_bitrate=None,
        audio_bitrate=None,
        crf=23,  # Good quality
        preset="medium",
        scale=None,
        fps=None,
        audio_channels=2,
        audio_sample_rate=44100,
        global_volume=1.0,  # Already applied to individual segments
        normalize_audio=True,
        crossfade_duration=crossfade_duration,
        gap_duration="00:00:00",
        overwrite=True,
        quiet=False,
        progress=True,
        request_id=request_id,
        priority=5
    )
    
    print(f"✅ FFmpeg request created successfully!")
    print(f"   🆔 Request ID: {request_id[:8]}...")
    print(f"   📊 Total segments: {len(input_segments)} (1 video + {len(input_segments)-1} audio)")
    print(f"   ⚙️ Settings: {ffmpeg_request.video_codec.value}/{ffmpeg_request.audio_codec.value}, CRF={ffmpeg_request.crf}, preset={ffmpeg_request.preset}")
    print(f"   📁 Output: {output_filename}")
    
    return ffmpeg_request

def create_multi_video_ffmpeg_request(request: MultiVideoFFmpegRequest) -> FfmpegRequest:
    """
    Create FFmpeg request from multiple videos with their audio selections
    Videos will be concatenated in sequence with their respective background music
    """
    successful_videos = [v for v in request.video_results if v.success and v.sentiment_analysis]
    
    print(f"🎬 Creating multi-video FFmpeg request:")
    print(f"   📊 Total videos submitted: {len(request.video_results)}")
    print(f"   ✅ Successfully processed: {len(successful_videos)}")
    print(f"   🔊 Global volume: {request.global_volume:.1%}")
    print(f"   ⏭️ Transition duration: {request.video_transition_duration}s")
    
    input_segments = []
    current_time_offset = 0.0
    
    for video_idx, video_result in enumerate(request.video_results):
        if not video_result.success or not video_result.sentiment_analysis:
            print(f"⚠️ Skipping video {video_idx + 1}: '{video_result.filename}' (processing failed)")
            continue
        
        sentiment_data = video_result.sentiment_analysis.sentiment_analysis
        if not isinstance(sentiment_data, SentimentAnalysisData):
            print(f"⚠️ Skipping video {video_idx + 1}: '{video_result.filename}' (invalid sentiment data)")
            continue
        
        video_length = video_result.video_length or sentiment_data.video_length
        input_filename = os.path.basename(video_result.file_path)
        
        print(f"📹 Adding video {video_idx + 1}: '{video_result.filename}'")
        print(f"   📁 File: {input_filename}")
        print(f"   ⏱️ Duration: {video_length}s | Offset: {current_time_offset}s")
        print(f"   🎭 Title: '{sentiment_data.video_title}' | Mood: {sentiment_data.overall_mood}")
        
        # Add video segment with time offset
        video_segment = InputSegment(
            file_path=video_result.file_path,
            file_type="video",
            start_time=seconds_to_time_format(current_time_offset),
            end_time=seconds_to_time_format(current_time_offset + video_length),
            clip_start="00:00:00",
            clip_end=None,
            volume=1.0,
            fade_in=None,
            fade_out=None,
            metadata={
                "type": "video_segment",
                "video_index": video_idx,
                "original_filename": video_result.filename
            }
        )
        input_segments.append(video_segment)
        
        # Add audio segments for this video with time offset
        audio_count = 0
        if video_result.segments_with_audio:
            for audio_segment in video_result.segments_with_audio:
                if audio_segment.audio_selection:
                    audio_filename = os.path.basename(audio_segment.audio_selection.audio_file)
                    final_volume = audio_segment.audio_selection.volume * request.global_volume
                    
                    audio_input = InputSegment(
                        file_path=audio_segment.audio_selection.audio_file,
                        file_type="audio",
                        start_time=seconds_to_time_format(current_time_offset + audio_segment.start_time),
                        end_time=seconds_to_time_format(current_time_offset + audio_segment.end_time),
                        clip_start="00:00:00",
                        clip_end=None,
                        volume=final_volume,
                        fade_in=audio_segment.audio_selection.fade_in,
                        fade_out=audio_segment.audio_selection.fade_out,
                        metadata={
                            "type": "background_music",
                            "video_index": video_idx,
                            "segment_sentiment": audio_segment.sentiment,
                            "music_style": audio_segment.music_style,
                            "intensity": audio_segment.intensity
                        }
                    )
                    input_segments.append(audio_input)
                    audio_count += 1
        
        print(f"   🎵 Added {audio_count} audio segments for '{video_result.filename}'")
        
        # Update time offset for next video (add transition time)
        current_time_offset += video_length + float(request.video_transition_duration)
    
    # Create the aggregated FFmpeg request
    request_id = str(uuid.uuid4())
    output_filename = os.path.basename(request.output_video_path)
    
    ffmpeg_request = FfmpegRequest(
        input_segments=input_segments,
        output_file=request.output_video_path,
        video_codec=VideoCodec.H264,
        audio_codec=AudioCodec.AAC,
        video_bitrate=None,
        audio_bitrate=None,
        crf=23,
        preset="medium",
        scale=None,
        fps=None,
        audio_channels=2,
        audio_sample_rate=44100,
        global_volume=1.0,
        normalize_audio=True,
        crossfade_duration=request.crossfade_duration,
        gap_duration=request.video_transition_duration,
        overwrite=True,
        quiet=False,
        progress=True,
        request_id=request_id,
        priority=5
    )
    
    total_duration = current_time_offset - float(request.video_transition_duration)
    video_segments = [s for s in input_segments if s.file_type == "video"]
    audio_segments = [s for s in input_segments if s.file_type == "audio"]
    
    print(f"✅ Multi-video FFmpeg request created successfully!")
    print(f"   🆔 Request ID: {request_id[:8]}...")
    print(f"   📊 Total segments: {len(input_segments)} ({len(video_segments)} video + {len(audio_segments)} audio)")
    print(f"   🎬 Videos processed: {len(successful_videos)}")
    print(f"   ⏱️ Total duration: {total_duration:.1f}s")
    print(f"   ⚙️ Settings: {ffmpeg_request.video_codec.value}/{ffmpeg_request.audio_codec.value}, CRF={ffmpeg_request.crf}")
    print(f"   📁 Output: {output_filename}")
    
    return ffmpeg_request 