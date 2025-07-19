"""
Audio selection logic for video sentiment analysis
"""
import os
import random
from typing import Optional, List
from models import (
    VideoSegment, AudioLibrary, AudioSelection, VideoSegmentWithAudio, 
    SentimentAnalysisData
)

def select_audio_for_segment(segment: VideoSegment, audio_library: AudioLibrary) -> AudioSelection:
    """Select appropriate audio file based on segment sentiment and music style"""
    
    # Map sentiment to audio categories
    sentiment_lower = segment.sentiment.lower()
    music_style_lower = segment.music_style.lower()
    intensity_lower = segment.intensity.lower()
    
    # Determine audio files based on sentiment and style
    if any(word in sentiment_lower for word in ['positive', 'happy', 'joy', 'excited']):
        audio_files = audio_library.happy_files
        category = "happy"
    elif any(word in sentiment_lower for word in ['negative', 'sad', 'melancholy', 'tragic']):
        audio_files = audio_library.sad_files
        category = "sad"
    elif any(word in music_style_lower for word in ['energetic', 'upbeat', 'electronic', 'rock']):
        audio_files = audio_library.energetic_files
        category = "energetic"
    elif any(word in music_style_lower for word in ['calm', 'ambient', 'acoustic', 'peaceful']):
        audio_files = audio_library.calm_files
        category = "calm"
    else:
        audio_files = audio_library.neutral_files
        category = "neutral"
    
    # Select a random file from the appropriate category
    selected_file = random.choice(audio_files)
    
    # Determine volume based on intensity
    if intensity_lower == 'high':
        volume = 0.5
        fade_duration = "0.2"
    elif intensity_lower == 'medium':
        volume = 0.3
        fade_duration = "0.5"
    else:  # low
        volume = 0.2
        fade_duration = "1.0"
    
    # Log the selection reasoning
    selected_filename = os.path.basename(selected_file)
    print(f"    🎼 Selected '{selected_filename}' from {category} category")
    print(f"       Reasoning: sentiment='{segment.sentiment}' + style='{segment.music_style}' + intensity='{segment.intensity}'")
    print(f"       Settings: volume={volume:.2f}, fade={fade_duration}s")
    
    return AudioSelection(
        audio_file=selected_file,
        volume=volume,
        fade_in=fade_duration,
        fade_out=fade_duration
    )

def pick_audio(sentiment_data: SentimentAnalysisData, audio_library: Optional[AudioLibrary] = None) -> List[VideoSegmentWithAudio]:
    """
    Pick audio tracks for video segments based on sentiment analysis
    Returns segments with audio selections attached
    """
    print(f"🎵 Starting audio selection for video: '{sentiment_data.video_title}'")
    print(f"📊 Video details: {sentiment_data.video_length}s duration | {len(sentiment_data.segments)} segments | Overall mood: {sentiment_data.overall_mood}")
    
    # Use default audio library if none provided
    if audio_library is None:
        audio_library = AudioLibrary()
    
    segments_with_audio = []
    
    # Process each sentiment-based segment and select appropriate audio
    for i, segment in enumerate(sentiment_data.segments):
        segment_duration = segment.end_time - segment.start_time
        print(f"🎼 Processing segment {i+1}/{len(sentiment_data.segments)}: '{segment.sentiment}' ({segment.music_style}, {segment.intensity})")
        print(f"   ⏱️ Timing: {segment.start_time}s - {segment.end_time}s (duration: {segment_duration:.1f}s)")
        
        # Select audio for this segment
        audio_selection = select_audio_for_segment(segment, audio_library)
        
        # Create enhanced segment with audio selection
        segment_with_audio = VideoSegmentWithAudio(
            start_time=segment.start_time,
            end_time=segment.end_time,
            sentiment=segment.sentiment,
            music_style=segment.music_style,
            intensity=segment.intensity,
            audio_selection=audio_selection
        )
        
        segments_with_audio.append(segment_with_audio)
        
        selected_filename = os.path.basename(audio_selection.audio_file)
        print(f"   ✅ Assigned: {selected_filename} | Volume: {audio_selection.volume:.2f}")
    
    print(f"🎉 Audio selection complete for '{sentiment_data.video_title}'!")
    print(f"📈 Summary: {len(segments_with_audio)} segments with background music selected")
    
    # Log summary by audio category
    audio_categories = {}
    for segment in segments_with_audio:
        if segment.audio_selection:
            filename = os.path.basename(segment.audio_selection.audio_file)
            sentiment = segment.sentiment
            if sentiment not in audio_categories:
                audio_categories[sentiment] = []
            audio_categories[sentiment].append(filename)
    
    print(f"🎵 Audio distribution:")
    for sentiment, files in audio_categories.items():
        unique_files = list(set(files))
        print(f"   {sentiment}: {len(files)} segments using {len(unique_files)} unique track(s)")
    
    return segments_with_audio 