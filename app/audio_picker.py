"""
Audio selection logic for video sentiment analysis
"""
import os
import json
from typing import Any

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

def get_music_file_paths(analysis_file_path: str) -> dict[str, dict[str, Any]]:
    with open(analysis_file_path, 'r') as f:
        analysis_data = json.load(f)
    
    print(f"🔍 DEBUG: get_music_file_paths analysis_data")
    print(f"   Analysis data type: {type(analysis_data)}")
    print(f"   Analysis data content: {analysis_data}")
    
    # Handle different data structures
    tracks = []
    if isinstance(analysis_data, dict):
        # Check if music key exists and what it contains
        music_data = analysis_data.get('music', {})
        print(f"   Music data type: {type(music_data)}")
        print(f"   Music data content: {music_data}")
        
        if isinstance(music_data, list):
            # Music data is directly a list of tracks
            tracks = music_data
            print(f"   Found tracks as direct list: {len(tracks)}")
        elif isinstance(music_data, dict):
            # Music data is a dict with 'tracks' key
            tracks = music_data.get('tracks', [])
            print(f"   Found tracks in dict structure: {len(tracks)}")
        else:
            print(f"   ⚠️ Unknown music data type: {type(music_data)}")
            tracks = []
    elif isinstance(analysis_data, list):
        # Handle case where analysis_data is a list (possibly segments)
        print("⚠️ Analysis data is a list - checking if it contains tracks")
        # Look for any music/track info in the list
        for item in analysis_data:
            if isinstance(item, dict) and 'music' in item:
                tracks.extend(item.get('music', {}).get('tracks', []))
            elif isinstance(item, dict) and any(key in item for key in ['style', 'sentiment', 'start', 'end']):
                # This looks like a track itself
                tracks.append(item)
        print(f"   Extracted tracks from list structure: {len(tracks)}")
    else:
        print(f"⚠️ Unknown analysis_data type: {type(analysis_data)}")
        tracks = []
    
    music_file_paths = {}
    print(f"🎵 Processing {len(tracks)} tracks for music file paths")
    
    for i, track in enumerate(tracks):
        try:
            print(f"   Track {i} type: {type(track)}")
            print(f"   Track {i} content: {track}")
            
            # Handle different track data types
            if isinstance(track, dict):
                track_dict = {}
                
                # Extract with defaults for missing fields
                track_dict['style'] = track.get('style', 'Pop')
                track_dict['sentiment'] = track.get('sentiment', 'calm')
                track_dict['intensity'] = track.get('intensity', 'medium')
                track_dict['start'] = track.get('start', i * 20)
                track_dict['end'] = track.get('end', (i + 1) * 20)
                
                # Create filename with fallback values
                style = track_dict['style'].lower()
                sentiment = track_dict['sentiment'].lower()
                filename = os.path.join('..', 'music', style, f'{sentiment}.mp3')
                music_file_paths[filename] = track_dict
                
                print(f"   ✅ Added track {i}: {filename} ({track_dict['start']}s - {track_dict['end']}s)")
                
            elif isinstance(track, list):
                print(f"   ⚠️ Track {i} is a list, skipping: {track}")
                continue
            else:
                print(f"   ⚠️ Unknown track type {type(track)}, creating default")
                # Create default track
                track_dict = {
                    'style': 'Pop',
                    'sentiment': 'calm',
                    'intensity': 'medium',
                    'start': i * 20,
                    'end': (i + 1) * 20
                }
                filename = os.path.join('..', 'music', 'pop', 'calm.mp3')
                music_file_paths[filename] = track_dict
                print(f"   🔄 Created default track {i}: {filename}")
                
        except Exception as track_error:
            print(f"   ❌ Error processing track {i}: {track_error}")
            # Create fallback track to prevent total failure
            track_dict = {
                'style': 'Pop',
                'sentiment': 'calm',
                'intensity': 'medium',
                'start': i * 20,
                'end': (i + 1) * 20
            }
            filename = os.path.join('..', 'music', 'pop', 'calm.mp3')
            music_file_paths[filename] = track_dict
            print(f"   🔄 Created fallback track {i}: {filename}")
    
    print(f"✅ Generated {len(music_file_paths)} music file paths")
        
    return music_file_paths

if __name__ == "__main__":
    import json
    from models import SentimentAnalysisData
    
    # Load test data from llm_answers directory
    test_file = "./llm_answers/20250719_142310_687b0d7d61acc75954400474.json"
    
    print(get_music_file_paths(test_file))
    
    # INSERT_YOUR_CODE
    import os

    file_paths = get_music_file_paths(test_file)
    all_exist = True
    for path in file_paths:
        if not os.path.isfile(path):
            print(f"❌ File does not exist: {path}")
            all_exist = False
        else:
            print(f"✅ File exists: {path}")
    if all_exist:
        print("All music file paths are valid.")
    else:
        print("Some music file paths are invalid.")