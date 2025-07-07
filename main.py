from script_generator import ScriptGenerator
from audio_generator import AudioGenerator
import os

def main():
    print("[INFO] Starting script generation...")
    script_gen = ScriptGenerator()
    script = script_gen.generate_script(topic="Real Estate Brokerage Using AI in Dubai")
    
    if script is None:
        raise ValueError("Script generation failed — received None from LLM")

    script_path = os.path.join("media", "output_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    
    print("[SUCCESS] Script generated and saved to media/output_script.txt")

    print("\n[INFO] Starting audio generation...\n")
    audio_gen = AudioGenerator()
    audio_file = audio_gen.generate_audio(script, output_file=os.path.join("media", "output_audio.mp3"))

    print("\n[INFO] Starting video generation...\n")
    from video_generator import VideoGenerator
    video_gen = VideoGenerator()
    video_file = video_gen.generate_video(script_path, audio_file, output_file=os.path.join("media", "output_video.mp4"))

    print("\n✅ MVP Progress:")
    print(" - [x] Script generated")
    print(" - [x] Audio generated")
    print(" - [x] Video generated: " + video_file)

if __name__ == "__main__":
    main()