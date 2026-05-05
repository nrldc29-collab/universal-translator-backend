import argparse

from backend.pipeline import UniversalTranslatorPipeline


def main():
    parser = argparse.ArgumentParser(description="Run the local universal translator pipeline.")
    parser.add_argument("--text", help="Text to translate.")
    parser.add_argument("--audio", help="Audio file to transcribe and translate.")
    parser.add_argument("--source", default="en", help="Source language code.")
    parser.add_argument("--target", default="es", help="Target language code.")
    parser.add_argument("--tone", help="Optional tone for the context layer.")
    parser.add_argument("--speak", action="store_true", help="Generate translated speech audio.")
    parser.add_argument("--output", default="models/output.wav", help="Output audio path.")
    args = parser.parse_args()

    if not args.text and not args.audio:
        parser.error("Provide either --text or --audio.")

    pipeline = UniversalTranslatorPipeline()

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

    print(f"Source: {result.source_text}")
    print(f"Improved: {result.improved_text}")
    print(f"Translated: {result.translated_text}")
    if result.audio_output_path:
        print(f"Audio: {result.audio_output_path}")


if __name__ == "__main__":
    main()
