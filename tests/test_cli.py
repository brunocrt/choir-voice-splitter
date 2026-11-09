"""Model preparation errors should be useful without disabling TLS verification."""
import ssl
import sys
from types import ModuleType, SimpleNamespace
from urllib.error import URLError

import pytest
from choir_splitter import __main__ as cli


def install_fake_model(monkeypatch, callback):
    module = ModuleType("demucs.pretrained")
    module.get_model = callback
    monkeypatch.setitem(sys.modules, "demucs", ModuleType("demucs"))
    monkeypatch.setitem(sys.modules, "demucs.pretrained", module)
    monkeypatch.setattr(sys, "argv", ["choir-splitter", "--prepare-model"])


@pytest.mark.parametrize("wrapped", [False, True])
def test_macos_certificate_failure_has_versioned_instructions(monkeypatch, capsys, wrapped):
    def fail(_):
        error = ssl.SSLCertVerificationError(1, "certificate verify failed")
        raise URLError(error) if wrapped else error
    install_fake_model(monkeypatch, fail)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "version_info", SimpleNamespace(major=3, minor=14))
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 1
    output = capsys.readouterr()
    assert '/Applications/Python 3.14/Install Certificates.command' in output.err
    assert "SSL_CERT_FILE" in output.err
    assert "TLS verification has not been disabled" in output.err
    assert "Model is cached" not in output.out


def test_network_error_is_not_misdiagnosed_as_certificates(monkeypatch, capsys):
    def fail(_):
        raise URLError("connection refused")
    install_fake_model(monkeypatch, fail)
    with pytest.raises(SystemExit):
        cli.main()
    output = capsys.readouterr()
    assert "connection refused" in output.err
    assert "Install Certificates.command" not in output.err


def test_successful_preparation(monkeypatch, capsys):
    names = []
    install_fake_model(monkeypatch, names.append)
    assert cli.main() == 0
    assert names == ["htdemucs"]
    assert "Model is cached" in capsys.readouterr().out
