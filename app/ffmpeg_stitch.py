import ffmpeg  # type: ignore
from models import FfmpegRequest, InputSegment
from typing import List, Tuple, Optional
import os

def _time_to_seconds(time_str: str) -> float:
    """Convert time string (HH:MM:SS or HH:MM:SS.mmm) to seconds."""
    if not time_str:
        return 0.0
    
    parts = time_str.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    else:
        return float(time_str)

def build_input_stream(segment: InputSegment, index: int):
    """Builds the input stream with filters applied based on segment options."""
    input_kwargs = {}

    # Handle clip selection from input file
    clip_start_seconds = _time_to_seconds(segment.clip_start or "00:00:00")
    
    # Calculate end time based on segment type and timing
    if segment.file_type == 'audio':
        # For audio, use the segment end_time if clip_end is not specified
        clip_end_seconds = _time_to_seconds(segment.clip_end or segment.end_time or "00:01:00")
    else:
        # For video, use end_time if clip_end is not specified
        clip_end_seconds = _time_to_seconds(segment.clip_end or segment.end_time or "00:01:00")
    
    clip_duration = clip_end_seconds - clip_start_seconds

    if segment.clip_start:
        input_kwargs['ss'] = segment.clip_start
    if segment.clip_end:
        input_kwargs['t'] = str(clip_duration)

    # Create base input stream
    base_stream = ffmpeg.input(segment.file_path, **input_kwargs)
    
    # Initialize stream as None
    stream = None
    
    # Create stream based on type
    if segment.file_type == 'audio':
        stream = base_stream.audio
        # Apply audio filters
        if segment.volume and segment.volume != 1.0:
            stream = ffmpeg.filter(stream, 'volume', segment.volume)
        if segment.fade_in:
            stream = ffmpeg.filter(stream, 'afade', t='in', st=0, d=segment.fade_in)
        if segment.fade_out:
            # Calculate fade out start time based on actual segment duration
            fade_out_seconds = float(segment.fade_out)
            segment_duration = _time_to_seconds(segment.end_time) - _time_to_seconds(segment.start_time)
            fade_start = max(0, segment_duration - fade_out_seconds)
            stream = ffmpeg.filter(stream, 'afade', t='out', st=fade_start, d=segment.fade_out)
        
        # Handle placement timing
        start_seconds = _time_to_seconds(segment.start_time)
        if start_seconds > 0:
            # Add silence before the audio to place it at the right time
            stream = ffmpeg.filter(stream, 'adelay', f'{int(start_seconds * 1000)}|{int(start_seconds * 1000)}')

    elif segment.file_type == 'video':
        stream = base_stream.video
        # Apply video filters
        if segment.fade_in:
            stream = ffmpeg.filter(stream, 'fade', t='in', st=0, d=segment.fade_in)
        if segment.fade_out:
            # Calculate fade out start time based on actual segment duration
            fade_out_seconds = float(segment.fade_out)
            segment_duration = _time_to_seconds(segment.end_time) - _time_to_seconds(segment.start_time)
            fade_start = max(0, segment_duration - fade_out_seconds)
            stream = ffmpeg.filter(stream, 'fade', t='out', st=fade_start, d=segment.fade_out)
    
    # Handle invalid file type
    if stream is None:
        raise ValueError(f"Invalid file type: {segment.file_type}. Must be 'audio' or 'video'.")
        
    return stream

