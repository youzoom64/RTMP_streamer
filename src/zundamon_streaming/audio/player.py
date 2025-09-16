import numpy as np
import threading
import time
import pyaudio
import wave
import io
import os

class AudioPlayer:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.volume_callback = None
        self.mouth_callback = None  # 口パク制御用コールバック
        self.temp_dir = "temp/audio"
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def play_audio_data(self, audio_data, stop_event):
        """音声データ再生 + リアルタイム口パク制御"""
        
        # 一時ファイル用ディレクトリ作成
        temp_dir = "temp/audio"
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # WAVデータをメモリで解析
            wav_io = io.BytesIO(audio_data)
            with wave.open(wav_io, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                
                print(f"WAV情報: {frames}フレーム, {sample_rate}Hz, {channels}ch, {sample_width}byte")
                
                # 音声ストリーム開始
                stream = self.audio.open(
                    format=self.audio.get_format_from_width(sample_width),
                    channels=channels,
                    rate=sample_rate,
                    output=True,
                    frames_per_buffer=1024
                )
                
                print("pyaudio 3ストリーム音声開始")
                
                # チャンクサイズ（0.1秒分）
                chunk_frames = int(sample_rate * 0.1)
                
                wav_file.rewind()
                chunk_count = 0
                while not stop_event.is_set():
                    chunk = wav_file.readframes(chunk_frames)
                    if not chunk:
                        break
                    
                    chunk_count += 1
                    
                    # 音声出力
                    stream.write(chunk)
                    
                    # 振幅計算（口パク判定）
                    if self.mouth_callback:
                        audio_array = np.frombuffer(chunk, dtype=np.int16)
                        if len(audio_array) > 0:
                            amplitude = np.max(np.abs(audio_array))
                            amplitude_percent = (amplitude / 32767.0) * 100
                            
                            # 口パクしきい値: 1%
                            is_speaking = amplitude_percent > 1.0
                            self.mouth_callback(is_speaking, amplitude_percent)
                
                stream.stop_stream()
                stream.close()
                print(f"pyaudio 3ストリーム音声完了: {chunk_count}チャンク処理")
                
        except Exception as e:
            print(f"pyaudio 3ストリーム音声エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def __del__(self):
        if hasattr(self, 'audio'):
            self.audio.terminate()