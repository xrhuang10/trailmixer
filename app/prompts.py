def segment_video_prompt(num_segments: int, desired_duration: int) -> str:
    prompt = f"""
    You are a professional video editor. Your task is to take this video, and split it strictly into the top {num_segments} most important parts. 
    The desired duration of each segment is {desired_duration} seconds.
    Essentially you are going to be creating a list of timestamps for each segment. Output the timestamps strictly in a JSON format.
    The JSON should be in the following exampleformat:
    [
        {{
            "start": "0.0",
            "end": "5.0"
        }},
        {{
            "start": "10.0",
            "end": "20"
        }}
    ]
    The start and end should be in seconds with milliseconds.
    Do not include any other text in your response.
    """
    
    return prompt

def sentiment_analysis_prompt(num_sentiments: int) -> str:
    sentiments = [
        "calm",
        "dramatic",
        "energetic",
        "happy",
        "romantic",
        "sad",
        "suspenseful"
    ]
    
    prompt = f"""
    You are a professional video editor. Your task is to take this video, and analyze the sentiment of the video.
    Divide the video into {num_sentiments} consecutive segments and analyze the sentiment of each segment.
    
    Each sentiment string should be one of the following:
    {sentiments}
    
    Output the sentiment of each segment in a JSON format.
    The JSON should be in the following exampleformat:
    [
        {{
            "start": "0.0",
            "end": "5.0",
            "sentiment": One of the following: {sentiments}
        }},
        {{
            "start": "5.0",
            "end": "10.0",
            "sentiment": One of the following: {sentiments}
        }}
    ]
    The start and end should be in seconds with milliseconds.
    Do not include any other text in your response.
    """
    
    return prompt