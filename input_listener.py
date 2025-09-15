def wait_for_prompt(streamer):
    try:
        while True:
            user_input = input("質問があれば入力してください (Enterでスキップ): ")
            if not user_input.strip():
                break
            print(f"質問: {user_input}")
            from rag_client import ask_rag
            answer = ask_rag(user_input)
            print(f"回答: {answer}")
            # TODO: streamer に新しいシーンとして追加し、音声合成して再生
    except KeyboardInterrupt:
        print("\n質問受付終了")

