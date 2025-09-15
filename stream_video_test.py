import subprocess
import time
from streamer import VoiceVoxStreamer
import os

VIDEO_PATH = r"D:\Bandicam\CharaStudio 2025-04-01 11-45-21-752.mp4"  # ← 再生したい動画のパスを指定

def test_video_rtmp():
    """特定の動画ファイルをRTMP配信するテスト"""
    if not os.path.exists(VIDEO_PATH):
        print(f"❌ 動画ファイルが見つかりません: {VIDEO_PATH}")
        return

    streamer = VoiceVoxStreamer()
    if not streamer.start_rtmp_server():
        return

    time.sleep(3)

    print("📺 VLCを開いて rtmp://localhost:1935/live/test-stream を準備してください")
    input("準備ができたらEnterを押してください...")

    cmd = [
        "ffmpeg",
        "-re",               # 実時間で再生
        "-i", VIDEO_PATH,    # 入力動画
        "-c:v", "libx264",   # 映像エンコード
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-c:a", "aac",       # 音声エンコード
        "-ar", "44100",
        "-f", "flv",
        "rtmp://localhost:1935/live/test-stream"
    ]

    print("📡 動画配信開始...")
    try:
        process = subprocess.Popen(cmd)
        process.wait()  # 動画が終わるまで待機
    except KeyboardInterrupt:
        print("\n🛑 配信停止中...")
        process.terminate()
    finally:
        streamer.stop_rtmp_server()
        print("🧹 クリーンアップ完了")

if __name__ == "__main__":
    test_video_rtmp()
