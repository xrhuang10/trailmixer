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
                    "description": "One of: 'happy', 'sad', 'energetic', 'calm', 'dramatic', 'romantic', 'suspenseful'"
                },
                "music_style": {
                    "type": "string",
                    "description": "One of: 'Classical', 'Hip Hop', 'Pop', 'Electronic', 'Meme'"
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

extract_info_prompt = f"""
You are a professional video analyst that extracts information from videos for automated music mixing and editing.

You will be given a video and must:
1. Analyze and break it into logical segments based on mood, content, or scene/highlight changes.
2. Select the most important segments to KEEP, such that the total cropped duration is the **lesser of** the video length and approximately {desired_length} seconds (allow a few seconds of flexibility for clean scene transitions).
3. Propose {num_tracks} suitable music track(s) based on the mood and pacing of the selected segments.

Each segment must include:
- "start_time": (number, in seconds)
- "end_time": (number, in seconds)
- "sentiment": the mood of the segment
- "music_style": strictly "{music_style}"
- "intensity": one of ["low", "medium", "high"]
- "include": true or false (true if segment is included in the cropped final video)

---

**Music Track Guidelines:**

Use the following structure for the `"music"` object:

{f'''Single track format (if num_tracks = 1):
"music": {{
    "tracks": [
        {{
            "start": 0,
            "end": total_duration_of_included_segments (must be the lesser of {desired_length} and video length),
            "style": "{music_style}",
            "intensity": "<analyzed intensity>",
            "sentiment": "<one word from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful">"
        }}
    ]
}}''' if num_tracks == 1 else f'''Multiple tracks format (if num_tracks > 1):
"music": {{
    "tracks": [
        {{
            "start": 0,
            "end": length_a,
            "style": "{music_style}",
            "intensity": "<analyzed intensity>",
            "sentiment": "<one word from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful"
        }},
        {{
            "start": length_a,
            "end": length_b,
            "style": "{music_style}",
            "intensity": "<analyzed intensity>",
            "sentiment": "<one word from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful>"
        }},
        ...
        {{
            "start": length_n,
            "end": total_duration_of_included_segments (must be the lesser of {desired_length} and video length),
            "style": "{music_style}",
            "intensity": "<analyzed intensity>",
            "sentiment": "<one word from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful>""
        }}
    ]
}}'''}

**Constraints for Music Tracks:**
- The number of tracks must be exactly {num_tracks}.
- The total duration of all tracks combined must equal the total duration of `"include": true` segments.
- This duration must NOT exceed the lesser of the video length and the user's desired length of {desired_length} seconds.
- Track time ranges must not overlap.
- All timestamps must be numeric values in seconds.
- Each track must use a **unique combination** of `style` and `sentiment`.
- Track sentiment must be a single word strictly from: "happy", "sad", "energetic", "calm", "dramatic", "romantic", "suspenseful".

---

**General Rules:**
- The combined duration of all `"include": true` segments must not exceed the lesser of {desired_length} and the total video length. The sum of all the durations (end_time - start_time) of all the segments will therefore be around {desired_length} seconds.
- Segments must not overlap or leave gaps between included portions.
- Use only the most emotionally or narratively meaningful scenes.
- All timestamps must be in numeric seconds (e.g., 14.5 — not "00:14").
- Only use the full video if its total length is less than the user's desired length of {desired_length} seconds.

**Also return:**
- Full original video length (`video_length`)
- Effective cropped video length (equal to total `"include": true` segment durations)
- Overall mood/sentiment of the full video

**IMPORTANT:**
- Only segments marked `"include": true` are retained and used for music generation. Therefore, the sum of all the durations (end_time - start_time) of all the segments will be around the user's desired length of {desired_length} seconds.
- Music must reflect the dominant mood and pacing of selected segments.
- Each music track must have a **distinct combination** of style and sentiment.
- Your #1 priority is to create a list of segments whose total sum of durations (end_time - start_time) equals the user's desired length of {desired_length} seconds, even if that means incorporating less meaningful segments. The sum of all the music track durations will also be around the user's desired length of {desired_length} seconds.
- No commentary or explanation — return ONLY the final JSON using this exact format:

{json.dumps(twelvelabs_output_schema, indent=4)}

Now take a deep breath and start analyzing the video.
"""
