import shutil
import subprocess
import sys

from conftest import SCRIPTS, SKILL


def test_setup_names_install_fix_when_pyyaml_is_missing(root):
    shutil.copy(SKILL / 'templates/models.example.yaml', root / 'exam-bank/config/models.yaml')
    result = subprocess.run([sys.executable, '-S', str(SCRIPTS / 'eb.py'), 'setup', 'pmle'],
                            cwd=root, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 1
    assert 'pip install -r requirements.txt' in result.stderr
    assert 'Traceback' not in result.stderr
