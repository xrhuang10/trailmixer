output = {
  "video_id": "hack_the_6ix",
  "video_title": "Hackathon Event Highlights",
  "video_description": "A compilation of various activities at a hackathon event.",
  "video_length": 145,
  "overall_mood": "energetic",
  "segments": [
    {
      "start_time": 0,
      "end_time": 7,
      "sentiment": "exciting",
      "music_style": "Pop",
      "intensity": "high",
      "include": True
    },
    {
      "start_time": 11,
      "end_time": 18,
      "sentiment": "calm",
      "music_style": "Pop",
      "intensity": "medium",
      "include": True
    },
    {
      "start_time": 34,
      "end_time": 40,
      "sentiment": "energetic",
      "music_style": "Pop",
      "intensity": "high",
      "include": True
    },
    {
      "start_time": 58,
      "end_time": 69,
      "sentiment": "fun",
      "music_style": "Pop",
      "intensity": "medium",
      "include": True
    },
    {
      "start_time": 105,
      "end_time": 119,
      "sentiment": "happy",
      "music_style": "Pop",
      "intensity": "low",
      "include": True
    },
    {
      "start_time": 123,
      "end_time": 138,
      "sentiment": "sad",
      "music_style": "Pop",
      "intensity": "low",
      "include": True
    }
  ],
  "music": {
    "tracks": [
      {
        "start": 0,
        "end": 17,
        "style": "Pop",
        "intensity": "high",
        "sentiment": "exciting"
      },
      {
        "start": 17,
        "end": 38,
        "style": "Pop",
        "intensity": "medium",
        "sentiment": "calm"
      },
      {
        "start": 38,
        "end": 60,
        "style": "Pop",
        "intensity": "high",
        "sentiment": "energetic"
      }
    ]
  }
}


one_shot_example = f"""
Example:
You are given a video with a length of 145 seconds and a desired trailer length of 60 seconds.
Your answer can follow this format:
{output}
because the sum of all the segment durations == the sum of all the track durations == the user's desired length of 60 seconds.

"""