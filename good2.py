# language: Python 3.10+, file: john.py, target: Termux/Android, Selenium + Chrome headless
# v7.0: friend request + like + comment + share + review + follow + join group,
#       all multi-account, all from the same cookie pool.

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    WebDriverException, StaleElementReferenceException,
    ElementClickInterceptedException, TimeoutException, NoSuchElementException
)
import time, random, os, sys, csv, json, re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from collections import defaultdict

GREEN, YELLOW, RED, BLUE, CYAN, MAGENTA, WHITE = (
    '\033[92m','\033[93m','\033[91m','\033[94m','\033[96m','\033[95m','\033[97m')
BOLD, DIM, ITALIC, RESET = '\033[1m','\033[2m','\033[3m','\033[0m'
def fg(n): return f'\033[38;5;{n}m'
ORANGE, PINK, LIME, TEAL, INDIGO, GOLD, GRAY, DIMWHITE = (
    fg(208), fg(213), fg(154), fg(44), fg(99), fg(220), fg(244), fg(250))

COOKIE_STRING = "dbln=%7B%22100004068587319%22%3A%225nZHxoVJ%22%7D; datr=diXmaUh1_GvzxGp_bgpI1KUg; sb=diXmaTrK3wRed3iZDhnB_5jU; ps_l=1; ps_n=1; dpr=1.5303868055343628; c_user=100004068587319; fr=1tllZGDGMnlBIk5cw.AWdV3i9ffSSbesZQv-JfkQWVZQjsR_1u94AARdn94KG_szMfKcw.Bqx1gq..AAA.0.0.Bqx1gq.AWefo5PB4ys9B2LUOJrYrZMpSV0; xs=45%3Aa50HMg8-oswdvA%3A2%3A1791139292%3A-1%3A-1%3A%3AAczQRqMIwywf-_-V--TdcGMqZiRBMaSO0tnjSk1m-A; wd=470x909; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1791449141637%2C%22v%22%3A1%7D"

def parse_cookie_string(cs):
    out = {}
    for pair in cs.split("; "):
        if "=" not in pair: continue
        k, v = pair.split("=", 1)
        out[k.strip()] = v.strip()
    return out

EMBEDDED_COOKIES_DICT = parse_cookie_string(COOKIE_STRING)
EMBEDDED_UID = EMBEDDED_COOKIES_DICT.get("c_user", "100004068587319")
EMBEDDED_LABEL = "embedded:default"

def _storage_root():
    for c in ("/sdcard/fb_friender", "/storage/emulated/0/fb_friender", "/sdcard/Download/fb_friender"):
        try:
            os.makedirs(c, exist_ok=True)
            t = os.path.join(c, ".w")
            with open(t,"w") as f: f.write("x")
            os.remove(t); return c
        except Exception: continue
    fb = "/data/data/com.termux/files/home/fb_friender"
    os.makedirs(fb, exist_ok=True); return fb

ROOT         = _storage_root()
ACCOUNTS_DB  = os.path.join(ROOT, "accounts.json")
LOG_FILE     = os.path.join(ROOT, "log.csv")
SHOT_DIR     = os.path.join(ROOT, "shots")
HTML_DIR     = os.path.join(ROOT, "html")
os.makedirs(SHOT_DIR, exist_ok=True); os.makedirs(HTML_DIR, exist_ok=True)

PAGE_LOAD_MIN, PAGE_LOAD_MAX = 2.5, 5.0
POST_CLICK_MIN, POST_CLICK_MAX = 2.0, 4.0
ACCOUNT_COOLDOWN_MIN, ACCOUNT_COOLDOWN_MAX = 8.0, 18.0
LONG_PAUSE_EVERY = 8
LONG_PAUSE_MIN, LONG_PAUSE_MAX = 25.0, 60.0
W = 62

# ═══════════════════════ ACTIONS REGISTRY ═══════════════════════
# each entry: (menu_label, handler_name, list of extra params)
ACTIONS = {
    "1": {"key": "friend_request", "label": "Friend Request",         "params": []},
    "2": {"key": "like_post",      "label": "Like a Post",            "params": []},
    "3": {"key": "comment_post",   "label": "Comment on a Post",      "params": ["text"]},
    "4": {"key": "share_post",     "label": "Share Post to Profile",  "params": []},
    "5": {"key": "react_post",     "label": "React to a Post",        "params": ["reaction"]},
    "6": {"key": "review_page",    "label": "Review a Page",          "params": ["rating", "text"]},
    "7": {"key": "follow_user",    "label": "Follow a User",          "params": []},
    "8": {"key": "like_page",      "label": "Like a Page",            "params": []},
    "9": {"key": "follow_page",    "label": "Follow a Page",          "params": []},
    "10":{"key": "join_group",     "label": "Join a Group",           "params": []},
    "11":{"key": "save_post",      "label": "Save a Post",            "params": []},
}
ACTIONS_BY_KEY = {v["key"]: v for v in ACTIONS.values()}

# ── UI ──
def clear(): os.system('clear' if os.name == 'posix' else 'cls')
def hr(color=INDIGO, ch="─", w=W): print(f"{color}{ch * w}{RESET}")
def banner():
    art = [
        "  ███████╗ ██████╗ ██╗   ██╗██╗     ██████╗  ██████╗ ████████╗",
        "  ██╔════╝██╔═══██╗██║   ██║██║     ██╔══██╗██╔═══██╗╚══██╔══╝",
        "  █████╗  ██║   ██║██║   ██║██║     ██████╔╝██║   ██║   ██║   ",
        "  ██╔══╝  ██║   ██║██║   ██║██║     ██╔══██╗██║   ██║   ██║   ",
        "  ██║     ╚██████╔╝╚██████╔╝███████╗██████╔╝╚██████╔╝   ██║   ",
        "  ╚═╝      ╚═════╝  ╚═════╝ ╚══════╝╚═════╝  ╚═════╝    ╚═╝   ",
    ]
    print()
    for line in art: print(f"{ORANGE}{BOLD}{line}{RESET}")
    print(f"{DIMWHITE}           F A C E B O O K   A U T O - F R I E N D E R{RESET}")
    print(f"{GOLD}                          ✦ v7.0 ✦{RESET}")
    print()
