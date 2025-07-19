"""
Audio selection logic for video sentiment analysis
"""
from fileinput import filename
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

def get_music_file_paths(analysis_file_path: str) -> list[str]:
    with open(analysis_file_path, 'r') as f:
        analysis_data = json.load(f)
    tracks = analysis_data.get('music', {}).get('tracks', [])
    
    music_file_paths = []
    for track in tracks:
        style = track['style']
        sentiment = track['sentiment']
        filename = os.path.join('..', 'music', style, f'{sentiment}.mp3')
        music_file_paths.append(filename)
        
    return music_file_paths

if __name__ == "__main__":
    import json
    from models import SentimentAnalysisData
    
    print("🧪 Testing Audio Picker Logic")
    print("=" * 50)
    
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