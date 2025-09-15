from streamer import VoiceVoxStreamer
from input_listener import wait_for_prompt

if __name__ == "__main__":
    streamer = VoiceVoxStreamer()
    if not streamer.check_services():
        exit(1)

    script_data = streamer.load_script('scripts/script.json')
    if not script_data:
        exit(1)

    if not streamer.prepare_all_scenes(script_data):
        exit(1)

    wait_for_prompt(streamer)  # 質問受付（同期版）
    input("Enterで配信開始...")
    streamer.stream_all_scenes()