def header_box(t):
    print(f"{TEAL}╭{'─' * (W - 2)}╮{RESET}")
    pad = (W - 2 - len(t)) // 2
    print(f"{TEAL}│{RESET}{' ' * pad}{BOLD}{WHITE}{t}{RESET}{' ' * (W - 2 - pad - len(t))}{TEAL}│{RESET}")
    print(f"{TEAL}╰{'─' * (W - 2)}╯{RESET}")
def kv(k, v, c=WHITE): print(f"  {GRAY}│{RESET} {DIMWHITE}{k:<22}{RESET} {c}{v}{RESET}")
def menu_row(n, t, h=""): print(f"  {GOLD}▸{RESET} {LIME}{BOLD}{n}{RESET}  {WHITE}{t}{RESET}" + (f"  {GRAY}· {h}{RESET}" if h else ""))
def ok(m):   print(f"  {GREEN}✓{RESET} {WHITE}{m}{RESET}")
def warn(m): print(f"  {YELLOW}⚠{RESET} {WHITE}{m}{RESET}")
def err(m):  print(f"  {RED}✗{RESET} {WHITE}{m}{RESET}")
def info(m): print(f"  {CYAN}ℹ{RESET} {DIMWHITE}{m}{RESET}")
def prompt(t, c=GOLD): return input(f"  {c}{BOLD}❯{RESET} {WHITE}{t}{RESET} ")
def pause(m="Press Enter"): input(f"\n  {GRAY}{ITALIC}{m}...{RESET}")
def ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def human_delay(a, b): time.sleep(random.uniform(a, b))
def normalize_url(l):
    l = l.strip()
    if not l: return None
    if "facebook.com" not in l: return None
    return l
def extract_target_uid(url):
    try:
        u = urlparse(url); q = parse_qs(u.query)
        if "id" in q: return q["id"][0]
        if "story_fbid" in q: return q.get("id", [""])[0]
        m = re.search(r"/(\d{6,})/?", u.path)
        if m: return m.group(1)
    except Exception: pass
    return None
def to_platform(url, platform):
    """Convert URL between www / m / mbasic."""
    if platform == "mbasic":
        if "m.facebook.com" in url: return url.replace("m.facebook.com", "mbasic.facebook.com")
        if "www.facebook.com" in url: return url.replace("www.facebook.com", "mbasic.facebook.com")
        return url
    if platform == "m":
        if "mbasic.facebook.com" in url: return url.replace("mbasic.facebook.com", "m.facebook.com")
        if "www.facebook.com" in url: return url.replace("www.facebook.com", "m.facebook.com")
        return url
    return url

# ═══════════════════════ ACCOUNT DB ═══════════════════════
def _embedded_entry():
    now = ts()
    return {
        "uid": EMBEDDED_UID, "identifier": EMBEDDED_LABEL, "password": "",
        "cookie": COOKIE_STRING, "cookies_dict": EMBEDDED_COOKIES_DICT,
        "added_at": now, "last_used": now, "note": "built-in",
        "status": "unknown", "embedded": True,
    }
def _ensure_embedded(accounts):
    accounts = [a for a in accounts if a.get("uid") != EMBEDDED_UID]
    accounts.insert(0, _embedded_entry())
    return accounts
def load_accounts(seed_embedded=True):
    accounts = []
    if os.path.exists(ACCOUNTS_DB):
        try:
            with open(ACCOUNTS_DB, "r", encoding="utf-8") as f:
                data = json.load(f)
            accounts = data if isinstance(data, list) else []
        except Exception: accounts = []
    if seed_embedded:
        accounts = _ensure_embedded(accounts); save_accounts(accounts)
    return accounts
