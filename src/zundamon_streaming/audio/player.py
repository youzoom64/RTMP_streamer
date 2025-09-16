import numpy as np
import threading
import time
import pygame
import os

class AudioPlayer:
    def __init__(self):
        pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        self.current_volume = 0.0
        self.volume_monitor_active = False
    
    def play_audio_data(self, audio_data, stop_event):
        """音声データ再生"""
        temp_file = f"debug_audio_{int(time.time())}.wav"  # ←ファイル名を変更して保存
        
        try:
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            
            print(f"音声ファイル保存: {temp_file}")  # ←ファイル確認用
            
            # 音量モニタリング開始
            self.volume_monitor_active = True
            volume_thread = threading.Thread(target=self._monitor_volume, args=(audio_data,), daemon=True)
            volume_thread.start()
            
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy() and not stop_event.is_set():
                time.sleep(0.1)
                
        finally:
            self.volume_monitor_active = False
            # ファイルを削除しないでそのまま残す
    def _monitor_volume(self, audio_data):
        """音声データから正しい音量を計算"""
        try:
            # 実際に再生されている音声の音量を取得
            while self.volume_monitor_active:
                if pygame.mixer.music.get_busy():
                    # pygameから直接音量を取得
                    volume = pygame.mixer.music.get_volume() * 100
                    
                    # バー表示
                    bar_length = int(volume / 2)  # 50文字max
                    bar = "█" * bar_length + "░" * (50 - bar_length)
                    print(f"\r音量: [{bar}] {volume:.1f}%", end="", flush=True)
                else:
                    print(f"\r音量: [{'░' * 50}] 0.0%", end="", flush=True)
                    
                time.sleep(0.1)
                
        except Exception as e:
            print(f"\n音量モニタリングエラー: {e}")
        
        print()  # 改行