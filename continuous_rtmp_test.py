# continuous_rtmp_test.py
import subprocess
import time
import threading
from streamer import VoiceVoxStreamer

def test_continuous_rtmp():
    """継続的なRTMP配信テスト"""
    streamer = VoiceVoxStreamer()
    
    if not streamer.start_rtmp_server():
        return
    
    time.sleep(3)
    
    print("📺 VLCを開いて rtmp://localhost:1935/live/test-stream を準備してください")
    input("準備ができたらEnterを押してください...")
    
    # 無限ループのテストパターン配信
    cmd = [
        'ffmpeg', 
        '-f', 'lavfi', '-i', 'testsrc=size=640x480:rate=30',  # duration削除で無限
        '-f', 'lavfi', '-i', 'sine=frequency=1000',  # duration削除で無限
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-c:a', 'aac', '-ar', '44100',
        '-f', 'flv', 'rtmp://localhost:1935/live/test-stream'
    ]
    
    print("📡 継続配信開始...")
    print("VLCで受信を確認してください")
    print("停止するにはCtrl+Cを押してください")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 配信状態を監視
        start_time = time.time()
        while True:
            # プロセスが生きているかチェック
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print("❌ 配信プロセスが終了しました")
                print(f"エラー: {stderr.decode()}")
                break
            
            # 経過時間表示
            elapsed = int(time.time() - start_time)
            print(f"\r📡 配信中... {elapsed}秒経過", end="", flush=True)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 配信停止中...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    finally:
        streamer.stop_rtmp_server()
        print("🧹 クリーンアップ完了")

if __name__ == "__main__":
    test_continuous_rtmp()