def save_accounts(accounts):
    try:
        with open(ACCOUNTS_DB, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
    except Exception as e: err(f"Save failed: {e}")
def add_or_update_account(identifier, password, cookie_string, uid, cookies_dict, note=""):
    accounts = load_accounts(seed_embedded=False)
    now = ts()
    accounts = [a for a in accounts if a.get("uid") != uid]
    accounts.append({
        "uid": uid, "identifier": identifier, "password": password,
        "cookie": cookie_string, "cookies_dict": cookies_dict,
        "added_at": now, "last_used": now, "note": note,
        "status": "ready", "embedded": False,
    })
    accounts = _ensure_embedded(accounts); save_accounts(accounts)
def mark_account_used(uid, status="ready", note=""):
    accounts = load_accounts(seed_embedded=False)
    for a in accounts:
        if a.get("uid") == uid:
            a["last_used"] = ts(); a["status"] = status
            if note: a["note"] = note
            break
    accounts = _ensure_embedded(accounts); save_accounts(accounts)
def delete_account(uid):
    accounts = load_accounts(seed_embedded=False)
    accounts = [a for a in accounts if a.get("uid") != uid]
    accounts = _ensure_embedded(accounts); save_accounts(accounts)

# ═══════════════════════ BOT ═══════════════════════
class FacebookBot:
    def __init__(self):
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1080,1920")
        opts.add_argument("user-agent=Mozilla/5.0 (Linux; Android 13; SM-S918B) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--lang=en-US")
        opts.add_argument("--blink-settings=imagesEnabled=false")
        service = Service(executable_path='/data/data/com.termux/files/usr/bin/chromedriver')
        try:
            self.bot = webdriver.Chrome(service=service, options=opts)
            self.bot.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": (
                    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                    "window.chrome={runtime:{}};"
                    "Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});"
                    "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
                )
            })
        except Exception as e:
            err(f"Browser start failed: {e}"); raise
        new = not os.path.exists(LOG_FILE)
        self.log_fh = open(LOG_FILE, "a", newline="", encoding="utf-8")
        self.log_writer = csv.writer(self.log_fh)
        if new: self.log_writer.writerow(["timestamp","uid","target_url","status","note"])

    def log(self, uid, t, s, n=""):
        try: self.log_writer.writerow([ts(), uid, t, s, n]); self.log_fh.flush()
        except Exception: pass

    def reset_cookies(self):
        try: self.bot.delete_all_cookies()
        except Exception: pass
        try: self.bot.execute_cdp_cmd("Network.clearBrowserCookies", {})
        except Exception: pass

    # ── cookie injection ──
    def inject_cookies_dict(self, cookies_dict):
        self.reset_cookies()
        try: self.bot.get("https://m.facebook.com/")
        except WebDriverException: return False
        human_delay(1.5, 2.5)
        n = 0
        for name, value in (cookies_dict or {}).items():
            for dom in (".facebook.com", "m.facebook.com", ".m.facebook.com"):
                try:
                    self.bot.add_cookie({"name": name, "value": value, "domain": dom, "path": "/"})
                    n += 1; break
                except Exception: continue
        if n == 0: return False
        try: self.bot.refresh()
        except WebDriverException: return False
        human_delay(2.5, 4.0)
        try:
            cur = self.bot.current_url.lower()
            if "login" in cur or "checkpoint" in cur: return False
        except Exception: pass
        return True

    # ── generic element finders ──
    def _find_first(self, xpaths, timeout=12):
        end = time.time() + timeout
        while time.time() < end:
            for xp in xpaths:
                try:
                    for el in self.bot.find_elements(By.XPATH, xp):
                        if el.is_displayed(): return el
                except Exception: continue
            time.sleep(0.4)
        return None

    def _find_first_text(self, texts, timeout=10):
        xs = []
        for t in texts:
            xs += [
                f"//a[normalize-space(text())='{t}']",
                f"//button[normalize-space(text())='{t}']",
                f"//span[normalize-space(text())='{t}']",
                f"//div[@role='button' and normalize-space(.)='{t}']",
            ]
        return self._find_first(xs, timeout=timeout)

    def _human_click(self, el):
        try:
            self.bot.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", el)
            time.sleep(random.uniform(0.5, 1.0))
            try: ActionChains(self.bot).move_to_element(el).perform()
            except Exception: pass
            time.sleep(random.uniform(0.15, 0.4))
            try: el.click()
            except (StaleElementReferenceException, ElementClickInterceptedException):
                self.bot.execute_script("arguments[0].click();", el)
            time.sleep(random.uniform(POST_CLICK_MIN, POST_CLICK_MAX))
            return True
        except Exception:
            return False

    def _type_human(self, el, text):
        try:
            el.click(); time.sleep(random.uniform(0.15, 0.4))
            try:
                el.send_keys(Keys.CONTROL, "a"); el.send_keys(Keys.DELETE)
            except Exception: pass
            for ch in str(text):
                el.send_keys(ch)
                time.sleep(random.uniform(0.03, 0.10))
            return True
        except Exception:
            try:
                self.bot.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input',{bubbles:true}));",
                    el, text)
                return True
            except Exception:
                return False

    def _page_body(self, limit=6000):
        try:
            return (self.bot.execute_script(
                f"return document.body ? document.body.innerText.slice(0,{limit}) : '';") or "").lower()
        except Exception:
            return ""

    def _check_restriction(self):
        b = self._page_body()
        if any(m in b for m in ("add a phone","add an email","confirm your identity",
                                "temporarily restricted","security check",
                                "temporarily locked","detected suspicious","feature isn't available",
                                "limited account")):
            return "restricted"
        if "you're temporarily blocked" in b or "we limit how often" in b:
            return "blocked"
        return None

    def _dump_debug(self, uid, tag):
        try:
            fp = os.path.join(HTML_DIR, f"{tag}_{uid}.html")
            with open(fp, "w", encoding="utf-8") as f: f.write(self.bot.page_source or "")
        except Exception: fp = ""
        try:
            sp = os.path.join(SHOT_DIR, f"{tag}_{uid}.png")
            self.bot.save_screenshot(sp)
        except Exception: sp = ""
        return fp, sp

    # ── interactive login ──
    def login_with_credentials(self, identifier, password):
        self.reset_cookies()
        try: self.bot.get("https://m.facebook.com/login/")
        except WebDriverException as e:
            return {"status": "error", "note": f"nav: {e.__class__.__name__}"}
        human_delay(2.5, 4.5)
        ef = self._find_first([
            "//input[@name='email']","//input[@id='m_login_email']",
            "//input[@type='email']","//input[@type='text' and contains(@name,'email')]",
            "//input[contains(@placeholder,'Email') or contains(@placeholder,'Phone')]",
        ], timeout=18)
        if ef is None: return {"status": "error", "note": "email-field-not-found"}
        if not self._type_human(ef, identifier): return {"status": "error", "note": "type-email-failed"}
        human_delay(0.5, 1.2)
        pf = self._find_first(["//input[@name='pass']","//input[@id='m_login_password']","//input[@type='password']"], 10)
        if pf is None: return {"status": "error", "note": "password-field-not-found"}
        if not self._type_human(pf, password): return {"status": "error", "note": "type-password-failed"}
        human_delay(0.6, 1.4)
        sub = self._find_first([
            "//button[@name='login']","//input[@name='login'][@type='submit']",
            "//button[@type='submit']","//button[contains(.,'Log in') or contains(.,'Login')]",
        ], 10)
        if sub is None:
            try: pf.send_keys(Keys.RETURN)
            except Exception: return {"status": "error", "note": "submit-not-found"}
        else:
            if not self._human_click(sub): return {"status": "error", "note": "click-failed"}
        human_delay(4.0, 7.0)
        try: cur = self.bot.current_url.lower()
        except Exception: cur = ""
        bl = self._page_body(8000)
        if ("password" in bl and ("incorrect" in bl or "wrong" in bl or "invalid" in bl)) \
                or "password that you've entered is incorrect" in bl:
            return {"status": "bad_password", "note": "wrong-password"}
        if any(k in bl for k in ("enter the code","login code","two-factor","two factor",
                                 "authentication code","we sent a code")):
            return {"status": "2fa", "note": "code-required"}
        if "checkpoint" in cur or any(k in bl for k in (
            "confirm your identity","security check","verify your identity","we need to confirm")):
            return {"status": "checkpoint", "note": "identity-verify"}
        if "continue as" in bl and "not you" in bl:
            c = self._find_first(["//button[contains(.,'Continue')]","//div[@role='button' and contains(.,'Continue')]","//a[contains(.,'Continue')]"], 6)
            if c is not None:
                self._human_click(c); human_delay(3.0, 5.0)
        bl = self._page_body(8000)
        logged = any(k in bl for k in ("news feed","what's on your mind","home","friends","notifications","your profile")) \
                 or ("login" not in self.bot.current_url.lower() and "checkpoint" not in cur)
        if not logged: return {"status": "error", "note": f"unknown:{bl[:60]}"}
        cookies = {}
        try:
            for ck in self.bot.get_cookies(): cookies[ck["name"]] = ck["value"]
        except Exception: pass
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        uid = cookies.get("c_user", "") or ""
        if not cookie_str or not uid: return {"status": "error", "note": "no-cookies"}
        return {"status": "ok", "uid": uid, "cookie_string": cookie_str,
                "cookies_dict": cookies, "note": "login-ok"}

    # ── restriction state ──
    def detect_account_state(self):
        try: self.bot.get("https://m.facebook.com/")
        except WebDriverException: return "logged_out", "nav-fail"
        human_delay(2.0, 3.5)
        u = self.bot.current_url.lower()
        if "login" in u: return "logged_out", "redirect-login"
        if "checkpoint" in u: return "checkpoint", "redirect-checkpoint"
        bl = self._page_body()
        for m in ("confirm your identity","we need to confirm","add a phone number to your account",
                  "add an email to your account","temporarily restricted","before you can use facebook",
                  "please confirm your identity","security check","temporarily locked",
                  "detected suspicious","feature isn't available","limited account"):
            if m in bl: return "restricted", m[:40]
        if "log in" in bl and "sign up" in bl and len(bl) < 800: return "logged_out", "login-form"
        home = any(k in bl for k in ("news feed","what's on your mind","home","friends","notifications"))
        if not home: return "logged_out", "no-home"
        for m in ("complete your profile","add friends to get started","find friends","no posts yet"):
            if m in bl: return "restricted", f"fresh:{m[:25]}"
        return "ready", "home-ok"

    # ═══════════════════════ ACTION HANDLERS ═══════════════════════
    # each returns (status, note)

    def _check_sent_generic(self, success_markers):
        b = self._page_body(4000)
        r = self._check_restriction()
        if r: return False, r
        for m in success_markers:
            if m in b: return True, f"marker:{m}"
        return False, "unconfirmed"

    def action_friend_request(self, target_url, params):
        tuid = extract_target_uid(target_url) or ""
        if not tuid: return "error", "no-uid-in-url"
        for plat in ("mbasic", "m"):
            url = f"https://{plat}.facebook.com/profile.php?id={tuid}" if plat=="mbasic" \
                  else f"https://m.facebook.com/profile.php?id={tuid}"
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.0)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"
            b = self._page_body()
            if "this content isn't available" in b or "content not found" in b:
                return "not_found", "unavailable"
            if "cancel request" in b or "request sent" in b:
                return "requested", "already-pending"
            btn = self._find_first([
                "//a[contains(@href,'/friends/add/')]",
                "//a[contains(@href,'add_friend')]",
                "//a[contains(@href,'/add_friend/confirm')]",
            ], 10)
            if btn is None:
                btn = self._find_first_text(["Add Friend", "Add friend"], 8)
            if btn is not None and self._human_click(btn):
                ok_, note = self._check_sent_generic(["cancel request","request sent","friend request sent"])
                if ok_: return "added", f"{plat}-{note}"
            # direct endpoint fallback on mbasic
            if plat == "mbasic":
                try:
                    self.bot.get(f"https://mbasic.facebook.com/add_friend/confirm/?id={tuid}")
                    human_delay(2.0, 3.5)
                    cb = self._find_first_text(["Add Friend","Confirm","Add friend"], 6)
                    if cb is not None and self._human_click(cb):
                        human_delay(2.0, 3.0)
                    ok_, note = self._check_sent_generic(["cancel request","request sent"])
                    if ok_: return "added", f"direct-{note}"
                except Exception: pass
        return "error", "all-paths-failed"

    def action_like_post(self, target_url, params):
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.5)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"
            b = self._page_body()
            if "you already like this" in b or "unlike" in b and "like" not in b.split("unlike")[0][-20:]:
                pass  # ambiguous — keep going
            # find Like link
            like = self._find_first([
                "//a[normalize-space(text())='Like']",
                "//a[contains(@href,'/reactions/') or contains(@href,'like')]",
                "//span[normalize-space(text())='Like']",
                "//div[@role='button' and normalize-space(.)='Like']",
                "//button[normalize-space(text())='Like']",
            ], 10)
            if like is None and plat == "mbasic":
                # mbasic post page always has a "Like" link with a numeric like id
                like = self._find_first_text(["Like"], 8)
            if like is not None and self._human_click(like):
                human_delay(2.0, 3.5)
                b2 = self._page_body()
                if "unlike" in b2 or "you and" in b2 or "likes" in b2 and "like" not in b2.split("likes")[0][-30:]:
                    return "liked", f"{plat}-clicked"
                # treat presence of "Unlike" text as success
                if self._find_first_text(["Unlike"], 3) is not None:
                    return "liked", f"{plat}-confirmed"
                return "liked", f"{plat}-clicked-unconfirmed"
        return "error", "like-button-not-found"

    def action_comment_post(self, target_url, params):
        text = params.get("text", "").strip()
        if not text: return "error", "no-text"
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(3.0, 5.0)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"

            box = self._find_first([
                "//textarea[contains(@name,'comment')]",
                "//textarea[contains(@placeholder,'comment') or contains(@placeholder,'Comment')]",
                "//textarea",
                "//input[@type='text' and contains(@name,'comment')]",
                "//div[@role='textbox' and contains(@aria-label,'comment')]",
            ], 8)

            if box is None:
                # click "Comment" link first to reveal box
                cl = self._find_first_text(["Comment","Write a comment"], 6)
                if cl is not None and self._human_click(cl):
                    human_delay(1.5, 2.5)
                    box = self._find_first([
                        "//textarea","//div[@role='textbox']",
                    ], 6)

            if box is None: continue
            if not self._type_human(box, text): continue
            human_delay(0.8, 1.6)

            sub = self._find_first([
                "//input[@type='submit' and (contains(@value,'Comment') or contains(@value,'Post'))]",
                "//button[contains(.,'Comment') or contains(.,'Post')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
            ], 6)
            if sub is not None:
                if not self._human_click(sub): continue
            else:
                try: box.send_keys(Keys.RETURN)
                except Exception: continue

            human_delay(3.0, 5.0)
            b2 = self._page_body(6000)
            if text.lower()[:40] in b2:
                return "commented", f"{plat}-text-visible"
            if "comment" in b2 and ("posted" in b2 or "sent" in b2):
                return "commented", f"{plat}-post-confirm"
            return "commented", f"{plat}-unconfirmed"
        return "error", "comment-box-not-found"

    def action_share_post(self, target_url, params):
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.5)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"

            sh = self._find_first([
                "//a[normalize-space(text())='Share']",
                "//a[contains(@href,'sharer')]",
                "//a[contains(@href,'/share')]",
                "//span[normalize-space(text())='Share']",
                "//div[@role='button' and normalize-space(.)='Share']",
            ], 10)
            if sh is None: continue
            if not self._human_click(sh): continue
            human_delay(2.5, 4.5)

            # land on share dialog or sharer page — pick "Share Now" / "Share to Feed" / "Post"
            for label in ("Share Now", "Share now", "Share to Feed", "Share on your Timeline",
                          "Share on your timeline", "Post", "Share"):
                btn = self._find_first_text([label], 4)
                if btn is not None and self._human_click(btn):
                    human_delay(3.0, 5.0)
                    b2 = self._page_body(5000)
                    if "shared" in b2 or "post" in b2 and ("timeline" in b2 or "feed" in b2 or "profile" in b2):
                        return "shared", f"{plat}-{label}"
                    if self.bot.current_url.lower() != url.lower():
                        return "shared", f"{plat}-{label}-nav"
                    return "shared", f"{plat}-{label}-clicked"
        return "error", "share-flow-not-found"

    def action_react_post(self, target_url, params):
        reaction = params.get("reaction", "love").lower()
        reaction_cap = reaction.capitalize()
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.5)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"

            # 1. hover / click the Like button to expand reactions
            like = self._find_first_text(["Like"], 8)
            if like is None: continue
            try:
                ActionChains(self.bot).move_to_element(like).perform()
            except Exception: pass
            time.sleep(random.uniform(0.6, 1.2))

            # 2. click the reaction by name
            react = self._find_first([
                f"//*[@aria-label='{reaction_cap}']",
                f"//*[contains(@aria-label,'{reaction_cap}')]",
                f"//span[normalize-space(text())='{reaction_cap}']",
                f"//div[@role='button' and normalize-space(.)='{reaction_cap}']",
            ], 6)
            if react is None and plat == "mbasic":
                # mbasic direct like reaction URLs: /reactions/picker/?ft_ent_identifier=<postid>&reaction_type=N
                # simpler: just click Like (thumbs-up) as fallback
                if self._human_click(like):
                    human_delay(2.0, 3.5)
                    return "reacted", f"{plat}-fallback-like"
                continue
            if react is not None and self._human_click(react):
                human_delay(2.0, 3.5)
                return "reacted", f"{plat}-{reaction}"
        return "error", "reaction-not-found"

    def action_save_post(self, target_url, params):
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.5)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"
            # find "Save" or "..." → "Save post"
            save = self._find_first([
                "//a[normalize-space(text())='Save']",
                "//a[normalize-space(text())='Save post']",
                "//span[normalize-space(text())='Save post']",
                "//div[@role='button' and normalize-space(.)='Save']",
            ], 6)
            if save is None:
                more = self._find_first_text(["More","...","More options"], 4)
                if more is not None and self._human_click(more):
                    human_delay(1.2, 2.0)
                    save = self._find_first_text(["Save post","Save"], 4)
            if save is not None and self._human_click(save):
                human_delay(2.0, 3.5)
                return "saved", f"{plat}-clicked"
        return "error", "save-not-found"

    def action_review_page(self, target_url, params):
        rating = str(params.get("rating", "5"))
        text = params.get("text", "").strip()
        if not text: return "error", "no-text"
        # try mbasic first, then m.facebook
        for plat in ("mbasic", "m"):
            base = to_platform(target_url, plat).rstrip("/")
            # navigate to reviews sub-page
            candidates = [base + "/reviews", base + "/reviews/", base]
            for u in candidates:
                try: self.bot.get(u)
                except WebDriverException: continue
                human_delay(3.0, 5.0)
                r = self._check_restriction()
                if r: return r, f"{r}-{plat}"

                # click "Write a review" / "Write Review"
                wr = self._find_first_text(["Write a review","Write Review","Write review","Write a Review",
                                            "Recommend","Reviews"], 6)
                if wr is None: continue
                if not self._human_click(wr): continue
                human_delay(2.0, 3.5)

                # rating stars — try aria-label "N stars", title "N stars", or 5 radio inputs
                star = self._find_first([
                    f"//*[@aria-label='{rating} stars']",
                    f"//*[@aria-label='{rating} star']",
                    f"//*[@title='{rating} stars']",
                    f"//*[@title='{rating} star']",
                    f"//input[@type='radio'][@value='{rating}']",
                    f"//div[@role='radio'][@aria-label='{rating} stars']",
                    f"//span[normalize-space(text())='{rating}']",
                ], 6)
                if star is not None:
                    self._human_click(star)
                    human_delay(0.8, 1.5)

                # textarea
                box = self._find_first([
                    "//textarea",
                    "//div[@role='textbox']",
                ], 6)
                if box is None: continue
                if not self._type_human(box, text): continue
                human_delay(0.8, 1.5)

                # submit
                sub = self._find_first([
                    "//button[contains(.,'Submit') or contains(.,'Post') or contains(.,'Publish')]",
                    "//input[@type='submit']",
                    "//div[@role='button' and (contains(.,'Submit') or contains(.,'Post'))]",
                ], 6)
                if sub is None: continue
                if not self._human_click(sub): continue
                human_delay(3.0, 5.0)

                b2 = self._page_body(6000)
                if "review" in b2 and ("posted" in b2 or "submitted" in b2 or "thanks" in b2):
                    return "reviewed", f"{plat}-confim-text"
                if text.lower()[:40] in b2:
                    return "reviewed", f"{plat}-visible"
                return "reviewed", f"{plat}-unconfirmed"
        return "error", "review-flow-failed"

    def action_follow_user(self, target_url, params):
        return self._follow_or_like(target_url, kind="follow_user")

    def action_follow_page(self, target_url, params):
        return self._follow_or_like(target_url, kind="follow_page")

    def action_like_page(self, target_url, params):
        return self._follow_or_like(target_url, kind="like_page")

    def _follow_or_like(self, target_url, kind):
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.5)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"
            b = self._page_body()
            if "this content isn't available" in b: return "not_found", "unavailable"

            if kind == "follow_user":
                if "following" in b or "unfollow" in b:
                    return "requested", "already-following"
                btn = self._find_first_text(["Follow"], 8)
                if btn is None: continue
                if self._human_click(btn):
                    human_delay(2.0, 3.5)
                    if self._find_first_text(["Following","Unfollow"], 4) is not None:
                        return "followed", f"{plat}-confirmed"
                    return "followed", f"{plat}-clicked"

            elif kind == "follow_page":
                if "following" in b or "unfollow" in b or "unlike" in b:
                    return "requested", "already-following/liked"
                btn = self._find_first_text(["Follow"], 8)
                if btn is None: continue
                if self._human_click(btn):
                    human_delay(2.0, 3.5)
                    if self._find_first_text(["Following","Unfollow","Unlike"], 4) is not None:
                        return "followed", f"{plat}-confirmed"
                    return "followed", f"{plat}-clicked"

            elif kind == "like_page":
                if "liked" in b or "unlike" in b:
                    return "requested", "already-liked"
                btn = self._find_first_text(["Like"], 8)
                if btn is None:
                    btn = self._find_first([
                        "//a[contains(@href,'/pages/like')]",
                        "//a[contains(@href,'like_profile_section')]",
                    ], 6)
                if btn is None: continue
                if self._human_click(btn):
                    human_delay(2.0, 3.5)
                    if self._find_first_text(["Liked","Unlike"], 4) is not None:
                        return "liked", f"{plat}-confirmed"
                    return "liked", f"{plat}-clicked"
        return "error", f"{kind}-button-not-found"

    def action_join_group(self, target_url, params):
        for plat in ("mbasic", "m"):
            url = to_platform(target_url, plat)
            try: self.bot.get(url)
            except WebDriverException: continue
            human_delay(2.5, 4.5)
            r = self._check_restriction()
            if r: return r, f"{r}-{plat}"
            b = self._page_body()
            if "pending" in b or "membership pending" in b:
                return "requested", "pending-approval"
            if "member" in b and "join" not in b.split("member")[0][-20:]:
                return "requested", "already-member"
            btn = self._find_first([
                "//a[contains(@href,'join_group')]",
                "//a[normalize-space(text())='Join Group']",
                "//a[normalize-space(text())='Join group']",
                "//span[normalize-space(text())='Join Group']",
                "//div[@role='button' and contains(.,'Join')]",
            ], 10)
            if btn is None: continue
            if self._human_click(btn):
                human_delay(2.5, 4.5)
                # sometimes a confirm dialog appears
                for label in ("Join Group","Join group","Join","Confirm"):
                    c = self._find_first_text([label], 3)
                    if c is not None and self._human_click(c):
                        human_delay(2.0, 3.0); break
                b2 = self._page_body()
                if "member" in b2 or "pending" in b2 or "joined" in b2:
                    return "joined", f"{plat}-confirmed"
                return "joined", f"{plat}-clicked"
        return "error", "join-button-not-found"

    # ── dispatcher ──
    def dispatch_action(self, action_key, target_url, params):
        handlers = {
            "friend_request": self.action_friend_request,
            "like_post":      self.action_like_post,
            "comment_post":   self.action_comment_post,
            "share_post":     self.action_share_post,
            "react_post":     self.action_react_post,
            "save_post":      self.action_save_post,
            "review_page":    self.action_review_page,
            "follow_user":    self.action_follow_user,
            "follow_page":    self.action_follow_page,
            "like_page":      self.action_like_page,
            "join_group":     self.action_join_group,
        }
        h = handlers.get(action_key)
        if h is None: return "error", "unknown-action"
        try:
            return h(target_url, params or {})
        except Exception as e:
            return "error", f"{e.__class__.__name__}:{str(e)[:30]}"

    # ── multi-account action runner ──
    def run_action_multi(self, action_key, target_url, params):
        label = ACTIONS_BY_KEY.get(action_key, {}).get("label", action_key)
        accounts = load_accounts()
        if not accounts:
            warn("No accounts saved."); return

        clear(); banner()
        header_box(f"RUN · {label.upper()}")
        print()
        kv("Action", action_key, GOLD)
        kv("Target", target_url[:W-10], DIMWHITE)
        kv("Accounts", str(len(accounts)), GOLD)
        for k, v in (params or {}).items():
            kv(f"  {k}", str(v)[:40], DIMWHITE)
        print(); hr(); pause("Press Enter to launch")

        results = defaultdict(int)
        start = time.time()
        usable = []

        print(); header_box("PRE-CHECK"); print()
        for a in accounts:
            uid = a.get("uid", "?")
            is_emb = a.get("embedded", False)
            tag = f"{DIM}(embedded){RESET}" if is_emb else ""
            ck = a.get("cookies_dict") or {}
            if not ck:
                print(f"  {RED}✗{RESET} {WHITE}{uid:<20}{RESET} {tag} {DIM}no cookies{RESET}")
                continue
            if not self.inject_cookies_dict(ck):
                results["expired"] += 1
                print(f"  {RED}✗{RESET} {WHITE}{uid:<20}{RESET} {tag} {DIM}cookie rejected{RESET}")
                continue
            state, note = self.detect_account_state()
            if state == "ready":
                usable.append(a)
                print(f"  {GREEN}✓{RESET} {WHITE}{uid:<20}{RESET} {tag} {DIM}ready{RESET}")
            elif state == "restricted":
                results["restricted"] += 1
                print(f"  {YELLOW}⚠{RESET} {WHITE}{uid:<20}{RESET} {tag} {DIM}restricted{RESET}")
                mark_account_used(uid, "restricted", note)
            elif state == "checkpoint":
                results["blocked"] += 1
                print(f"  {YELLOW}⚠{RESET} {WHITE}{uid:<20}{RESET} {tag} {DIM}checkpoint{RESET}")
                mark_account_used(uid, "checkpoint", note)
            else:
                results["expired"] += 1
                print(f"  {RED}✗{RESET} {WHITE}{uid:<20}{RESET} {tag} {DIM}{state}{RESET}")
                mark_account_used(uid, "expired", note)

        print()
        info(f"usable: {len(usable)} / {len(accounts)}")
        if not usable: warn("Nothing to do."); pause(); return
        pause("Press Enter to launch with usable accounts")

        for idx, entry in enumerate(usable, 1):
            uid = entry.get("uid", "?")
            is_emb = entry.get("embedded", False)
            tag = f" {CYAN}[embedded]{RESET}" if is_emb else ""
            print()
            print(f"  {TEAL}╭{'─' * (W - 2)}╮{RESET}")
            head = f"[{idx}/{len(usable)}]  uid {uid}"
            pad = (W - 2 - len(head)) // 2
            print(f"  {TEAL}│{RESET}{' ' * pad}{BOLD}{GOLD}{head}{RESET}{' ' * (W - 2 - pad - len(head))}{TEAL}│{RESET}")
            print(f"  {TEAL}╰{'─' * (W - 2)}╯{RESET}{tag}")

            if not self.inject_cookies_dict(entry.get("cookies_dict") or {}):
                results["expired"] += 1
                err("Cookie rejected now — skipping")
                continue
            ok("Session loaded"); human_delay(1.0, 2.0)

            status, note = self.dispatch_action(action_key, target_url, params)
            results[status] += 1
            self.log(uid, target_url, f"{action_key}:{status}", note)
            mark_account_used(uid, status, note)

            color = GREEN if status in ("added","liked","commented","shared","reacted",
                                        "saved","reviewed","followed","joined") \
                    else YELLOW if status in ("requested","already_friends","follow_only") \
                    else RED
            print(f"  {color}{status}{RESET} {DIM}({note}){RESET}")

            elapsed = time.time() - start
            eta = (elapsed / idx) * (len(usable) - idx) if idx else 0
            fill = int(30 * idx / len(usable))
            bar = f"{GREEN}{'█' * fill}{RESET}{GRAY}{'░' * (30 - fill)}{RESET}"
            print(f"\n  {bar}  {DIMWHITE}{idx}/{len(usable)}{RESET}  {DIM}eta {int(eta)}s{RESET}  "
                  f"{GREEN}ok={sum(results[k] for k in ('added','liked','commented','shared','reacted','saved','reviewed','followed','joined'))}{RESET}  "
                  f"{RED}err={results['error']+results['expired']+results['blocked']}{RESET}")

            if idx < len(usable):
                w = random.uniform(ACCOUNT_COOLDOWN_MIN, ACCOUNT_COOLDOWN_MAX)
                print(f"  {GRAY}⏳ cooldown {int(w)}s…{RESET}")
                time.sleep(w)
            if idx % LONG_PAUSE_EVERY == 0 and idx < len(usable):
                p = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
                print(f"  {YELLOW}☕ pause {int(p)}s…{RESET}")
                time.sleep(p)

        clear(); banner()
        header_box("FINAL SUMMARY")
        print()
        kv("Action", action_key, GOLD)
        kv("Target", target_url[:W-10], DIMWHITE)
        kv("Accounts total", str(len(accounts)), WHITE)
        kv("Usable", str(len(usable)), GREEN)
        print()
        for k in sorted(results.keys()):
            v = results[k]
            c = GREEN if k in ("added","liked","commented","shared","reacted","saved","reviewed","followed","joined") \
                else YELLOW if k in ("requested","restricted") else RED
            kv(k, str(v), c)
        print(); hr(); kv("Log", LOG_FILE, DIMWHITE); hr(); pause()

    def close(self):
        try:
            if self.log_fh: self.log_fh.close()
        except Exception: pass
        try: self.bot.quit()
        except Exception: pass

