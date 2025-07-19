"""
Audio selection logic for video sentiment analysis
"""
import os
import random
from typing import Optional, List, Dict
from models import (
    VideoSegment, AudioLibrary, AudioSelection, VideoSegmentWithAudio, 
    SentimentAnalysisData
)

def map_sentiment_to_filename(sentiment: str) -> str:
    """
    Map sentiment values from analysis to available music filenames
    """
    sentiment_lower = sentiment.lower()
    
    # Direct mappings for exact matches
    direct_mappings = {
        'happy': 'happy',
        'sad': 'sad', 
        'energetic': 'energetic',
        'calm': 'calm',
        'dramatic': 'dramatic',
        'romantic': 'romantic',
        'suspenseful': 'suspenseful'
    }
    
    # Check for direct match first
    if sentiment_lower in direct_mappings:
        return direct_mappings[sentiment_lower]
    
    # Fuzzy mappings for similar sentiments
    if any(word in sentiment_lower for word in ['tense', 'intense', 'anxious']):
        return 'suspenseful'
    elif any(word in sentiment_lower for word in ['exciting', 'upbeat', 'lively']):
        return 'energetic'
    elif any(word in sentiment_lower for word in ['peaceful', 'relaxed', 'soothing']):
        return 'calm'
    elif any(word in sentiment_lower for word in ['positive', 'joyful', 'cheerful']):
        return 'happy'
    elif any(word in sentiment_lower for word in ['negative', 'melancholy', 'depressing']):
        return 'sad'
    elif any(word in sentiment_lower for word in ['epic', 'cinematic', 'powerful']):
        return 'dramatic'
    elif any(word in sentiment_lower for word in ['love', 'tender', 'sweet']):
        return 'romantic'
    else:
        # Default fallback
        return 'calm'

def get_music_file_path(style: str, sentiment: str) -> Optional[str]:
    """
    Get the file path for a music track based on style and sentiment
    """
    # Normalize style name to match directory structure
    style_lower = style.lower()
    style_mappings = {
        'pop': 'pop',
        'hip hop': 'hiphop',
        'hiphop': 'hiphop', 
        'classical': 'classical',
        'electronic': 'pop',  # Fallback to pop for now
        'meme': 'pop'  # Fallback to pop for now
    }
    
    if style_lower in style_mappings:
        style_dir = style_mappings[style_lower]
    else:
        style_dir = 'pop'  # Default fallback
    
    # Map sentiment to filename
    filename = map_sentiment_to_filename(sentiment)
    
    # Construct file path (music directory is one level up from app)
    music_file_path = os.path.join('..', 'music', style_dir, f'{filename}.mp3')
    
    # Check if file exists
    if os.path.exists(music_file_path):
        return music_file_path
    else:
        print(f"⚠️ Music file not found: {music_file_path}")
        # Try fallback to pop directory
        fallback_path = os.path.join('..', 'music', 'pop', f'{filename}.mp3')
        if os.path.exists(fallback_path):
            print(f"   Using fallback: {fallback_path}")
            return fallback_path
        else:
            print(f"   Fallback also not found: {fallback_path}")
            return None

def create_audio_selection_from_track(track: Dict, global_volume: float = 0.3) -> Optional[AudioSelection]:
    """
    Create an AudioSelection from a track definition
    """
    style = track.get('style', 'Pop')
    sentiment = track.get('sentiment', 'calm')
    intensity = track.get('intensity', 'medium')
    
    # Get the music file path
    music_file_path = get_music_file_path(style, sentiment)
    if not music_file_path:
        print(f"❌ Could not find music file for style='{style}', sentiment='{sentiment}'")
        return None
    
    # Determine volume based on intensity
    intensity_lower = intensity.lower()
    if intensity_lower == 'high':
        volume = 0.5 * global_volume
        fade_duration = "0.2"
    elif intensity_lower == 'medium':
        volume = 0.3 * global_volume  
        fade_duration = "0.5"
    else:  # low
        volume = 0.2 * global_volume
        fade_duration = "1.0"
    
    print(f"    🎼 Selected: {os.path.basename(music_file_path)}")
    print(f"       Track: style='{style}' + sentiment='{sentiment}' + intensity='{intensity}'")
    print(f"       Settings: volume={volume:.3f}, fade={fade_duration}s")
    
    return AudioSelection(
        audio_file=music_file_path,
        volume=volume,
        fade_in=fade_duration,
        fade_out=fade_duration
    )

