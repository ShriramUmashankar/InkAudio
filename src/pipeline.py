import argparse
from pathlib import Path

from .config import load_settings
from .ingest import convert_pdf, md_path_for
from .script_gen import generate_script, regenerate_audio, revise_script


def main() -> None:
    p = argparse.ArgumentParser(description="Local PDF -> 2-host podcast pipeline")
    p.add_argument("--pdf", default=None, help="PDF path (overrides config)")
    p.add_argument("--skip-ingest", action="store_true")
    p.add_argument("--skip-script", action="store_true")
    p.add_argument("--skip-stitch", action="store_true")
    p.add_argument("--no-tts", action="store_true", help="Skip TTS and stitching; stop after script generation")
    p.add_argument("--force-ingest", action="store_true")
    p.add_argument("--revise", action="store_true", help="Revise existing script.json from feedback file")
    p.add_argument("--feedback", default="Content/feedback.txt", help="Feedback notes file for --revise")
    p.add_argument("--config", default="config.yaml")
    args = p.parse_args()

    settings = load_settings(args.config)
    if args.pdf:
        settings.pipeline.pdf_path = args.pdf

    if args.revise:
        fb = Path(args.feedback)
        if not fb.exists():
            raise RuntimeError(f"Feedback file not found: {fb}")
        revise_script(settings, fb.read_text(encoding="utf-8"))
        return

    md_path = md_path_for(settings.pipeline.pdf_path, settings.pipeline.content_dir)

    if not args.skip_ingest:
        convert_pdf(
            settings.pipeline.pdf_path,
            settings.pipeline.content_dir,
            force=args.force_ingest,
        )

    if not args.skip_script:
        if not Path(md_path).exists():
            raise RuntimeError(f"Markdown not found at {md_path}; run ingest first.")
        markdown = Path(md_path).read_text(encoding="utf-8")
        generate_script(markdown, settings, do_stitch=not args.skip_stitch, no_tts=args.no_tts)
    else:
        regenerate_audio(settings, do_stitch=not args.skip_stitch)


if __name__ == "__main__":
    main()
