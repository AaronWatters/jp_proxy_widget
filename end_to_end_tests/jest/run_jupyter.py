
'''
Run a Jupyter server and save the token URL in a file.
This script is left here for testing and maintenance.
The script is available as a string constant in '../src/jp_helpers.js'.
'''

# https://stackoverflow.com/questions/2804543/read-subprocess-stdout-line-by-line

import subprocess
import os
import signal

proc = None
cmd = None

JUPYTER_URL_PATH = './_jupyter_url.txt';

def run():
    global proc, cmd
    signal.signal(signal.SIGINT, exit_cleanly)
    signal.signal(signal.SIGTERM, exit_cleanly)
    cmd = ['jupyter', 'notebook', '--port=3000', '--no-browser']
    print ('Starting jupyter server: ' + repr(cmd))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    url_emitted = False
    try:
        for line in proc.stderr:
            print('Jupyter_server: ' + repr(line))
            line = str(line, encoding='utf8')
            if not url_emitted:
                # assume first line starting 'http:...' gives the start url with token similar to
                # http://localhost:3000/?token=793337e53c6ca95680623cb6556afdb32c7a1ee002f60119
                sline = line.strip()
                if sline.startswith('http://'):
                    with open(JUPYTER_URL_PATH, 'w') as f:
                        f.write(sline)
                    url_emitted = True
                    print ('Jupyter url emitted: ' + repr(sline))
                    print ('   saved to: ' + repr(JUPYTER_URL_PATH))
    finally:
        exit_cleanly()

def exit_cleanly(*arguments):
    print ('Stopping jupyter server', cmd)
    proc.kill()
    if os.path.exists(JUPYTER_URL_PATH):
        print('removing', JUPYTER_URL_PATH)
        os.remove(JUPYTER_URL_PATH)

if __name__=='__main__':
    run()
