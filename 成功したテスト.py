# voicevox_live_test.py
import subprocess
import time
import os
from streamer import VoiceVoxStreamer

def test_voicevox_live():
    """VoiceVox音声でライブ配信"""
    streamer = VoiceVoxStreamer()
    
    if not streamer.start_rtmp_server():
        return
    
    time.sleep(3)
    
    # VoiceVoxでテスト音声作成
    test_script = {
        "title": "ライブ配信テスト",
        "scenes": [
            {
                "text": "ライブ配信テストです。VLCで正常に受信できていますか？この音声はVoiceVoxで生成されています。",
                "display_text": "🔴 LIVE配信中",
                "speaker_id": 1,
                "font_size": 48,
                "font_color": "red"
            },
            {
                "text": "配信システムが正常に動作しています。音声と映像が同期して配信されています。",
                "display_text": "✅ 配信システム正常動作",
                "speaker_id": 1,
                "font_size": 36
            }
        ]
    }
    
    if not streamer.prepare_all_scenes(test_script):
        return
    
    # ループ動画作成
    loop_video = create_loop_video(streamer.prepared_scenes)
    if not loop_video:
        return
    
    print("📺 VLCで rtmp://localhost:1935/live/test-stream を開いてください")
    input("準備ができたらEnterを押してください...")
    
    # VoiceVox音声でライブ配信
    cmd = [
        'ffmpeg', '-re', '-stream_loop', '-1', '-i', loop_video,
        '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv',
        'rtmp://localhost:1935/live/test-stream'
    ]
    
    print("📡 VoiceVox音声ライブ配信開始！")
    print("🎤 VoiceVoxの音声が聞こえるはずです")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("🛑 配信停止")
    finally:
        streamer.stop_rtmp_server()

def create_loop_video(scenes):
    """シーンからループ動画作成"""
    if not scenes:
        return None
    
    loop_video = "output/voicevox_loop.mp4"
    concat_list = "voicevox_concat.txt"
    
    try:
        with open(concat_list, 'w', encoding='utf-8') as f:
            for _ in range(5):  # 5回ループ
                for video_file in scenes:
                    abs_path = os.path.abspath(video_file).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
        
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
            '-c:v', 'libx264', '-c:a', 'aac', loop_video
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ VoiceVoxループ動画作成完了: {loop_video}")
            return loop_video
        
    except Exception as e:
        print(f"❌ エラー: {e}")
    finally:
        if os.path.exists(concat_list):
            os.remove(concat_list)
    
    return None

if __name__ == "__main__":
    test_voicevox_live()