"""Interruptible external media commands with disk-backed diagnostic output."""
import subprocess
import tempfile


def check_interrupted():
    try:
        from comfy.model_management import throw_exception_if_processing_interrupted
    except ImportError:
        return
    throw_exception_if_processing_interrupted()


def run_media(command, stdout_path=None):
    check_interrupted()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        try:
            while True:
                try:
                    code = process.wait(timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    check_interrupted()
            check_interrupted()
            stderr.seek(max(0, stderr.tell()-8192))
            error = stderr.read().decode('utf-8', errors='replace')
            if code:
                raise ValueError(f'Media decode/encode failed: {error.strip()}')
            stdout.seek(0)
            if stdout_path is not None:
                import shutil
                with open(stdout_path, 'wb') as destination:
                    shutil.copyfileobj(stdout, destination)
                return subprocess.CompletedProcess(command, code, '', error)
            return subprocess.CompletedProcess(command, code,
                stdout.read().decode('utf-8', errors='replace'), error)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
