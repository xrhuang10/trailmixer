import os
import json
from typing import List, Dict, Optional

from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task

from prompts import segment_video_prompt

class TwelveLabsClient:
    def __init__(self, api_key, index):
        if not api_key:
            raise ValueError("API key is required")
        self.client = TwelveLabs(api_key=api_key)
        self.index = index

    def upload_video(self, file_path: str) -> str:
        task = self.client.task.create(
            index_id=self.index,
            file=file_path
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

    def prompt_segment(self, video_id: str, prompt: str) -> Optional[List[Dict[str, float]]]: 
        print(f'Prompting Twelve Labs with video ID: {video_id}')
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
    
# For testing
if __name__ == "__main__":
    load_dotenv()
    TWELVE_LABS_API_KEY = os.getenv("TWELVE_LABS_API_KEY")
    TWELVE_LABS_INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")
    if not TWELVE_LABS_API_KEY or not TWELVE_LABS_INDEX_ID:
        raise ValueError("TWELVE_LABS_API_KEY and TWELVE_LABS_INDEX_ID must be set")
    
    client = TwelveLabsClient(api_key=TWELVE_LABS_API_KEY, index=TWELVE_LABS_INDEX_ID)
    
    # client.upload_video("videos/speed.mp4")
    
    prompt = segment_video_prompt(num_segments=2)
    print(client.prompt_segment(video_id="6882c933fcecfb2100e4edb3", prompt=prompt))
    
