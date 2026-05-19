import argparse
import json

from backend.pipeline import AnaiTranslatorPipeline


def main():
    parser = argparse.ArgumentParser(description="Run the local Anai Translator pipeline.")
    parser.add_argument("--text", help="Text to translate.")
    parser.add_argument("--audio", help="Audio file to transcribe and translate.")
    parser.add_argument("--source", default="en", help="Source language code.")
    parser.add_argument("--target", default="es", help="Target language code.")
    parser.add_argument("--tone", help="Optional tone for the context layer.")
    parser.add_argument("--speak", action="store_true", help="Generate translated speech audio.")
    parser.add_argument("--output", default="models/output.wav", help="Output audio path.")
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON output.")
    args = parser.parse_args()

    if not args.text and not args.audio:
        parser.error("Provide either --text or --audio.")

    pipeline = AnaiTranslatorPipeline()

    if args.audio:
        result = pipeline.translate_audio(
            args.audio,
            source_language=args.source,
            target_language=args.target,
            tone=args.tone,
            synthesize_audio=True,
            output_audio_path=args.output,
        )
    else:
        result = pipeline.translate_text(
            args.text,
            source_language=args.source,
            target_language=args.target,
            tone=args.tone,
            synthesize_audio=args.speak,
            output_audio_path=args.output,
        )

    payload = {
        "source_text": result.source_text,
        "improved_text": result.improved_text,
        "translated_text": result.translated_text,
        "audio_output_path": result.audio_output_path,
    }
    if args.json:
        parser.exit(0, json.dumps(payload, ensure_ascii=False) + "\n")
    lines = [
        f"Source: {result.source_text}",
        f"Improved: {result.improved_text}",
        f"Translated: {result.translated_text}",
    ]
    if result.audio_output_path:
        lines.append(f"Audio: {result.audio_output_path}")
    parser.exit(0, "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
