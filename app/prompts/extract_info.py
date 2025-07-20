import json

# with open("app/prompts/twelvelabs_output_schema.json", "r") as f:
#     twelvelabs_output_schema = json.load(f)

output_example = {
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
{output_example}
because the sum of all the segment durations == the sum of all the track durations == the user's desired length of 60 seconds.

"""

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
                    "description": "One of: 'happy', 'sad', 'energetic', 'calm', 'dramatic', 'romantic', 'suspenseful'"
                },
                "music_style": {
                    "type": "string",
                    "description": "One of: 'Classical', 'Hip Hop', 'Pop', 'Electronic', 'Meme'"
                }
            },
            "required": ["start_time", "end_time", "sentiment", "music_style", "intensity"]
        }
    },
    "music": {
        "type": "array",
        "description": "Array of music tracks", 
        "items": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "number",
                    "description": "Start time of the track in seconds"
                },
                "end": {
                    "type": "number",
                    "description": "End time of the track in seconds"
                },
                "style": {
                    "type": "string",
                    "description": "One of: 'Classical', 'Hip Hop', 'Pop', 'Electronic', 'Meme'"
                },
                "sentiment": {
                    "type": "string",
                    "description": "One of: 'happy', 'sad', 'energetic', 'calm', 'dramatic', 'romantic', 'suspenseful'"
                }
            },
            "required": ["start", "end", "style", "sentiment"]
        }
    }
}
 

desired_length = 30  # in seconds
music_style = "Pop"  # One of: Classical, Hip Hop, Pop, Electronic, Meme
num_tracks = 3
sentiment_list = ["happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful"]

# # Track format
# song_format = {
#     "music": {
#         "tracks": [
#             {
#                 "start": 0,
#                 "end": desired_length,
#                 "style": music_style,
#                 "intensity": music_intensity,
#             }
#         ]
#     }
# }

# # Inject music track schema into the output schema template
# twelvelabs_output_schema.update(song_format)

# extract_info_prompt_old = f"""
# You are a professional video analyst that extracts information from videos for automated music mixing and editing.
# The hard cut off length is {desired_length} seconds.
# You are not providing specific audio analysis, rather I am asking you to provide a general music suggestion (only the style and sentiment).

# Given a video and the desired Trailers  length, you must
# 1. Analyze and break video into logical segments based on mood, content, or scene/highlight changes.
# 2. Select the most important segments to KEEP, such that the total cropped duration must be equal to the trailer length of {desired_length} seconds. Note that the individual segment and tracks may vary in duration, but MUST be {desired_length} seconds
# 3. When segments total time is greater than the desired trailer length, reject the least important segments until the total duration is drops below {desired_length} seconds.
# 4. Propose {num_tracks} suitable music track(s) based on the mood and pacing of the selected segments.

# Each segment must include:
# - "start_time": (number, in seconds)
# - "end_time": (number, in seconds)
# - "sentiment": the mood of the segment
# - "music_style": strictly "{music_style}"
# - "include": true or false (true if segment is included in the cropped final trailer)

# The end_time - start_time of each segment is the segment's duration. All segment durations added together must be less than the desired trailer length of {desired_length} seconds. Note that the individual segment and individual track durations may vary in duration, as long as their sums add up.

# ---


# **Constraints for Music Tracks:**
# - The number of tracks must be exactly {num_tracks}.
# - The total duration of the audio tracks combined MUST equal the total duration of `"include": true` segments.
# - Track time ranges must not overlap.
# - All timestamps must be numeric values in seconds.
# - This duration of all tracks combined must NOT exceed the MAX trailer length of {desired_length} seconds.
# - Each track must use a **unique combination** of `style` and `sentiment`.
# - Track sentiment must be a single word strictly from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful".

# ---

# **General Rules:**
# - Avoid including segments smaller than 2 seconds. Remove them if they are less than 2 seconds to make more time for the other smaller segments.
# - Segments must not overlap or leave gaps between included portions.
# - Use the most emotionally or narratively meaningful scenes, BUT ABOVE ALL, make sure the total sum of durations of all the segments equals the user's desired trailer length of {desired_length} seconds.
# - Prioritize time over meaningfulness. This means you can drop some segments or add some segments, even if they are not meaningful, as long as doing so will get to the desired trailer length of {desired_length} seconds.
# - All timestamps must be in numeric seconds (e.g., 14.5 — not "00:14").
# - Only use the full video if its total length is less than the user's desired trailer length.

# **Also return:**
# - Original video length (DO NOT CONFUSE WITH DESIRED TRAILER LENGTH). Original video length is always greater than the trailer length.
# - Overall mood/sentiment of the full video


# **IMPORTANT:**
# - AIM to have {desired_length / 10} segments.
# - AIM to have each segment duration be around 10 seconds.
# - Reminder: the desired trailer length is {desired_length} seconds which the trailer length cannot exceed.
# - Music must reflect the dominant mood and pacing of selected segments.
# - Each music track must have a **distinct combination** of style and sentiment.
# - EXTREMELY IMPORTANT: Return ONLY the final JSON using this exact format WITH NO ADDITIONAL TEXT:
# {json.dumps(twelvelabs_output_schema, indent=4)}

# Now take a deep breath and start analyzing the video.
# """


extract_info_prompt = f"""
You are a professional video analyst that extracts information from videos for picking the best suited music for scenes in a video and giving general music suggestions.
The final output is a trailer video with a HARD cut off length of {desired_length} seconds. The trailer video cannot exceed this length.

Given a video and the desired Trailers  length, you must
1. Analyze and break video into logical segments based on mood, content, or scene/highlight changes.
2. Only choose the most important segments to KEEP, The total length of the segments (each segment length calculated as end_time - start_time) must be less than or equal to the trailer length of {desired_length} seconds which is the final product.
3. When segments total time is greater than the desired trailer length, start removing segments in the trailer until the total length of the segments drops below {desired_length} seconds.
4. Propose {num_tracks} suitable music track(s) based on the mood and pacing of the selected segments.

Each segment must include:
- "start_time": (number, in seconds)
- "end_time": (number, in seconds)
- "sentiment": the mood of the segment
- "music_style": strictly "{music_style}"
- "include": true or false (true if segment is included in the cropped final trailer)

The end_time - start_time of each segment is the segment's duration. All segment durations added together must be less than the desired trailer length of {desired_length} seconds.

---


**Constraints for Music Tracks:**
- The number of tracks must be exactly {num_tracks}.
- The total duration of the audio tracks combined MUST equal the total duration of `"include": true` segments.
- Track time ranges must not overlap.
- All timestamps must be numeric values in seconds.
- This duration of all tracks combined must NOT exceed the MAX trailer length of {desired_length} seconds.
- Each track must use a **unique combination** of `style` and `sentiment`.
- Track sentiment must be a single word strictly from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful".

---

**General Rules:**
- Segments should be at least 4 seconds long. Remove them if they are less than 4 seconds long.
- Segments must not overlap or leave gaps between included portions.
- Use the most emotionally or narratively meaningful scenes, BUT ABOVE ALL, make sure the total sum of durations of all the segments equals the user's desired trailer length of {desired_length} seconds.
- Prioritize time over meaningfulness. This means you can drop some segments or add some segments, even if they are not meaningful, as long as doing so will get to the desired trailer length of {desired_length} seconds.
- All timestamps must be in numeric seconds (e.g., 14.5 — not "00:14").
- Only use the full video if its total length is less than the user's desired trailer length.

**Also return:**
- Original video length (DO NOT CONFUSE WITH DESIRED TRAILER LENGTH). Original video length is always greater than the trailer length.
- Overall mood/sentiment of the full video


**IMPORTANT:**
- AIM to have {desired_length / 10} segments.
- AIM to have an exactly {desired_length} second video total when summing up (end - start) for each
- Avoid including segments over 20 seconds calculated by (end - start)
- Reminder: the desired trailer length is {desired_length} seconds which the trailer length cannot exceed.
- Music must reflect the dominant mood and pacing of selected segments.
- Each music track must have a **distinct combination** of style and sentiment.
- EXTREMELY IMPORTANT: Return ONLY the final JSON using this exact format WITH NO ADDITIONAL TEXT:
{json.dumps(twelvelabs_output_schema, indent=4)}

Now take a deep breath and start analyzing the video.
"""
