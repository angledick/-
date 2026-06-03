import psutil, os, signal
for p in psutil.process_iter(['pid','name','cmdline']):
    try:
        cmd = ' '.join(p.info.get('cmdline') or [])
        if 'uvicorn' in cmd.lower() or ('python' in cmd.lower() and 'main:app' in cmd):
            print(f"Killing PID {p.info['pid']}: {cmd[:120]}")
            p.kill()
    except:
        pass
print("Done")
