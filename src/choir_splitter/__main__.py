"""Desktop entry point, with explicit online model preparation."""
import argparse
import sys
import ssl
from urllib.error import URLError


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
        try:
            get_model("htdemucs")
        except (URLError, ssl.SSLCertVerificationError) as error:
            reason = error.reason if isinstance(error, URLError) else error
            if not isinstance(reason, ssl.SSLCertVerificationError):
                parser.exit(1, f"Model preparation failed: {error}\nCheck your connection and proxy settings, then retry.\n")
            message = "Model download failed: Python could not verify the server's TLS certificate.\n"
            if sys.platform == "darwin":
                version = f"{sys.version_info.major}.{sys.version_info.minor}"
                message += (
                    "For the python.org macOS installer, run:\n"
                    f'  open "/Applications/Python {version}/Install Certificates.command"\n'
                    "Wait for it to finish, then retry:\n"
                )
            else:
                message += "Install or repair the trusted CA certificates for this Python installation, then retry:\n"
            message += (
                "  python -m choir_splitter --prepare-model\n"
                "If your network uses a company TLS proxy, obtain its trusted CA bundle from IT "
                "and set SSL_CERT_FILE to that bundle's path before retrying.\n"
                "TLS verification has not been disabled.\n"
            )
            parser.exit(1, message)
        print("Model is cached. Processing can now run offline.")
        return 0
    from .app import launch
    return launch()


if __name__ == "__main__":
    sys.exit(main())