# ═══════════════════════ FLOWS ═══════════════════════
def add_account_flow(bot):
    clear(); banner(); header_box("ADD ACCOUNT · LOGIN"); print()
    info("Enter email or phone and password."); print()
    ident = prompt("Email or phone").strip()
    if not ident: warn("Cancelled."); return
    pw = prompt("Password").strip()
    if not pw: warn("Cancelled."); return
    print(); info("Logging in…"); print()
    r = bot.login_with_credentials(ident, pw)
    st = r.get("status")
    if st == "ok":
        uid = r.get("uid",""); cs = r.get("cookie_string",""); ck = r.get("cookies_dict",{})
        add_or_update_account(ident, pw, cs, uid, ck, note="login-ok")
        ok(f"Logged in. uid = {uid}")
        info(f"Saved to {ACCOUNTS_DB}")
        st_, note_ = bot.detect_account_state()
        kv("State", st_, GREEN if st_ == "ready" else YELLOW)
        mark_account_used(uid, st_, note_)
    elif st == "bad_password": err("Wrong password.")
    elif st == "2fa": warn("2FA required — log in manually, then retry.")
    elif st == "checkpoint": warn("FB wants identity verification.")
    else: err(f"Login failed — {r.get('note','')}")
    pause()

def list_accounts_flow():
    clear(); banner(); header_box("SAVED ACCOUNTS"); print()
    accounts = load_accounts()
    if not accounts: warn("No accounts."); pause(); return
    for i, a in enumerate(accounts, 1):
        uid = a.get("uid","?"); ident = a.get("identifier","?")
        status = a.get("status","?"); note = a.get("note","")
        emb = f" {CYAN}[built-in]{RESET}" if a.get("embedded") else ""
        c = GREEN if status in ("ready","added","liked","commented","shared","reacted","saved","reviewed","followed","joined") \
            else YELLOW if status in ("restricted","checkpoint","unknown","requested") else RED
        print(f"  {GOLD}{i:>3}.{RESET} {WHITE}{uid:<20}{RESET}  {DIM}{ident:<28}{RESET}  {c}{status}{RESET}{emb}")
        if note: print(f"       {GRAY}{note[:60]}{RESET}")
    print(); print(f"  {GRAY}total: {len(accounts)}{RESET}"); print(); hr()
    menu_row("d <n>", "delete account number n")
    menu_row("c",     "clear all (keeps built-in)")
    choice = prompt("Action (blank to return)").strip().lower()
    if choice == "c":
        if prompt("Type YES to confirm wipe").strip() == "YES":
            accs = load_accounts(seed_embedded=False)
            accs = [a for a in accs if a.get("embedded")]
            save_accounts(_ensure_embedded(accs)); ok("Wiped.")
    elif choice.startswith("d "):
        try:
            n = int(choice.split()[1])
            if 1 <= n <= len(accounts):
                t = accounts[n-1]
                if t.get("embedded"): err("Built-in protected.")
                else: delete_account(t.get("uid")); ok(f"Deleted {t.get('uid')}.")
            else: err("Out of range.")
        except Exception: err("Bad format.")
    pause()

