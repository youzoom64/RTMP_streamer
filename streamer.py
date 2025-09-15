import json
import subprocess
import requests
import os
import socket
import time

class VoiceVoxStreamer:
    def __init__(self):
        self.voicevox_url = "http://localhost:50021"
        self.rtmp_url = "rtmp://localhost:1935/live/test-stream"
        self.rtmp_process = None
        self.prepared_scenes = []
        
        # 出力ディレクトリを作成
        self.audio_dir = os.path.join("output", "audio")
        self.video_dir = os.path.join("output", "video")
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.video_dir, exist_ok=True)

    def check_services(self):
        # VoiceVoxサーバーチェック
        try:
            response = requests.get(f"{self.voicevox_url}/speakers", timeout=5)
            print(f"VoiceVox接続: OK (ステータス: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"VoiceVoxサーバーエラー: {e}")
            return False
        
        return True

    def check_rtmp_server(self):
        """RTMPサーバーの接続確認（オプション）"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('localhost', 1935))
        sock.close()
        
        if result == 0:
            print("RTMPサーバー接続: OK")
            return True
        else:
            print("RTMPサーバーエラー: ポート1935が開いていません")
            return False

    def start_rtmp_server(self):
        """Node Media Serverを起動"""
        try:
            print("🚀 RTMPサーバー起動中...")
            self.rtmp_process = subprocess.Popen(
                ['node', 'rtmp_server.js'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(3)  # サーバー起動待ち
            
            # 起動確認
            if self.check_rtmp_server():
                print("✅ RTMPサーバー起動完了")
                return True
            else:
                print("❌ RTMPサーバー起動失敗")
                self.stop_rtmp_server()
                return False
                
        except FileNotFoundError:
            print("❌ Node.jsが見つかりません。以下をインストールしてください:")
            print("  npm install node-media-server")
            return False
        except Exception as e:
            print(f"❌ RTMPサーバー起動エラー: {e}")
            return False

    def stop_rtmp_server(self):
        """RTMPサーバーを停止"""
        if self.rtmp_process:
            self.rtmp_process.terminate()
            try:
                self.rtmp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.rtmp_process.kill()
            self.rtmp_process = None
            print("🛑 RTMPサーバー停止")

    def load_script(self, json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"スクリプトファイル {json_file} が見つかりません")
            return None
        except json.JSONDecodeError as e:
            print(f"JSONファイル読み込みエラー: {e}")
            return None

    def generate_voice(self, text, speaker_id, output_file):
        try:
            print(f"音声生成中: {text[:20]}...")
            
            query_response = requests.post(
                f"{self.voicevox_url}/audio_query", 
                params={"text": text, "speaker": speaker_id},
                timeout=10
            )
            query_response.raise_for_status()
            
            audio_response = requests.post(
                f"{self.voicevox_url}/synthesis", 
                params={"speaker": speaker_id}, 
                json=query_response.json(),
                timeout=30
            )
            audio_response.raise_for_status()
            
            with open(output_file, 'wb') as f:
                f.write(audio_response.content)
            
            print(f"✅ 音声生成完了: {output_file}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 音声生成エラー: {e}")
            return False

    def create_character_video(self, scene_data, audio_file, output_file):
        if not os.path.exists(audio_file):
            print(f"❌ 音声ファイルが存在しません: {audio_file}")
            return False
        
        text = scene_data.get("text", "")
        display_text = scene_data.get("display_text", text)
        character_image = scene_data.get("character_image", "")
        
        font_size = scene_data.get("font_size", 36)
        font_color = scene_data.get("font_color", "white")
        video_width = scene_data.get("width", 1280)
        video_height = scene_data.get("height", 720)
        
        # テキストのエスケープ処理を強化
        safe_text = display_text.replace("'", "\\'").replace('"', '\\"').replace('\\', '\\\\')
        
        print(f"📹 動画作成中: {display_text[:30]}...")
        
        if character_image and os.path.exists(character_image):
            filter_complex = (
                f"[1:v][2:v]overlay=50:h-h*0.8:eval=init[char_overlay];"
                f"[char_overlay]drawtext=text='{safe_text}':fontcolor={font_color}:fontsize={font_size}:x=(w-text_w)/2:y=h-120:box=1:boxcolor=black@0.5:boxborderw=10[final]"
            )
            cmd = [
                'ffmpeg', '-y', '-i', audio_file,
                '-f', 'lavfi', '-i', f'color=black:size={video_width}x{video_height}',
                '-i', character_image,
                '-filter_complex', filter_complex,
                '-map', '[final]', '-map', '0:a',
                '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest', output_file
            ]
        else:
            cmd = [
                'ffmpeg', '-y', '-i', audio_file,
                '-f', 'lavfi', '-i', f'color=black:size={video_width}x{video_height}',
                '-filter_complex', f"[1:v]drawtext=text='{safe_text}':fontcolor={font_color}:fontsize={font_size}:x=(w-text_w)/2:y=h-120:box=1:boxcolor=black@0.5:boxborderw=10[final]",
                '-map', '[final]', '-map', '0:a',
                '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-shortest', output_file
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ 動画作成エラー: {result.stderr}")
            return False
        
        print(f"✅ 動画作成完了: {output_file}")
        return True

    def prepare_all_scenes(self, script_data):
        """全シーンの音声・動画を事前生成"""
        scenes = script_data.get("scenes", [])
        if not scenes:
            print("❌ シーンが見つかりません")
            return False
            
        print(f"📋 {len(scenes)}個のシーンを準備中...")
        
        for i, scene in enumerate(scenes):
            audio_file = os.path.join(self.audio_dir, f"scene_{i:03d}_audio.wav")
            video_file = os.path.join(self.video_dir, f"scene_{i:03d}_video.mp4")
            
            print(f"[{i+1}/{len(scenes)}] シーン処理中...")
            
            if not self.generate_voice(scene["text"], scene["speaker_id"], audio_file):
                return False
            
            if not self.create_character_video(scene, audio_file, video_file):
                return False
            
            self.prepared_scenes.append(video_file)
            
        print(f"✅ 全{len(self.prepared_scenes)}シーン準備完了")
        return True

    def test_stream_to_file(self):
        """RTMPの代わりにファイル出力でテスト"""
        if not self.prepared_scenes:
            print("❌ 準備されたシーンがありません")
            return False
        
        output_file = "output/test_stream.mp4"
        concat_list = "concat_list.txt"
        
        print("📹 ファイル出力テスト中...")
        
        try:
            with open(concat_list, 'w', encoding='utf-8') as f:
                for video_file in self.prepared_scenes:
                    abs_path = os.path.abspath(video_file)
                    # Windowsパス対応
                    abs_path = abs_path.replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c:v', 'libx264', '-c:a', 'aac', output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ ファイル出力成功: {output_file}")
                return True
            else:
                print(f"❌ ファイル出力エラー: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ ファイル出力例外: {e}")
            return False
        finally:
            # 一時ファイル削除
            if os.path.exists(concat_list):
                os.remove(concat_list)

    def stream_all_scenes(self):
        """RTMP配信実行"""
        if not self.prepared_scenes:
            print("❌ 準備されたシーンがありません")
            return False
        
        concat_list = "concat_list.txt"
        
        try:
            with open(concat_list, 'w', encoding='utf-8') as f:
                for video_file in self.prepared_scenes:
                    abs_path = os.path.abspath(video_file)
                    abs_path = abs_path.replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list,
                '-c:v', 'libx264', '-c:a', 'aac', '-f', 'flv', self.rtmp_url
            ]
            
            print("📡 RTMP配信開始...")
            print(f"配信URL: {self.rtmp_url}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ RTMP配信完了")
                return True
            else:
                print(f"❌ RTMP配信エラー: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ RTMP配信例外: {e}")
            return False
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

    def run_full_test(self, script_data):
        """完全なテストフローを実行"""
        print("=== VoiceVox RTMP配信 完全テスト ===")
        
        # 1. サービス確認
        if not self.check_services():
            print("❌ VoiceVoxサーバーを先に起動してください")
            return False
        
        # 2. シーン準備
        if not self.prepare_all_scenes(script_data):
            print("❌ シーン準備失敗")
            return False
        
        # 3. ファイル出力テスト
        if not self.test_stream_to_file():
            print("❌ ファイル出力テスト失敗")
            return False
        
        # 4. RTMP配信テスト
        if self.start_rtmp_server():
            try:
                if self.stream_all_scenes():
                    print("✅ 全テスト成功！")
                    return True
                else:
                    print("❌ RTMP配信失敗")
                    return False
            finally:
                self.stop_rtmp_server()
        else:
            print("❌ RTMPサーバー起動失敗")
            return False

    def __del__(self):
        """デストラクタでRTMPサーバーを確実に停止"""
        self.stop_rtmp_server()

