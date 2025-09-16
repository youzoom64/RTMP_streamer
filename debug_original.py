"""元のコードのFFmpegコマンドをログ出力"""
import sys
sys.path.append('.')

# 元のコードを一時的に修正してFFmpegコマンドを出力
# src/zundamon_streaming/rtmp/ffmpeg.py の start_stream メソッドで
# print(f"FFmpeg command: {' '.join(cmd)}")
# を追加して、実際のコマンドを確認

from src.zundamon_streaming.core.animator import ZundamonAnimator

animator = ZundamonAnimator()
# 実際のFFmpegコマンドをログで確認
