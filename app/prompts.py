def segment_video_prompt(num_segments: int, desired_duration: float) -> str:
    prompt = f"""
    You are a professional video editor. Your task is to split this video into the top {num_segments} most important segments, with a combined total duration as close as possible to {desired_duration} seconds, but not exceeding it.

    Instructions:
    - Each segment should be represented by a start and end time in seconds (with milliseconds).
    - The end time of the last segment must not exceed the video's total duration.
    - The sum of all segment durations (end - start for each) should be as close as possible to {desired_duration} seconds, but never exceed it.
    - Segments should not overlap and should be ordered chronologically.
    - Output strictly in the following JSON format (no extra text):

    [
        {{
            "start": "0.0",
            "end": "5.0"
        }},
        {{
            "start": "10.0",
            "end": "20.0"
        }}
    ]

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