"""Import this FIRST in a test module: sends uploads and emails to temp folders."""
import atexit
import os
import shutil
import tempfile

if "NGO_TEST_TMP" not in os.environ:
    _tmp = tempfile.mkdtemp(prefix="ngo_test_")
    os.environ["NGO_TEST_TMP"] = _tmp
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
    os.environ["OUTBOX_DIR"] = os.path.join(_tmp, "outbox")
    atexit.register(shutil.rmtree, _tmp, ignore_errors=True)
os.environ.setdefault("DB_NAME", "ngo_donation_test")
os.environ["SMTP_HOST"] = ""