def run_action_flow(bot):
    """Pick action → collect params → dispatch."""
    while True:
        clear(); banner(); header_box("RUN ACTION"); print()
        for k in sorted(ACTIONS.keys(), key=lambda x: int(x)):
            menu_row(k, ACTIONS[k]["label"])
        menu_row("0", "Back")
        print(); hr()
        c = prompt("Choose action").strip()
        if c == "0" or not c: return
        if c not in ACTIONS: err("Invalid."); time.sleep(1); continue
        a = ACTIONS[c]

        clear(); banner(); header_box(f"ACTION · {a['label'].upper()}"); print()
        info("Common target URLs:")
        info("  profile:  https://www.facebook.com/profile.php?id=61594...")
        info("  post:     https://www.facebook.com/username/posts/123...")
        info("  page:     https://www.facebook.com/somepagename")
        info("  group:    https://www.facebook.com/groups/1234567890")
        print()

        target = normalize_url(prompt("Target URL").strip())
        if not target: err("Invalid URL."); time.sleep(1.5); continue

        params = {}
        for p in a["params"]:
            if p == "text":
                params["text"] = prompt("Comment/Review text").strip()
                if not params["text"]: err("Empty text."); time.sleep(1.5); break
            elif p == "rating":
                r = prompt("Rating 1-5").strip()
                params["rating"] = r if r in "12345" else "5"
            elif p == "reaction":
                r = prompt("Reaction [like/love/haha/wow/sad/angry]").strip().lower() or "love"
                params["reaction"] = r
            else:
                params[p] = prompt(f"{p}").strip()

        bot.run_action_multi(a["key"], target, params)
        return
