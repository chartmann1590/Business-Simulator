"""
Utility functions for safe printing and encoding handling.
"""
import sys
import io


def safe_print(*args, **kwargs):
    """
    Safely print text that may contain Unicode characters.
    Handles encoding errors gracefully by replacing problematic characters.
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # If encoding fails, encode with error handling and print
        output = io.StringIO()
        print(*args, file=output, **kwargs)
        text = output.getvalue()
        # Encode with error handling (replace problematic characters)
        encoded = text.encode(sys.stdout.encoding or 'utf-8', errors='replace')
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.write(b'\n')
        sys.stdout.buffer.flush()

