"""
One-click launcher for the Study Planner app.

This starts the Flask development server AND automatically opens
your default browser to the login page.

Run with:
    python run.py
"""
import threading
import webbrowser
import os
import sys

from app import app

PORT = 5000
HOST = '127.0.0.1'


def open_browser():
    """Open the browser shortly after the server starts."""
    import time
    time.sleep(1.5)
    url = f'http://{HOST}:{PORT}'
    print(f'\nOpening browser at {url} ...')
    webbrowser.open(url)


if __name__ == '__main__':
    print('=' * 50)
    print('  STUDY PLANNER - Starting local server...')
    print('=' * 50)
    print(f'  Local URL:  http://{HOST}:{PORT}')
    print('  Press CTRL+C to stop the server') 
    print('=' * 50)          

    # Open the browser automatically after a short delay
    threading.Timer(1.5, open_browser).start()

    # Start the Flask server (auto-reload on code changes)
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug_mode, host=HOST, port=PORT)