def manual_login_test():
    print("\nOpening Facebook...")
    bot = webdriver.Chrome()
    bot.get("https://www.facebook.com/")

    input("Log in manually in the browser, then press Enter here...")

    print("Current URL:", bot.current_url)
    input("Press Enter to close the browser...")
    bot.quit()
def main_menu():
    bot = None
    load_accounts()
    while True:
        clear(); banner(); header_box("MAIN MENU"); print()
        kv("Browser", f"{GREEN}● ready{RESET}" if bot else f"{RED}● stopped{RESET}")
        kv("Storage", ROOT, DIMWHITE)
        accounts = load_accounts(seed_embedded=False)
        emb = sum(1 for a in accounts if a.get("embedded"))
        kv("Accounts", f"{len(accounts)} saved ({emb} built-in)", GOLD)
        print(); hr(); print()
        menu_row("1", "Start Browser",       "launch chrome")
        menu_row("2", "Add Account",         "login with email/phone + password")
        menu_row("3", "List Accounts",       "view / delete saved accounts")
        menu_row("4", "Multi-Account Send",  "friend requests from all accounts")
        menu_row("5", "Run Action",          "like · comment · share · review · follow · join")
        menu_row("6", "Exit")
        print(); hr()
        c = prompt("Choose (1-6)").strip()

        if c == "1":
            if bot is None:
                clear(); banner(); header_box("LAUNCHING BROWSER"); print()
                try: bot = FacebookBot(); ok("Browser ready.")
                except Exception as e: err(f"Start failed: {e}")
                pause()
            else: info("Already running."); time.sleep(1.2)
        elif c == "2":
            if bot is None: err("Start browser first."); time.sleep(1.6); continue
            add_account_flow(bot)
        elif c == "3":
            list_accounts_flow()
        elif c == "4":
            if bot is None: err("Start browser first."); time.sleep(1.6); continue
            clear(); banner(); header_box("MULTI-ACCOUNT · FRIEND REQUESTS"); print()
            t = normalize_url(prompt("Target profile URL").strip())
            if not t: err("Invalid URL."); pause(); continue
            bot.run_action_multi("friend_request", t, {})
        elif c == "5":
            if bot is None: err("Start browser first."); time.sleep(1.6); continue
            run_action_flow(bot)
        elif c == "6":
            print(); info("Shutting down…")
            if bot: bot.close()
            sys.exit()
        else: err("Invalid."); time.sleep(1)

if __name__ == "__main__":
    main_menu()
