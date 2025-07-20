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

desired_length = 100  # in seconds
music_style = ["pop", "hiphop", "electronic", "classical", "meme"]  # One of: Classical, HipHop, Pop, Electronic, Meme
num_tracks = 3
sentiment_list = ["happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful"]

extract_info_prompt = f"""
You are a professional video analyst creating a {desired_length}-second trailer. 

**🚨 CRITICAL MATHEMATICAL CONSTRAINT 🚨**
THE TOTAL DURATION MUST EQUAL EXACTLY {desired_length} SECONDS. NOT {desired_length-1}, NOT {desired_length+1}, EXACTLY {desired_length}.

**APPROACH EXAMPLE:**
For a 300-second original video → 100-second trailer:
- Select segments with varying lengths (5s, 12s, 8s, 15s, 6s, 10s, 14s, 7s, 11s, 12s = EXACTLY 100s total)
- VERIFY: 5+12+8+15+6+10+14+7+11+12 = 100 seconds EXACTLY
- Spread across timeline but TOTAL MUST EQUAL {desired_length} SECONDS

**ABSOLUTE NON-NEGOTIABLE REQUIREMENTS:**
1. TOTAL DURATION = EXACTLY {desired_length} SECONDS (ZERO TOLERANCE FOR DEVIATION)
2. MANDATORY MATH CHECK: Sum all segment durations before finalizing - MUST equal {desired_length}
3. Segments must NOT be consecutive - spread them throughout the original video timeline
4. Segment lengths should match content importance BUT total must be {desired_length} seconds
5. If segments total > {desired_length}: REMOVE segments until exactly {desired_length}
6. If segments total < {desired_length}: EXTEND segments until exactly {desired_length}
7. Sum of ALL music track durations = EXACTLY {desired_length} seconds
8. Number of music tracks = EXACTLY {num_tracks}
9. Each track's music style MUST be selected from: {music_style}

**WARNING: IF THE VIDEO EXCEEDS {desired_length} SECONDS, THE OUTPUT IS INVALID AND REJECTED**

**SEGMENT ANALYSIS:**
- Break video into logical segments based on mood/content changes and narrative importance
- Segment lengths should be DYNAMIC based on content importance:
  * High-impact moments: 8-15 seconds (emotional peaks, action sequences, climaxes)
  * Mood transitions: 5-10 seconds (dialogue, character moments, setup scenes)
  * Quick highlights: 3-8 seconds (brief exciting moments, reaction shots, reveals)
  * Key scenes: 10-15 seconds (important story beats, memorable moments)
- CRITICAL: Segments must NOT be consecutive - create a highlight reel from across the entire video
- NATURAL SPACING: Distribute segments throughout the video timeline for variety and storytelling flow
- CONTENT-AWARE: Choose segments that showcase different aspects of the video (beginning, middle, end)
- Mark segments as "include": true/false to reach exactly {desired_length} seconds total
- ABSOLUTE PRIORITY: Duration precision over content preference - {desired_length} seconds is NON-NEGOTIABLE

**SEGMENT FORMAT:**
- "start_time": (number in seconds)
- "end_time": (number in seconds) 
- "sentiment": MUST be one of: {sentiment_list}
- "music_style": MUST be one of: {music_style}
- "include": true/false (only true segments count toward {desired_length}s)

**MUSIC TRACK CONSTRAINTS:**
- Exactly {num_tracks} tracks
- Each track covers a time range of the included segments
- No overlapping track times, no gaps between tracks
- CRITICAL: Each track MUST have a DIFFERENT style-sentiment combination
- Example: Track 1: "pop-happy", Track 2: "electronic-energetic", Track 3: "classical-dramatic"
- Track sentiment MUST be from: {sentiment_list}
- Track style MUST be one of: {music_style}
- EMPHASIS: Do NOT use any music style outside of {music_style}

**MANDATORY VALIDATION CHECKLIST:**
□ CRITICAL: Sum of (end_time - start_time) for "include": true segments = EXACTLY {desired_length}
□ CRITICAL: Sum of (end - start) for all music tracks = EXACTLY {desired_length}
□ VERIFY MATH: Calculate each segment duration and add them up = {desired_length} seconds
□ Number of music tracks = EXACTLY {num_tracks}
□ Segments are NOT consecutive - spread throughout original video with natural gaps
□ Segment lengths match content importance but TOTAL must equal {desired_length}
□ All sentiments from allowed list: {sentiment_list}
□ All music_style from allowed list: {music_style}
□ Each track has DIFFERENT style-sentiment combination from other tracks
□ All timestamps are numeric seconds
□ FINAL CHECK: Does the math add up to {desired_length} seconds? YES/NO

**REQUIRED OUTPUT:**
Return ONLY valid JSON in this exact format:
{json.dumps(twelvelabs_output_schema, indent=4)}

CALCULATE DURATIONS PRECISELY. The total of ALL selected segments MUST equal EXACTLY {desired_length} seconds. Use dynamic lengths based on content importance, spread throughout the original video, but the mathematical requirement of {desired_length} seconds total is ABSOLUTE and NON-NEGOTIABLE.
"""
