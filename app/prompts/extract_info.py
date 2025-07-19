import json

with open("prompts/twelvelabs_output_schema.json", "r") as f:
    twelvelabs_output_schema = json.load(f)

desired_length = 60  # in seconds
music_style = "Pop"  # One of: Classical, Hip Hop, Pop, Electronic, Meme
music_intensity = "medium"  # Can also make this a variable if needed
num_tracks = 1

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
              "sentiment": The overall sentiment of the video
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
- The total duration of all segments where `"include": true` MUST NOT exceed {desired_length} seconds.
- Only select the most meaningful scenes for inclusion.
- Segments without "include": true will be ignored for the final cropped video and music generation.

Return ONLY the JSON response following this exact format:
{json.dumps(twelvelabs_output_schema, indent=4)}
"""
