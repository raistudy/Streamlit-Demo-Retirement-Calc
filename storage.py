import os, json, hashlib, base64, secrets, tempfile, datetime

DATA_DIR = ".data"
DATA_FILE = os.path.join(DATA_DIR, "users.json")

def _ensure_db_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_db() -> dict:
    _ensure_db_file()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_db(db: dict) -> None:
    _ensure_db_file()
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix="users_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, DATA_FILE)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def norm_email(email: str) -> str:
    return (email or "").strip().lower()[:254]

def sha256_legacy(pw: str) -> str:
    return hashlib.sha256((pw or "").encode("utf-8")).hexdigest()

def hash_pw(pw: str, salt_b64: str | None = None) -> tuple[str, str]:
    pw_bytes = (pw or "").encode("utf-8")
    if not salt_b64:
        salt = secrets.token_bytes(16)
        salt_b64 = base64.b64encode(salt).decode("ascii")
    else:
        salt = base64.b64decode(salt_b64.encode("ascii"))
    dk = hashlib.pbkdf2_hmac("sha256", pw_bytes, salt, 200_000)
    return base64.b64encode(dk).decode("ascii"), salt_b64

def verify_pw(user_rec: dict, password: str) -> bool:
    if user_rec.get("pw_hash") and user_rec.get("pw_salt"):
        calc, _ = hash_pw(password, user_rec["pw_salt"])
        return secrets.compare_digest(calc, user_rec["pw_hash"])
    if user_rec.get("password_hash"):
        return secrets.compare_digest(sha256_legacy(password), user_rec["password_hash"])
    return False

def upgrade_pw_if_legacy(user_rec: dict, password: str) -> None:
    if user_rec.get("pw_hash") and user_rec.get("pw_salt"):
        return
    if user_rec.get("password_hash") and secrets.compare_digest(user_rec["password_hash"], sha256_legacy(password)):
        new_hash, new_salt = hash_pw(password)
        user_rec["pw_hash"] = new_hash
        user_rec["pw_salt"] = new_salt
        user_rec.pop("password_hash", None)

def append_history(user_rec: dict, key: str, payload: dict, limit: int = 30) -> None:
    arr = user_rec.setdefault(key, [])
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    arr.append({"ts": ts, **payload})
    if len(arr) > limit:
        user_rec[key] = arr[-limit:]

def signup_save(email: str, password: str, payload: dict, record_type: str):
    email = norm_email(email)
    if not email or not password:
        return False, "Email and password required."
    db = load_db()
    rec = db.get(email)

    if rec:
        if not verify_pw(rec, password):
            return False, "Account already exists with a different password. Use Log in."
        upgrade_pw_if_legacy(rec, password)
    else:
        pw_hash, pw_salt = hash_pw(password)
        rec = {"pw_hash": pw_hash, "pw_salt": pw_salt}
        db[email] = rec

    rec[f"last_{record_type}"] = payload
    append_history(rec, f"{record_type}_history", payload)
    save_db(db)
    return True, "Signed up and saved ✅"

def login_save(email: str, password: str, payload: dict, record_type: str):
    email = norm_email(email)
    if not email or not password:
        return False, "Email and password required."
    db = load_db()
    rec = db.get(email)
    if not rec:
        return False, "No account found. Use Sign up."
    if not verify_pw(rec, password):
        return False, "Wrong password."

    upgrade_pw_if_legacy(rec, password)
    rec[f"last_{record_type}"] = payload
    append_history(rec, f"{record_type}_history", payload)
    save_db(db)
    return True, "Logged in and saved ✅"