import json

# with open("app/prompts/twelvelabs_output_schema.json", "r") as f:
#     twelvelabs_output_schema = json.load(f)

twelvelabs_output_schema = {
    "video_id": {
        "type": "string",
        "description": "The ID of the video"
    },
    "video_title": {
        "type": "string",
        "description": "The title of the video"
    },
    "video_description": {
        "type": "string",
        "description": "The description of the video"
    },
    "video_length": {
        "type": "number",
        "description": "The length of the video in seconds"
    },
    "overall_mood": {
        "type": "string",
        "description": "The overall mood of the video (e.g., happy, sad, energetic, calm, dramatic, romantic, suspenseful)"
    },
    "segments": {
        "type": "array",
        "description": "Array of video segments with their mood and timing information",
        "items": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "number",
                    "description": "Start time of the segment in seconds"
                },
                "end_time": {
                    "type": "number", 
                    "description": "End time of the segment in seconds"
                },
                "sentiment": {
                    "type": "string",
                    "description": "The sentiment/mood of this segment (e.g., positive, negative, neutral, exciting, tense, peaceful)"
                },
                "music_style": {
                    "type": "string",
                    "description": "Recommended music style/genre for this segment (e.g., upbeat, ambient, cinematic, acoustic, electronic)"
                },
                "intensity": {
                    "type": "string",
                    "description": "Intensity level of the segment (low, medium, high)"
                }
            },
            "required": ["start_time", "end_time", "sentiment", "music_style", "intensity"]
        }
    }
}

desired_length = 60  # in seconds
music_style = "Pop"  # One of: Classical, Hip Hop, Pop, Electronic, Meme
music_intensity = "medium"  # Can also make this a variable if needed
num_tracks = 1
sentiment_list = ["happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful"]

# Track format
song_format = {
    "music": {
        "tracks": [
            {
                "start": 0,
                "end": desired_length,
                "style": music_style,
                "intensity": music_intensity,
            }
        ]
    }
}

# Inject music track schema into the output schema template
twelvelabs_output_schema.update(song_format)

extract_info_prompt = f"""
You are a professional video analyst that extracts information from videos for automated music mixing and editing.

You will be given a video and must:
1. Analyze and break it into logical segments (based on mood, content, or scene/highlight changes).
2. Select the most important segments to KEEP (to crop the video down to a final length of {desired_length} seconds, give or take a few seconds`).
3. Propose {num_tracks} suitable music track(s) based on the mood and pacing of the selected segments.

Each segment should include:
- Start time (in seconds)
- End time (in seconds)
- Sentiment/mood
- Music style, which should strictly be {music_style}
- Intensity level (low, medium, high)
- "include": true or false (true = included in cropped final)

**Music Track Guidelines:**
- Propose ONE track that fits the overall mood and intensity of the selected segments.
- Use this format:
  "music": {{
      "tracks": [
          {{
              "start": 0,
              "end": {desired_length},
              "style": "{music_style}",
              "intensity": "{music_intensity}"
              "sentiment": The single overall sentiment of the track, which should strictly be a single word from the following list: {sentiment_list}
          }}
      ]
  }}
- Ensure this matches the dominant mood/intensity from included segments.

**General Instructions:**
- Total time of all segments must NOT exceed {desired_length} seconds.
- Only select the most meaningful scenes (e.g., high emotion, action, climax).
- All timestamps must be in seconds as numbers (e.g., 32.5)
- No overlapping or skipped time in selected segments.
- Do not include the full video unless it’s shorter than {desired_length} seconds.

**Also provide:**
- Full original length
- Desired final length (which is {desired_length} seconds)
- Overall sentiment of the full video

**VERY IMPORTANT:**
- VERY VERY IMPORTANT: The total duration of all segments where `"include": true` MUST NOT exceed {desired_length} seconds.
- Only select the most meaningful scenes for inclusion.
- Segments without "include": true will be ignored for the final cropped video and music generation.
- For each track, the sentiment should be the single overall sentiment of the track, which should be a single word strictly from the following list: {sentiment_list}

Return ONLY the JSON response following this exact format:
{json.dumps(twelvelabs_output_schema, indent=4)}
"""
