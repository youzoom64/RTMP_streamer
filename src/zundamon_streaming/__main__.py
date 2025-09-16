"""ずんだもんライブ配信システム エントリーポイント"""
from .core.animator import ZundamonAnimator

def main():
    background_video = "D:/Bandicam/CharaStudio 2025-04-01 11-45-21-752.mp4"
    animator = ZundamonAnimator(layer_dir="assets/zundamon", fps=30)
    
    try:
        if not animator.start_layer_stream(background_video):
            return
        
        print("VLCで rtmp://localhost:1935/live/test-stream を開いてください")
        print("コマンド: テキスト=音声, 'happy'=笑顔, 'normal'=通常, 'exit'=終了")
        
        while True:
            text = input("\n入力: ").strip()
            if text.lower() == "exit":
                break
            elif text.lower() == "happy":
                animator.change_expression(mouth="ほあー", eyes="にっこり")
            elif text.lower() == "normal":
                animator.change_expression(mouth="むふ", eyes="普通目")
            else:
                animator.add_speech(text)
                
    except KeyboardInterrupt:
        print("\n配信停止中...")
    finally:
        animator.stop_stream()

if __name__ == "__main__":
    main()