def pick_audio(sentiment_data: SentimentAnalysisData, audio_library: Optional[AudioLibrary] = None, global_volume: float = 0.3) -> List[VideoSegmentWithAudio]:
    """
    Pick audio tracks for video segments based on sentiment analysis with new schema
    Works with music.tracks format where each track defines style, sentiment, and timing
    """
    print(f"🎵 Starting audio selection for video: '{sentiment_data.video_title}'")
    print(f"📊 Video details: {sentiment_data.video_length}s duration | Overall mood: {sentiment_data.overall_mood}")
    
    segments_with_audio = []
    
    # Check if we have music tracks defined
    music_data = getattr(sentiment_data, 'music', None)
    if not music_data or not hasattr(music_data, 'tracks') or not music_data.tracks:
        print("❌ No music tracks found in sentiment data")
        return segments_with_audio
    
    tracks = music_data.tracks
    print(f"🎼 Found {len(tracks)} music track(s) to process")
    
    # Process each music track
    for i, track in enumerate(tracks):
        track_dict = track.dict() if hasattr(track, 'dict') else track
        
        start_time = track_dict.get('start', 0)
        end_time = track_dict.get('end', 60)
        style = track_dict.get('style', 'Pop')
        sentiment = track_dict.get('sentiment', 'calm')
        intensity = track_dict.get('intensity', 'medium')
        
        track_duration = end_time - start_time
        print(f"🎼 Processing track {i+1}/{len(tracks)}: '{sentiment}' ({style}, {intensity})")
        print(f"   ⏱️ Timing: {start_time}s - {end_time}s (duration: {track_duration:.1f}s)")
        
        # Create audio selection for this track
        audio_selection = create_audio_selection_from_track(track_dict, global_volume)
        
        if audio_selection:
            # Create a video segment with audio selection
            # Note: We're treating each track as a segment for compatibility with existing pipeline
            segment_with_audio = VideoSegmentWithAudio(
                start_time=start_time,
                end_time=end_time,
                sentiment=sentiment,
                music_style=style,
                intensity=intensity,
                audio_selection=audio_selection
            )
            
            segments_with_audio.append(segment_with_audio)
            
            selected_filename = os.path.basename(audio_selection.audio_file)
            print(f"   ✅ Assigned: {selected_filename} | Volume: {audio_selection.volume:.3f}")
        else:
            print(f"   ❌ Failed to create audio selection for track {i+1}")
    
    print(f"🎉 Audio selection complete for '{sentiment_data.video_title}'!")
    print(f"📈 Summary: {len(segments_with_audio)} tracks with background music selected")
    
    # Log summary by style and sentiment
    if segments_with_audio:
        print(f"🎵 Audio distribution:")
        for i, segment in enumerate(segments_with_audio):
            filename = os.path.basename(segment.audio_selection.audio_file)
            print(f"   Track {i+1}: {segment.music_style}/{segment.sentiment} -> {filename}")
    
    return segments_with_audio

if __name__ == "__main__":
    import json
    from models import SentimentAnalysisData
    
    print("🧪 Testing Audio Picker Logic")
    print("=" * 50)
    
    # Load test data from llm_answers directory
    test_file = "./llm_answers/20250719_142310_687b0d7d61acc75954400474.json"
    
    try:
        print(f"📂 Loading test data from: {test_file}")
        with open(test_file, 'r') as f:
            raw_data = json.load(f)
        
        print(f"✅ Successfully loaded JSON data")
        print(f"📹 Video: {raw_data.get('video_title', 'Unknown')}")
        print(f"⏱️ Length: {raw_data.get('video_length', 0)}s")
        print(f"🎭 Mood: {raw_data.get('overall_mood', 'Unknown')}")
        
        # Check if music tracks exist
        music_data = raw_data.get('music', {})
        tracks = music_data.get('tracks', [])
        print(f"🎵 Music tracks found: {len(tracks)}")
        
        if tracks:
            for i, track in enumerate(tracks):
                print(f"   Track {i+1}: {track.get('style', 'Unknown')} | {track.get('sentiment', 'Unknown')} | {track.get('intensity', 'Unknown')}")
                print(f"           Time: {track.get('start', 0)}s - {track.get('end', 0)}s")
        
        print("\n" + "=" * 50)
        print("🎼 Testing Audio Selection")
        print("=" * 50)
        
        # Convert to SentimentAnalysisData model
        # We need to handle this carefully since the model might expect specific structure
        
        # For now, let's test individual functions
        print("\n🧪 Testing individual functions:")
        
        # Test sentiment mapping
        test_sentiments = ['suspenseful', 'dramatic', 'tense', 'happy', 'calm']
        print(f"\n📊 Sentiment to filename mapping:")
        for sentiment in test_sentiments:
            filename = map_sentiment_to_filename(sentiment)
            print(f"   '{sentiment}' -> '{filename}.mp3'")
        
        # Test file path generation
        print(f"\n📁 File path generation:")
        for track in tracks:
            style = track.get('style', 'Pop')
            sentiment = track.get('sentiment', 'calm')
            file_path = get_music_file_path(style, sentiment)
            status = "✅ Found" if file_path else "❌ Not found"
            print(f"   {style}/{sentiment} -> {file_path} {status}")
        
        # Test audio selection creation
        print(f"\n🎵 Audio selection creation:")
        for i, track in enumerate(tracks):
            print(f"\n   Track {i+1}:")
            audio_selection = create_audio_selection_from_track(track, global_volume=0.3)
            if audio_selection:
                print(f"      ✅ Audio selection created successfully")
                print(f"      📁 File: {audio_selection.audio_file}")
                print(f"      🔊 Volume: {audio_selection.volume:.3f}")
                print(f"      ⏱️ Fade: {audio_selection.fade_in}s in, {audio_selection.fade_out}s out")
            else:
                print(f"      ❌ Failed to create audio selection")
        
        print(f"\n🎉 Audio picker testing completed!")
        
    except FileNotFoundError:
        print(f"❌ Test file not found: {test_file}")
        print("Available files in llm_answers:")
        import os
        try:
            files = os.listdir("../llm_answers/")
            for file in files:
                if file.endswith('.json'):
                    print(f"   - {file}")
        except:
            print("   Could not list files")
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()

