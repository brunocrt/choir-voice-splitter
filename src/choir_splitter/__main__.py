"""Desktop entry point, with explicit online model preparation."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Offline choir rehearsal studio")
    parser.add_argument("--prepare-model", action="store_true", help="Download HT-Demucs weights once (requires internet)")
    args = parser.parse_args()
    if args.prepare_model:
        try:
            from demucs.pretrained import get_model
        except ImportError:
            parser.exit(1, 'Install the optional AI dependencies first: pip install -e ".[ai]"\n')
        print("Preparing HT-Demucs. This command may download pretrained weights.")
        get_model("htdemucs")
        print("Model is cached. Processing can now run offline.")
        return 0
    from .app import launch
    return launch()


if __name__ == "__main__":
    sys.exit(main())
