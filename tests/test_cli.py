"Test buchfink cli app"
import contextlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from buchfink.cli import fetch_, init, report_


@contextlib.contextmanager
def cd(dir: Path):
    original_cwd = Path.cwd()
    try:
        os.chdir(dir)
        yield
    finally:
        os.chdir(original_cwd)


def test_run_on_ens_domain():
    "High level fetch+report integration test for adhoc accounts via ENS domain"
    runner = CliRunner()
    with TemporaryDirectory() as dir:
        with cd(dir):
            result = runner.invoke(init)
            assert result.exit_code == 0
            result = runner.invoke(fetch_, ['-e', 'coinyon.eth'])
            assert result.exit_code == 0
            result = runner.invoke(report_, ['-e', 'coinyon.eth', '-y', '2020'])
            assert result.exit_code == 0
            # We should test json output here