def stitch_ffmpeg_request(request: FfmpegRequest) -> str:
    """Stitch multiple video and audio segments together using FFmpeg."""
    print(f"InputSegments: {request.input_segments}")
    audio_streams = []
    video_streams = []

    # Build input streams
    for i, segment in enumerate(request.input_segments):
        stream = build_input_stream(segment, i)
        if segment.file_type == 'audio':
            audio_streams.append(stream)
        elif segment.file_type == 'video':
            # For video type, handle both video and audio streams
            video_streams.append(stream)
            if segment.volume and segment.volume > 0:  # Only add audio if volume > 0
                # Get audio stream from the same input
                audio_kwargs = {}
                if segment.clip_start:
                    audio_kwargs['ss'] = segment.clip_start
                if segment.clip_end:
                    clip_start_seconds = _time_to_seconds(segment.clip_start or "00:00:00")
                    clip_end_seconds = _time_to_seconds(segment.clip_end)
                    audio_kwargs['t'] = str(clip_end_seconds - clip_start_seconds)
                
                audio_stream = ffmpeg.input(segment.file_path, **audio_kwargs).audio
                if segment.volume != 1.0:
                    audio_stream = ffmpeg.filter(audio_stream, 'volume', segment.volume)
                audio_streams.append(audio_stream)

    # Process audio streams
    final_audio = None
    if audio_streams:
        # Process each audio stream with its own filters first
        processed_streams = []
        for i, stream in enumerate(audio_streams):
            segment = request.input_segments[i]
            if segment.file_type == 'audio':  # Only process background music streams
                # Apply volume
                if segment.volume and segment.volume != 1.0:
                    stream = ffmpeg.filter(stream, 'volume', segment.volume)
                
                # Apply fades if specified
                if segment.fade_in:
                    stream = ffmpeg.filter(stream, 'afade', t='in', st=0, d=segment.fade_in)
                if segment.fade_out:
                    fade_start = _time_to_seconds(segment.end_time) - _time_to_seconds(segment.start_time) - float(segment.fade_out)
                    stream = ffmpeg.filter(stream, 'afade', t='out', st=fade_start, d=segment.fade_out)
                
                # Add silence padding if needed
                start_seconds = _time_to_seconds(segment.start_time)
                if start_seconds > 0:
                    stream = ffmpeg.filter(stream, 'adelay', f'{int(start_seconds * 1000)}|{int(start_seconds * 1000)}')
            
            processed_streams.append(stream)

        if len(processed_streams) > 1:
            # Mix all audio streams together
            final_audio = ffmpeg.filter(processed_streams, 'amix', inputs=len(processed_streams), duration='longest')
        else:
            final_audio = processed_streams[0]

        # Apply global audio settings
        if request.global_volume and request.global_volume != 1.0:
            final_audio = ffmpeg.filter(final_audio, 'volume', request.global_volume)

        if request.normalize_audio:
            final_audio = ffmpeg.filter(final_audio, 'dynaudnorm')

    # Process video streams
    final_video = None
    if video_streams:
        if len(video_streams) > 1:
            # For multiple videos, we'll use a simpler approach
            # Note: In a real implementation, you might want to use filter_complex
            # For now, we'll take the first video and apply filters
            final_video = video_streams[0]
            # TODO: Implement proper video concatenation using filter_complex
        else:
            final_video = video_streams[0]

        # Apply video filters
        if request.scale:
            # Parse width and height from scale parameter
            width, height = request.scale.split(':')
            final_video = ffmpeg.filter(final_video, 'scale', width=width, height=height)
        if request.fps:
            final_video = ffmpeg.filter(final_video, 'fps', fps=request.fps)

    # Build output options
    output_kwargs = {
        'vcodec': request.video_codec,
        'acodec': request.audio_codec.value if hasattr(request.audio_codec, 'value') else request.audio_codec,
        'preset': request.preset
    }

    if request.crf is not None:
        output_kwargs['crf'] = request.crf
    if request.video_bitrate:
        output_kwargs['b:v'] = request.video_bitrate
    if request.audio_bitrate:
        output_kwargs['b:a'] = request.audio_bitrate
    if request.audio_channels:
        output_kwargs['ac'] = request.audio_channels
    if request.audio_sample_rate:
        output_kwargs['ar'] = request.audio_sample_rate

    # Create output stream based on what streams we have
    if final_video and final_audio:
        # Combined video and audio
        output = ffmpeg.output(final_video, final_audio, request.output_file, **output_kwargs)
    elif final_video:
        # Video only
        output_kwargs['an'] = None  # Disable audio
        output = ffmpeg.output(final_video, request.output_file, **output_kwargs)
    elif final_audio:
        # Audio only
        output_kwargs['vn'] = None  # Disable video
        output = ffmpeg.output(final_audio, request.output_file, **output_kwargs)
    else:
        raise RuntimeError("No input streams available")

    if request.overwrite:
        output = output.overwrite_output()

    # Always show FFmpeg output during testing/debugging
    output = output.global_args('-v', 'info')

    try:
        # Get the FFmpeg command for debugging
        cmd = ffmpeg.get_args(output)
        print(f"FFmpeg command: {' '.join(cmd)}")
        
        # Run the command
        stdout, stderr = output.run(capture_stdout=True, capture_stderr=True)
        return request.output_file
        
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else "No error output"
        stdout_msg = e.stdout.decode() if e.stdout else "No stdout output"
        cmd = ' '.join(ffmpeg.get_args(output))
        raise RuntimeError(f"FFmpeg failed:\nCommand: {cmd}\nSTDERR:\n{error_msg}\nSTDOUT:\n{stdout_msg}") 