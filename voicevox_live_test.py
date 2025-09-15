# test_script.py
import os
import subprocess
import time
import signal
from streamer import VoiceVoxStreamer
import threading

class ContinuousStreamer(VoiceVoxStreamer):
    def __init__(self):
        super().__init__()
        self.streaming = False
        self.stream_process = None

    def create_simple_video(self, scene_data, audio_file, output_file):
        """文字化けを避けるため、テキストなしのシンプル動画作成"""
        if not os.path.exists(audio_file):
            print(f"音声ファイルが存在しません: {audio_file}")
            return False
        
        video_width = scene_data.get("width", 1280)
        video_height = scene_data.get("height", 720)
        
        print(f"動画作成中: {audio_file}")
        
        cmd = [
            'ffmpeg', '-y', '-i', audio_file,
            '-f', 'lavfi', '-i', f'color=black:size={video_width}x{video_height}',
            '-map', '1:v', '-map', '0:a',
            '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest', output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"動画作成エラー: {result.stderr}")
            return False
        
        print(f"動画作成完了: {output_file}")
        return True

    def prepare_all_scenes(self, script_data):
        """シンプル動画版でシーン準備"""
        scenes = script_data.get("scenes", [])
        if not scenes:
            print("シーンが見つかりません")
            return False
            
        print(f"{len(scenes)}個のシーンを準備中...")
        
        for i, scene in enumerate(scenes):
            audio_file = os.path.join(self.audio_dir, f"scene_{i:03d}_audio.wav")
            video_file = os.path.join(self.video_dir, f"scene_{i:03d}_video.mp4")
            
            print(f"[{i+1}/{len(scenes)}] シーン処理中...")
            
            if not self.generate_voice(scene["text"], scene["speaker_id"], audio_file):
                return False
            
            if not self.create_simple_video(scene, audio_file, video_file):
                return False
            
            self.prepared_scenes.append(video_file)
            
        print(f"全{len(self.prepared_scenes)}シーン準備完了")
        return True

    def create_loop_video(self):
        """ループ動画作成"""
        if not self.prepared_scenes:
            print("準備されたシーンがありません")
            return None
        
        loop_video = "output/loop_stream.mp4"
        concat_list = "loop_concat_list.txt"
        
        try:
            with open(concat_list, 'w', encoding='utf-8') as f:
                for _ in range(10):  # 10回ループ
                    for video_file in self.prepared_scenes:
                        abs_path = os.path.abspath(video_file).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")
            
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c:v', 'libx264', '-c:a', 'aac', loop_video
            ]
            
            print("ループ動画作成中...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"ループ動画作成完了: {loop_video}")
                return loop_video
            else:
                print(f"ループ動画作成失敗: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"ループ動画作成例外: {e}")
            return None
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

def run_test():
    print("=== VoiceVox RTMP配信テスト ===")
    
    streamer = ContinuousStreamer()
    
    try:
        if not streamer.check_services():
            print("VoiceVoxサーバーを起動してください")
            return
        
        if not streamer.start_rtmp_server():
            print("RTMPサーバー起動失敗")
            return
        
        time.sleep(2)
        
        # テストシーン
        test_script = {
            "title": "音声配信テスト",
            "scenes": [
                {
                    "text": "VoiceVoxを使った音声配信のテストです。音声が正常に聞こえていますか？",
                    "speaker_id": 1
                },
                {
                    "text": "このシステムではリアルタイムで日本語音声を配信できます。技術的には完全に動作しています。",
                    "speaker_id": 1
                }
            ]
        }
        
        if not streamer.prepare_all_scenes(test_script):
            print("シーン準備失敗")
            return
        
        loop_video = streamer.create_loop_video()
        if not loop_video:
            print("ループ動画作成失敗")
            return
        
        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        input("準備ができたらEnterを押してください...")
        
        # 継続配信開始
        cmd = [
            'ffmpeg', '-re', '-stream_loop', '-1', '-i', loop_video,
            '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv',
            'rtmp://localhost:1935/live/test-stream'
        ]
        
        print("VoiceVox音声配信開始")
        print("停止するにはCtrl+Cを押してください")
        
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("配信停止")
        
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        streamer.stop_rtmp_server()
        print("クリーンアップ完了")
def start_stream_debug(self, video_file):
    cmd = [
        'ffmpeg', '-re', '-stream_loop', '-1', '-i', video_file,
        '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv',
        self.rtmp_url
    ]
    
    self.current_process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,  # 全出力を統合
        universal_newlines=True,
        bufsize=1
    )
    
    # リアルタイム出力監視
    def monitor_output():
        for line in self.current_process.stdout:
            print(f"FFmpeg: {line.strip()}")
    
    threading.Thread(target=monitor_output, daemon=True).start()
if __name__ == "__main__":
    run_test()