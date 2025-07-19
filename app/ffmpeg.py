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

    # Calculate duration from start_time and end_time
    start_seconds = _time_to_seconds(segment.start_time)
    end_seconds = _time_to_seconds(segment.end_time)
    duration = end_seconds - start_seconds

    if segment.start_time:
        input_kwargs['ss'] = segment.start_time
    if duration > 0:
        input_kwargs['t'] = str(duration)

    stream = ffmpeg.input(segment.file_path, **input_kwargs)

    if segment.file_type == 'audio':
        # Apply audio filters
        if segment.volume and segment.volume != 1.0:
            stream = stream.audio.filter('volume', segment.volume)
        if segment.fade_in:
            stream = stream.audio.filter('afade', t='in', st=0, d=segment.fade_in)
        if segment.fade_out:
            # Calculate fade out start time based on duration
            fade_out_seconds = _time_to_seconds(segment.fade_out)
            fade_start = duration - fade_out_seconds
            stream = stream.audio.filter('afade', t='out', st=fade_start, d=segment.fade_out)

    elif segment.file_type == 'video':
        # Apply video filters
        if segment.fade_in:
            stream = stream.video.filter('fade', t='in', st=0, d=segment.fade_in)
        if segment.fade_out:
            # Calculate fade out start time based on duration
            fade_out_seconds = _time_to_seconds(segment.fade_out)
            fade_start = duration - fade_out_seconds
            stream = stream.video.filter('fade', t='out', st=fade_start, d=segment.fade_out)

    return stream

def stitch_ffmpeg_request(request: FfmpegRequest) -> str:
    """Stitch multiple video and audio segments together using FFmpeg."""
    audio_streams = []
    video_streams = []

    # Build input streams
    for i, segment in enumerate(request.input_segments):
        stream = build_input_stream(segment, i)
        if segment.file_type == 'audio':
            audio_streams.append(stream.audio)
        elif segment.file_type == 'video':
            video_streams.append(stream.video)

    # Process audio streams
    final_audio = None
    if audio_streams:
        if len(audio_streams) > 1:
            # Mix multiple audio streams
            final_audio = audio_streams[0]
            for audio in audio_streams[1:]:
                final_audio = ffmpeg.filter([final_audio, audio], 'amix', inputs=2, duration='shortest')
        else:
            final_audio = audio_streams[0]

        # Apply global audio settings
        if request.global_volume and request.global_volume != 1.0:
            final_audio = final_audio.filter('volume', request.global_volume)

        if request.normalize_audio:
            final_audio = final_audio.filter('dynaudnorm')

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
            final_video = final_video.filter('scale', request.scale)
        if request.fps:
            final_video = final_video.filter('fps', fps=request.fps)

    # Build output options
    output_kwargs = {
        'vcodec': request.video_codec,
        'acodec': request.audio_codec,
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
    if request.quiet:
        output_kwargs['loglevel'] = 'quiet'

    # Create output stream
    output = ffmpeg.output(
        final_video if final_video else None,
        final_audio if final_audio else None,
        request.output_file,
        **output_kwargs
    )

    if request.overwrite:
        output = output.overwrite_output()

    if request.progress:
        output = output.global_args('-progress', 'pipe:1')

    # Run the command
    try:
        output.run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg failed: {error_msg}")

    return request.output_file
