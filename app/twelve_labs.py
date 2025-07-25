import os
import json
from typing import List, Dict, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

from prompts import segment_video_prompt, sentiment_analysis_prompt
from paths import MUSIC_DIR, STITCHED_DIR

class TwelveLabsClient:
    def __init__(self, api_key, index):
        if not api_key:
            raise ValueError("API key is required")
        self.client = TwelveLabs(api_key=api_key)
        self.index = index

    def upload_video(self, video_path: Path) -> str:
        print(f'Uploading video to Twelve Labs: {video_path}')
        task = self.client.task.create(
            index_id=self.index,
            file=str(video_path)
        )
        print(f'Created Twelve Labs task: {task.id}')
        self.tick = 0
        def on_task_update(task: Task):
            print(f'T{self.tick}: Twelve Labs Task Status: {task.status}')
            self.tick += 1
        task.wait_for_done(callback=on_task_update)
        if task.status == "ready":
            print(f'Twelve Labs task completed: {task.video_id}')
            return task.video_id
        else:
            raise RuntimeError(f'Twelve Labs task failed: {task.status}')

    def prompt_segment(self, video_id: str, desired_duration: int, num_segments: int) -> Optional[List[Dict[str, float]]]: 
        print(f'Segmentation prompt Twelve Labs with video ID: {video_id}')
        prompt = segment_video_prompt(desired_duration=desired_duration, num_segments=num_segments)
        response = self.client.analyze(
            video_id=video_id,
            prompt=prompt
        )
        print(f'Prompting complete! Response received.')
        if not response.data:
            return None
        data = json.loads(response.data)
        
        # Convert all second values to float
        for segment in data:
            segment["start"] = float(segment["start"])
            segment["end"] = float(segment["end"])
            
        return data
    
    def prompt_sentiment(self, video_id: str, num_sentiments: int, music_style: str) -> Optional[List[Dict[str, float]]]: 
        print(f'Sentiment analysis prompt Twelve Labs with video ID: {video_id}')
        prompt = sentiment_analysis_prompt(num_sentiments=num_sentiments)
        response = self.client.analyze(
            video_id=video_id,
            prompt=prompt
        )
        print(f'Prompting complete! Response received.')
        if not response.data:
            return None
        data = json.loads(response.data)
        
        # Convert all second values to float and add song paths
        for segment in data:
            segment["start"] = float(segment["start"])
            segment["end"] = float(segment["end"])
            
            # Add song path based on music_style and sentiment
            sentiment = segment.get("sentiment", None)
            if sentiment is None:
                raise ValueError("Sentiment is required")
            segment["song_path"] = MUSIC_DIR / f"{music_style}/{sentiment}.mp3"
            
        return data
    
# For testing
if __name__ == "__main__":
    load_dotenv()
    TWELVE_LABS_API_KEY = os.getenv("TWELVE_LABS_API_KEY")
    TWELVE_LABS_INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")
    if not TWELVE_LABS_API_KEY or not TWELVE_LABS_INDEX_ID:
        raise ValueError("TWELVE_LABS_API_KEY and TWELVE_LABS_INDEX_ID must be set")
    
    client = TwelveLabsClient(api_key=TWELVE_LABS_API_KEY, index=TWELVE_LABS_INDEX_ID)
    
    # client.upload_video(STITCHED_DIR / "speed.mp4")
    
    # prompt = segment_video_prompt(num_segments=2)
    # prompt = sentiment_analysis_prompt(num_sentiments=2)
    print(client.prompt_segment(video_id="6883e11cb59be315a5bcff45", desired_duration=30, num_segments=5))
    
