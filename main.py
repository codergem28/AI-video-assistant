from dotenv import load_dotenv
from core.transcriber import get_transcript
from core.analyzer import analyze
from core.rag_engine import build_rag_chain, ask_question


load_dotenv()

def run_pipeline(source: str, language: str = "english") -> dict:
    print("starting AI Video Assistant")

    # YouTube URLs use captions first (no download); falls back to
    # download + Whisper/Sarvam for videos without captions and local files.
    transcript = get_transcript(source, language)

    print(f"raw transcription (first 300 characters ) {transcript[:300]}")

    report = analyze(transcript)
    rag_chain = build_rag_chain(transcript)

    return {
        "title": report["title"],
        "transcript": transcript,
        "summary": report["summary"],
        "action_items": report["action_items"],
        "key_decisions": report["key_decisions"],
        "open_questions": report["open_questions"],
        "rag_chain": rag_chain,
    }
if __name__ == "__main__":
    # CLI entry point
    source = input("Enter YouTube URL or local file path: ").strip()
    language = input("Language (english/hinglish): ").strip() or "english"
    result = run_pipeline(source, language)

    print("\n" + "=" * 60)
    print(f"📌 Title: {result['title']}")
    print(f"\n📋 Summary:\n{result['summary']}")
    print(f"\n✅ Action Items:\n{result['action_items']}")
    print(f"\n🔑 Key Decisions:\n{result['key_decisions']}")
    print(f"\n❓ Open Questions:\n{result['open_questions']}")
    print("=" * 60)

    # Phase 2 — Chat with your meeting via RAG
    print("\n💬 Chat with your meeting (type 'exit' to quit)\n")
    rag_chain = result["rag_chain"]
    while True:
        question = input("You: ").strip()
        if question.lower() in ["exit", "quit", "q"]:
            print("👋 Goodbye!")
            break
        if not question:
            continue
        answer = ask_question(rag_chain, question)
        print(f"\n🤖 Assistant: {answer}\n")