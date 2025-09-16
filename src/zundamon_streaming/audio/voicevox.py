"""VOICEVOX API クライアント"""
import requests
from typing import Optional

class VoiceVoxClient:
    def __init__(self, base_url: str = "http://localhost:50021"):
        self.base_url = base_url
    
    def generate_voice(self, text: str, speaker_id: int = 3) -> Optional[bytes]:
        """音声データ生成"""
        try:
            print(f"VOICEVOX音声生成開始: '{text}' (speaker={speaker_id})")
            
            # クエリ生成
            query_response = requests.post(
                f"{self.base_url}/audio_query",
                params={"text": text, "speaker": speaker_id}
            )
            query_response.raise_for_status()
            print(f"クエリ生成成功: {query_response.status_code}")
            
            # 音声合成
            synthesis_response = requests.post(
                f"{self.base_url}/synthesis",
                params={"speaker": speaker_id},
                json=query_response.json(),
                headers={"Content-Type": "application/json"}
            )
            synthesis_response.raise_for_status()
            
            audio_data = synthesis_response.content
            print(f"音声合成成功: {len(audio_data)} bytes")
            
            # 音声データの先頭を確認
            if len(audio_data) > 44:  # WAVヘッダーをスキップ
                sample_data = audio_data[44:144]  # 100バイトのサンプル
                hex_preview = sample_data.hex()[:50]
                print(f"音声データ先頭: {hex_preview}...")
                
                # 実際に音声データが含まれているかチェック
                import numpy as np
                if len(sample_data) >= 4:
                    sample_values = np.frombuffer(sample_data, dtype=np.int16)
                    max_amplitude = np.max(np.abs(sample_values)) if len(sample_values) > 0 else 0
                    print(f"最大振幅: {max_amplitude} / 32767 = {(max_amplitude/32767)*100:.1f}%")
            
            return audio_data
            
        except requests.exceptions.ConnectionError:
            print("VOICEVOXサーバーに接続できません (http://localhost:50021)")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"VOICEVOX APIエラー: {e}")
            return None
        except Exception as e:
            print(f"音声生成エラー: {e}")
            return None