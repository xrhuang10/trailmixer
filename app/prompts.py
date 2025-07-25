def segment_video_prompt(num_segments: int) -> str:
    prompt = f"""
    You are a professional video editor. Your task is to take this video, and split it strictly into the top {num_segments} most important parts. 
    Essentially you are going to be creating a list of timestamps for each segment. Output the timestamps strictly in a JSON format.
    The JSON should be in the following exampleformat:
    [
        {{
            "start": "0",
            "end": "5"
        }},
        {{
            "start": "10",
            "end": "20"
        }}
    ]
    The start and end should be in seconds.
    Do not include any other text in your response.
    """
    
    return prompt