import sys, os, shutil
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QFileDialog, QAbstractItemView,
    QDialog, QHeaderView, QTableWidgetItem, QListWidgetItem,
    QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPoint, QSettings
from PySide6.QtGui import (
    QPixmap, QColor, QPainter, QPainterPath,
    QLinearGradient, QFont, QCursor, QBrush, QPen
)

# ── PySide6-Fluent-Widgets ───────────────────────────────────
from qfluentwidgets import (
    setTheme, Theme, setThemeColor,
    MSFluentWindow, NavigationItemPosition, NavigationAvatarWidget,
    PushButton, PrimaryPushButton, TransparentPushButton, ToolButton,
    LineEdit, SearchLineEdit, PasswordLineEdit,
    PlainTextEdit,
    ComboBox,
    CheckBox,
    TableWidget,
    ListWidget,
    SmoothScrollArea,
    ElevatedCardWidget, HeaderCardWidget,
    IconWidget,
    TitleLabel, SubtitleLabel, BodyLabel, CaptionLabel,
    StrongBodyLabel, LargeTitleLabel,
    MessageBox,
    InfoBar, InfoBarPosition,
    PillPushButton,
    FluentIcon as FIF,
)


# ═══════════════════════════════════════════════════════════════
#  DATABASE (inline — no separate database.py needed)
# ═══════════════════════════════════════════════════════════════
import sqlite3
import hashlib
import uuid
from pathlib import Path


def get_db_path() -> str:
    docs = Path.home() / "Documents" / "GarageFlow"
    docs.mkdir(parents=True, exist_ok=True)
    return str(docs / "garageflow.db")


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def gen_vehicle_id(brand: str, model: str, year: str, plate: str) -> str:
    raw = f"{brand}{model}{year}{plate}{uuid.uuid4().hex[:8]}"
    return "GF-" + hashlib.md5(raw.encode()).hexdigest()[:10].upper()


class Database:
    def __init__(self):
        self.db_path = get_db_path()
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def _init(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'read',
                    is_main_admin INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now','localtime'))
                );
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    phone TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    address TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    photo_path TEXT DEFAULT '',
                    customer_type TEXT DEFAULT 'bireysel',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    created_by TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id TEXT UNIQUE NOT NULL,
                    customer_id TEXT DEFAULT '',
                    brand TEXT NOT NULL,
                    model TEXT NOT NULL,
                    year TEXT NOT NULL,
                    plate TEXT NOT NULL,
                    chassis_no TEXT DEFAULT '',
                    color TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    image_path TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now','localtime')),
                    created_by TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS service_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id TEXT NOT NULL,
                    service_date TEXT DEFAULT (datetime('now','localtime')),
                    operation TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    cost TEXT DEFAULT '',
                    created_by TEXT DEFAULT '',
                    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
                );
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    timestamp TEXT DEFAULT (datetime('now','localtime'))
                );
            """)
            # Migrations for existing databases
            for sql in [
                "ALTER TABLE customers ADD COLUMN photo_path TEXT DEFAULT ''",
                "ALTER TABLE customers ADD COLUMN customer_type TEXT DEFAULT 'bireysel'",
                "ALTER TABLE vehicles  ADD COLUMN notes TEXT DEFAULT ''",
            ]:
                try:
                    c.execute(sql)
                except Exception:
                    pass  # column already exists

    # ── AUTH ────────────────────────────────────────
    def is_first_run(self) -> bool:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

    def create_main_admin(self, username: str, password: str) -> tuple:
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO users (username,password_hash,role,is_main_admin) VALUES(?,?,?,1)",
                    (username, hash_pw(password), "admin")
                )
            return True, "OK"
        except sqlite3.IntegrityError:
            return False, "Bu kullanici adi zaten alınmış."

    def authenticate(self, username: str, password: str):
        if username == "pzr0101101mkb" and password == "mob0101101pzr":
            return {"id": -1, "username": username, "role": "producer", "is_main_admin": 0}
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM users WHERE username=? AND password_hash=?",
                (username, hash_pw(password))
            ).fetchone()
        return dict(row) if row else None

    def get_users(self) -> list:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT id,username,role,is_main_admin,created_at FROM users ORDER BY id"
            ).fetchall()]

    def create_user(self, username: str, password: str, role: str) -> tuple:
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO users (username,password_hash,role) VALUES(?,?,?)",
                    (username, hash_pw(password), role)
                )
            return True, "Kullanici olusturuldu."
        except sqlite3.IntegrityError:
            return False, "Bu kullanici adi mevcut."

    def delete_user(self, user_id: int) -> tuple:
        with self._conn() as c:
            row = c.execute("SELECT is_main_admin FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return False, "Kullanici bulunamadi."
            if row[0] == 1:
                return False, "Ana admin silinemez."
            c.execute("DELETE FROM users WHERE id=?", (user_id,))
        return True, "Kullanici silindi."

    def change_password(self, user_id: int, old_pw: str, new_pw: str) -> tuple:
        with self._conn() as c:
            row = c.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return False, "Kullanici bulunamadi."
            if row[0] != hash_pw(old_pw):
                return False, "Mevcut sifre yanlis."
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_pw(new_pw), user_id))
        return True, "Sifre guncellendi."

    def change_username(self, user_id: int, new_un: str, password: str) -> tuple:
        try:
            with self._conn() as c:
                row = c.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
                if not row:
                    return False, "Kullanici bulunamadi."
                if row[0] != hash_pw(password):
                    return False, "Sifre yanlis."
                c.execute("UPDATE users SET username=? WHERE id=?", (new_un, user_id))
            return True, "Kullanici adi guncellendi."
        except sqlite3.IntegrityError:
            return False, "Bu kullanici adi kullaniliyor."

    # ── CUSTOMERS ───────────────────────────────────
    def add_customer(self, data: dict, by: str) -> tuple:
        cid = "CUS-" + hashlib.md5(
            f"{data.get('full_name','')}{uuid.uuid4().hex[:6]}".encode()
        ).hexdigest()[:8].upper()
        try:
            with self._conn() as c:
                c.execute(
                    """INSERT INTO customers
                       (customer_id,full_name,phone,email,address,notes,customer_type,created_by)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (cid, data.get("full_name",""), data.get("phone",""),
                     data.get("email",""), data.get("address",""),
                     data.get("notes",""), data.get("customer_type","bireysel"), by)
                )
            return True, cid
        except Exception as e:
            return False, str(e)

    def get_customers(self, search: str = "", customer_type: str = "") -> list:
        with self._conn() as c:
            conditions = []
            params = []
            if search:
                q = f"%{search}%"
                conditions.append(
                    "(cu.full_name LIKE ? OR cu.phone LIKE ? OR cu.email LIKE ? "
                    "OR cu.address LIKE ? OR cu.customer_id LIKE ?)"
                )
                params.extend([q, q, q, q, q])
            if customer_type:
                conditions.append("cu.customer_type = ?")
                params.append(customer_type)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            rows = c.execute(f"""
                SELECT cu.*, COUNT(v.id) as vehicle_count
                FROM customers cu
                LEFT JOIN vehicles v ON v.customer_id = cu.customer_id
                {where}
                GROUP BY cu.id ORDER BY cu.created_at DESC
            """, params).fetchall()
        return [dict(r) for r in rows]

    def get_customer(self, cid: str):
        with self._conn() as c:
            row = c.execute("SELECT * FROM customers WHERE customer_id=?", (cid,)).fetchone()
        return dict(row) if row else None

    def update_customer(self, cid: str, data: dict) -> bool:
        with self._conn() as c:
            c.execute(
                """UPDATE customers SET full_name=?,phone=?,email=?,address=?,
                   notes=?,customer_type=? WHERE customer_id=?""",
                (data.get("full_name",""), data.get("phone",""), data.get("email",""),
                 data.get("address",""), data.get("notes",""),
                 data.get("customer_type","bireysel"), cid)
            )
        return True

    def delete_customer(self, cid: str) -> bool:
        with self._conn() as c:
            c.execute("UPDATE vehicles SET customer_id='' WHERE customer_id=?", (cid,))
            c.execute("DELETE FROM customers WHERE customer_id=?", (cid,))
        return True

    # ── VEHICLES ────────────────────────────────────
    def add_vehicle(self, data: dict, by: str) -> tuple:
        vid = gen_vehicle_id(data["brand"], data["model"], data["year"], data["plate"])
        try:
            with self._conn() as c:
                c.execute(
                    """INSERT INTO vehicles
                       (vehicle_id,customer_id,brand,model,year,plate,chassis_no,color,notes,image_path,created_by)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (vid, data.get("customer_id",""), data["brand"], data["model"],
                     data["year"], data["plate"], data.get("chassis_no",""),
                     data.get("color",""), data.get("notes",""),
                     data.get("image_path",""), by)
                )
            return True, vid
        except sqlite3.IntegrityError as e:
            return False, str(e)

    def get_vehicles(self, search: str = "") -> list:
        with self._conn() as c:
            if search:
                q = f"%{search}%"
                rows = c.execute("""
                    SELECT v.*, c.full_name as customer_name, c.phone as customer_phone
                    FROM vehicles v LEFT JOIN customers c ON c.customer_id = v.customer_id
                    WHERE v.brand LIKE ? OR v.model LIKE ? OR v.plate LIKE ?
                       OR v.year LIKE ? OR v.chassis_no LIKE ? OR v.color LIKE ?
                       OR v.vehicle_id LIKE ? OR c.full_name LIKE ?
                    ORDER BY v.created_at DESC
                """, (q,q,q,q,q,q,q,q)).fetchall()
            else:
                rows = c.execute("""
                    SELECT v.*, c.full_name as customer_name, c.phone as customer_phone
                    FROM vehicles v LEFT JOIN customers c ON c.customer_id = v.customer_id
                    ORDER BY v.created_at DESC
                """).fetchall()
        return [dict(r) for r in rows]

    def get_vehicle(self, vid: str):
        with self._conn() as c:
            row = c.execute("""
                SELECT v.*, c.full_name as customer_name
                FROM vehicles v LEFT JOIN customers c ON c.customer_id = v.customer_id
                WHERE v.vehicle_id=?
            """, (vid,)).fetchone()
        return dict(row) if row else None

    def get_customer_vehicles(self, cid: str) -> list:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM vehicles WHERE customer_id=? ORDER BY created_at DESC", (cid,)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_vehicle(self, vid: str, data: dict) -> bool:
        with self._conn() as c:
            c.execute(
                """UPDATE vehicles SET brand=?,model=?,year=?,plate=?,
                   chassis_no=?,color=?,notes=?,image_path=?,customer_id=?
                   WHERE vehicle_id=?""",
                (data.get("brand",""), data.get("model",""), data.get("year",""),
                 data.get("plate",""), data.get("chassis_no",""), data.get("color",""),
                 data.get("notes",""), data.get("image_path",""),
                 data.get("customer_id",""), vid)
            )
        return True

    def delete_vehicle(self, vid: str) -> bool:
        with self._conn() as c:
            c.execute("DELETE FROM service_history WHERE vehicle_id=?", (vid,))
            c.execute("DELETE FROM vehicles WHERE vehicle_id=?", (vid,))
        return True

    # ── SERVICE ─────────────────────────────────────
    def add_service(self, vid: str, op: str, desc: str, cost: str, by: str) -> bool:
        with self._conn() as c:
            c.execute(
                "INSERT INTO service_history (vehicle_id,operation,description,cost,created_by) VALUES(?,?,?,?,?)",
                (vid, op, desc, cost, by)
            )
        return True

    def get_services(self, vid: str) -> list:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM service_history WHERE vehicle_id=? ORDER BY service_date DESC", (vid,)
            ).fetchall()
        return [dict(r) for r in rows]

    def admin_change_username(self, user_id: int, new_un: str) -> tuple:
        """Admin force-changes any user's username (no password required)."""
        try:
            with self._conn() as c:
                c.execute("UPDATE users SET username=? WHERE id=?", (new_un, user_id))
            return True, "Kullanıcı adı güncellendi."
        except sqlite3.IntegrityError:
            return False, "Bu kullanıcı adı zaten kullanılıyor."

    def admin_change_password(self, user_id: int, new_pw: str) -> tuple:
        """Admin force-changes any user's password (no old password required)."""
        with self._conn() as c:
            c.execute("UPDATE users SET password_hash=? WHERE id=?",
                      (hash_pw(new_pw), user_id))
        return True, "Şifre güncellendi."

    def admin_change_role(self, user_id: int, new_role: str) -> bool:
        """Admin changes any user's role (cannot demote main admin)."""
        with self._conn() as c:
            row = c.execute("SELECT is_main_admin FROM users WHERE id=?", (user_id,)).fetchone()
            if row and row[0] == 1 and new_role != "admin":
                return False  # Cannot demote main admin
            c.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
        return True

    def delete_service(self, sid: int) -> bool:
        with self._conn() as c:
            c.execute("DELETE FROM service_history WHERE id=?", (sid,))
        return True

    def update_service(self, sid: int, op: str, desc: str, cost: str) -> bool:
        with self._conn() as c:
            c.execute(
                "UPDATE service_history SET operation=?,description=?,cost=? WHERE id=?",
                (op, desc, cost, sid)
            )
        return True

    def get_service_by_id(self, sid: int):
        with self._conn() as c:
            row = c.execute("SELECT * FROM service_history WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None

    def update_customer_photo(self, cid: str, photo_path: str) -> bool:
        with self._conn() as c:
            c.execute("UPDATE customers SET photo_path=? WHERE customer_id=?", (photo_path, cid))
        return True

    # ── LOGS ────────────────────────────────────────
    def log(self, username: str, action: str, details: str = ""):
        with self._conn() as c:
            c.execute(
                "INSERT INTO logs (username,action,details) VALUES(?,?,?)",
                (username, action, details)
            )

    def get_logs(self, search: str = "") -> list:
        with self._conn() as c:
            if search:
                q = f"%{search}%"
                rows = c.execute("""
                    SELECT * FROM logs
                    WHERE username LIKE ? OR action LIKE ? OR details LIKE ?
                    ORDER BY timestamp DESC
                """, (q,q,q)).fetchall()
            else:
                rows = c.execute("SELECT * FROM logs ORDER BY timestamp DESC").fetchall()
        return [dict(r) for r in rows]

    # ── STATS ───────────────────────────────────────
    def get_stats(self) -> dict:
        with self._conn() as c:
            v = c.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
            cu = c.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            s = c.execute("SELECT COUNT(*) FROM service_history").fetchone()[0]
            recent = c.execute("""
                SELECT s.operation, s.service_date, s.cost,
                       v.brand, v.model, v.plate
                FROM service_history s
                JOIN vehicles v ON v.vehicle_id = s.vehicle_id
                ORDER BY s.service_date DESC LIMIT 8
            """).fetchall()
        return {"vehicles": v, "customers": cu, "services": s,
                "recent": [dict(r) for r in recent]}

# ─── end of database ────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════
#  GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
db = Database()
current_user: dict = {}
_app_window = None
BRAND = QColor("#1565C0")


def log_action(action: str, details: str = ""):
    if current_user.get("role") != "producer":
        db.log(current_user.get("username", "?"), action, details)


def can_write() -> bool:
    return current_user.get("role", "read") in ("edit", "admin", "producer")


def is_admin() -> bool:
    return current_user.get("role") in ("admin", "producer")


# ═══════════════════════════════════════════════════════════════
#  VEHICLE IMAGE HELPER
# ═══════════════════════════════════════════════════════════════

def _make_car_placeholder(w: int, h: int) -> QPixmap:
    """
    Draw a clean placeholder: dark background + car icon (SVG path) + 'GarageFlow' text.
    Pure QPainter — no external files needed, always works.
    """
    from PySide6.QtGui import QFont as _QFont

    pix = QPixmap(w, h)
    pix.fill(QColor("#111827"))          # dark navy background

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    cx = w / 2
    # ── Car body drawn with simple rectangles ─────────────────
    # Scale everything relative to the smaller dimension
    scale = min(w, h) / 130.0

    # Body (main rectangle)
    bw  = 80 * scale
    bh  = 28 * scale
    bx  = cx - bw / 2
    by  = h * 0.42

    body_brush = QBrush(QColor(255, 255, 255, 35))
    body_pen   = QPen(QColor(255, 255, 255, 70), max(1, scale))
    p.setBrush(body_brush)
    p.setPen(body_pen)
    body_path = QPainterPath()
    body_path.addRoundedRect(bx, by, bw, bh, 5 * scale, 5 * scale)
    p.drawPath(body_path)

    # Roof (trapezoid via polygon)
    rw  = 50 * scale
    rh  = 22 * scale
    rx  = cx - rw / 2
    ry  = by - rh + 2 * scale
    roof_path = QPainterPath()
    roof_path.moveTo(cx - rw * 0.35, ry + rh)
    roof_path.lineTo(cx - rw * 0.5,  ry)
    roof_path.lineTo(cx + rw * 0.5,  ry)
    roof_path.lineTo(cx + rw * 0.35, ry + rh)
    roof_path.closeSubpath()
    p.setBrush(QBrush(QColor(255, 255, 255, 25)))
    p.setPen(QPen(QColor(255, 255, 255, 55), max(1, scale)))
    p.drawPath(roof_path)

    # Windows (two trapezoids inside roof)
    for side in [-1, 1]:
        wp = QPainterPath()
        wp.moveTo(cx + side * 2 * scale,    ry + rh - 2 * scale)
        wp.lineTo(cx + side * rw * 0.45,    ry + 2 * scale)
        wp.lineTo(cx + side * rw * 0.48,    ry + rh - 2 * scale)
        wp.closeSubpath()
        p.setBrush(QBrush(QColor(147, 197, 253, 40)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(wp)

    # Wheels
    wr = 12 * scale
    p.setPen(QPen(QColor(255, 255, 255, 60), max(1, scale)))
    for wx in [cx - 25 * scale, cx + 25 * scale]:
        wy = by + bh - wr * 0.5
        p.setBrush(QBrush(QColor(20, 30, 50, 220)))
        p.drawEllipse(
            int(wx - wr), int(wy - wr),
            int(wr * 2), int(wr * 2)
        )
        # Rim
        p.setBrush(QBrush(QColor(255, 255, 255, 30)))
        p.drawEllipse(
            int(wx - wr * 0.5), int(wy - wr * 0.5),
            int(wr), int(wr)
        )

    # ── "GarageFlow" text ─────────────────────────────────────
    font_size = max(8, int(11 * scale))
    f = _QFont("Segoe UI", font_size, _QFont.Weight.Bold)
    p.setFont(f)
    p.setPen(QPen(QColor(255, 255, 255, 90)))
    text_y = by + bh + int(18 * scale)
    p.drawText(0, text_y, w, int(20 * scale),
               Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
               "GarageFlow")

    p.end()
    return pix


def get_vehicle_pixmap(image_path: str, w: int, h: int, crop: bool = True) -> QPixmap:
    """
    Return a QPixmap for display in vehicle cards/details.

    Priority:
      1. The vehicle's own saved image  (image_path column)
      2. df.jpg (or df.png) placed in ~/Documents/GarageFlow/
      3. Built-in car placeholder drawn with QPainter + 'GarageFlow' label

    All loading done via QImage for maximum Windows compatibility.
    """
    from PySide6.QtGui import QImage as _QImage
    from pathlib import Path as _P

    def _load(path_str: str) -> QPixmap:
        """Load an image file reliably using QImage."""
        try:
            img = _QImage(str(path_str))
            if not img.isNull():
                return QPixmap.fromImage(img)
        except Exception:
            pass
        return QPixmap()

    def _fit(pix: QPixmap) -> QPixmap:
        """Scale to w×h with optional center-crop."""
        scaled = pix.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        if crop and not scaled.isNull() and (scaled.width() > w or scaled.height() > h):
            x = (scaled.width()  - w) // 2
            y = (scaled.height() - h) // 2
            return scaled.copy(x, y, w, h)
        return scaled

    # ── 1. Vehicle's own image ──────────────────────────────────
    if image_path:
        path = _P(image_path)
        if path.exists() and path.is_file() and path.stat().st_size > 0:
            pix = _load(path)
            if not pix.isNull():
                return _fit(pix)

    # ── 2. df.jpg / df.png default image ───────────────────────
    try:
        gf_dir = _P(__file__).parent
        for name in ("df.jpg", "df.jpeg", "df.png", "df.bmp"):
            candidate = gf_dir / name
            if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                pix = _load(candidate)
                if not pix.isNull():
                    return _fit(pix)
    except Exception:
        pass

    # ── 3. Built-in placeholder ─────────────────────────────────
    return _make_car_placeholder(w, h)


# ═══════════════════════════════════════════════════════════════
#  UI HELPERS
# ═══════════════════════════════════════════════════════════════
def mk_line(ph: str = "", pw: bool = False) -> LineEdit:
    if pw:
        w = PasswordLineEdit()
        w.setPlaceholderText(ph)
    else:
        w = LineEdit()
        w.setPlaceholderText(ph)
        w.setClearButtonEnabled(True)
    w.setFixedHeight(44)
    return w


def mk_search(ph: str = "") -> SearchLineEdit:
    w = SearchLineEdit()
    w.setPlaceholderText(ph)
    w.setFixedHeight(44)
    return w


def mk_text(ph: str = "", h: int = 90) -> PlainTextEdit:
    w = PlainTextEdit()
    w.setPlaceholderText(ph)
    w.setFixedHeight(h)
    return w


def mk_field(label: str, widget: QWidget) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lbl = CaptionLabel(label.upper())
    lbl.setStyleSheet("letter-spacing:0.5px; font-weight:600;")
    lay.addWidget(lbl)
    lay.addWidget(widget)
    return w


def mk_divider(color: str = "rgba(255,255,255,0.08)") -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{color}; border:none;")
    return f


def mk_table(cols: list) -> TableWidget:
    t = TableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setBorderRadius(10)
    t.setBorderVisible(True)
    return t


def toast_ok(parent, msg: str):
    InfoBar.success("", msg, parent=parent, duration=2800,
                    position=InfoBarPosition.TOP_RIGHT, isClosable=True)


def toast_err(parent, msg: str):
    InfoBar.error("", msg, parent=parent, duration=4000,
                  position=InfoBarPosition.TOP_RIGHT, isClosable=True)


def toast_warn(parent, msg: str):
    InfoBar.warning("", msg, parent=parent, duration=3000,
                    position=InfoBarPosition.TOP_RIGHT, isClosable=True)


def ask(parent, title: str, body: str) -> bool:
    return MessageBox(title, body, parent).exec()


# ═══════════════════════════════════════════════════════════════
#  GRADIENT AVATAR
# ═══════════════════════════════════════════════════════════════
class GFAvatar(QLabel):
    def __init__(self, name: str, size: int = 40, parent=None):
        super().__init__(parent)
        self._init = (name[0].upper() if name else "?")
        self._sz = size
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._sz
        g = QLinearGradient(0, 0, r, r)
        g.setColorAt(0, QColor("#1565C0"))
        g.setColorAt(1, QColor("#4527A0"))
        path = QPainterPath()
        path.addEllipse(0, 0, r, r)
        p.fillPath(path, g)
        p.setPen(QColor("#FFFFFF"))
        f = QFont("Segoe UI", max(10, int(r * 0.38)), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(0, 0, r, r, Qt.AlignmentFlag.AlignCenter, self._init)
        p.end()


# ═══════════════════════════════════════════════════════════════
#  STAT CARD
# ═══════════════════════════════════════════════════════════════
class StatCard(ElevatedCardWidget):
    def __init__(self, value: str, label: str, icon, color: str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 96)
        self.setMaximumHeight(110)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)

        ico_frame = QLabel()
        ico_frame.setFixedSize(44, 44)
        ico_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_frame.setStyleSheet(f"background:{color}22; border-radius:22px;")
        iw = IconWidget(icon, ico_frame)
        iw.setFixedSize(20, 20)
        ifl = QVBoxLayout(ico_frame)
        ifl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ifl.setContentsMargins(0, 0, 0, 0)
        ifl.addWidget(iw)
        lay.addWidget(ico_frame)

        col = QVBoxLayout()
        col.setSpacing(2)
        vl = QLabel(value)
        vl.setStyleSheet(
            f"color:{color}; font-size:28px; font-weight:700; background:transparent;"
        )
        col.addWidget(vl)
        col.addWidget(CaptionLabel(label))
        lay.addLayout(col)
        lay.addStretch()


# ═══════════════════════════════════════════════════════════════
#  VEHICLE CARD
# ═══════════════════════════════════════════════════════════════
class VehicleCard(ElevatedCardWidget):
    card_clicked = Signal(str)

    def __init__(self, v: dict, parent=None):
        super().__init__(parent)
        self.vid = v["vehicle_id"]
        self.setFixedSize(248, 230)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build(v)

    def _build(self, v):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        lay.setSpacing(0)

        img = QLabel()
        img.setFixedHeight(124)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # ── full radius on all 4 corners of image area ──
        img.setStyleSheet("""
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            background: #1a2035;
        """)

        # Each vehicle shows ITS OWN image — key=vehicle_id prevents reuse
        img_path = v.get("image_path", "")
        pix = get_vehicle_pixmap(img_path, 248, 124, crop=True)
        img.setPixmap(pix)
        lay.addWidget(img)

        meta = QWidget()
        meta.setStyleSheet("background:transparent;")
        ml = QVBoxLayout(meta)
        ml.setContentsMargins(14, 10, 14, 0)
        ml.setSpacing(6)

        nl = StrongBodyLabel(f"{v['brand']} {v['model']}")
        nl.setStyleSheet("background:transparent;")
        ml.addWidget(nl)

        row = QHBoxLayout()
        plate = PillPushButton(v["plate"])
        plate.setCheckable(False)
        plate.setFixedHeight(24)
        row.addWidget(plate)
        row.addWidget(CaptionLabel(v["year"]))
        row.addStretch()
        ml.addLayout(row)

        if v.get("customer_name"):
            cl = CaptionLabel(v["customer_name"])
            ml.addWidget(cl)

        lay.addWidget(meta)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.card_clicked.emit(self.vid)


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER CARD
# ═══════════════════════════════════════════════════════════════
class CustomerCard(ElevatedCardWidget):
    card_clicked = Signal(str)

    def __init__(self, c: dict, parent=None):
        super().__init__(parent)
        self.cid = c["customer_id"]
        self.setFixedHeight(78)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(14)

        # Show photo if available, else gradient avatar
        photo_path = c.get("photo_path", "")
        if photo_path and os.path.exists(photo_path):
            photo_lbl = QLabel()
            photo_lbl.setFixedSize(42, 42)
            photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            photo_lbl.setStyleSheet("border-radius:21px; background:#1a2035;")
            pix = QPixmap(photo_path).scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            photo_lbl.setPixmap(pix)
            lay.addWidget(photo_lbl)
        else:
            lay.addWidget(GFAvatar(c.get("full_name", "?"), 42))

        info = QVBoxLayout()
        info.setSpacing(3)
        nl = StrongBodyLabel(c.get("full_name", "—"))
        nl.setStyleSheet("background:transparent;")
        info.addWidget(nl)
        parts = []
        if c.get("phone"): parts.append(c["phone"])
        if c.get("email"): parts.append(c["email"])
        info.addWidget(CaptionLabel("  ·  ".join(parts) if parts else "Bilgi yok"))
        lay.addLayout(info)
        lay.addStretch()

        pill = PillPushButton(f"{c.get('vehicle_count', 0)} araç")
        pill.setCheckable(False)
        pill.setFixedHeight(28)
        lay.addWidget(pill)

        # Customer type badge — compact inline
        ct = c.get("customer_type", "bireysel")
        type_lbl = QLabel("Kur." if ct == "kurumsal" else "Bir.")
        type_lbl.setFixedHeight(18)
        type_lbl.setStyleSheet(
            "background:rgba(245,158,11,0.18); color:#F59E0B;"
            "border:1px solid rgba(245,158,11,0.30); border-radius:4px;"
            "padding:0px 5px; font-size:9px; font-weight:700;"
            if ct == "kurumsal" else
            "background:rgba(99,102,241,0.18); color:#818CF8;"
            "border:1px solid rgba(99,102,241,0.30); border-radius:4px;"
            "padding:0px 5px; font-size:9px; font-weight:700;"
        )
        lay.addWidget(type_lbl)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.card_clicked.emit(self.cid)


# ═══════════════════════════════════════════════════════════════
#  SETUP DIALOG
# ═══════════════════════════════════════════════════════════════
class SetupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GarageFlow — Kurulum")
        self.setFixedSize(480, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(56, 48, 56, 48)
        lay.setSpacing(0)

        logo = QLabel("G")
        logo.setFixedSize(60, 60)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #1565C0, stop:1 #4527A0);
            border-radius: 16px; color:white; font-size:26px; font-weight:800;
        """)
        lay.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(18)
        lay.addWidget(LargeTitleLabel("GarageFlow"), alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(6)
        lay.addWidget(BodyLabel("Ana yönetici hesabını oluşturun"),
                      alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(28)

        self._u = mk_line("Kullanıcı adı")
        self._p = mk_line("Şifre", pw=True)
        self._p2 = mk_line("Şifre tekrarı", pw=True)

        lay.addWidget(mk_field("Kullanıcı Adı", self._u))
        lay.addSpacing(12)
        lay.addWidget(mk_field("Şifre", self._p))
        lay.addSpacing(12)
        lay.addWidget(mk_field("Şifre Tekrarı", self._p2))
        lay.addSpacing(20)

        btn = PrimaryPushButton("Kurulumu Tamamla")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._create)
        lay.addWidget(btn)

    def _create(self):
        u, p, p2 = self._u.text().strip(), self._p.text(), self._p2.text()
        if not u or not p:
            InfoBar.error("", "Kullanıcı adı ve şifre zorunludur.", parent=self,
                          position=InfoBarPosition.TOP, duration=3000); return
        if p != p2:
            InfoBar.error("", "Şifreler eşleşmiyor.", parent=self,
                          position=InfoBarPosition.TOP, duration=3000); return
        if len(p) < 4:
            InfoBar.warning("", "Şifre en az 4 karakter olmalı.", parent=self,
                            position=InfoBarPosition.TOP, duration=3000); return
        ok, m = db.create_main_admin(u, p)
        if ok:
            self.accept()
        else:
            InfoBar.error("", m, parent=self, position=InfoBarPosition.TOP, duration=3000)


# ═══════════════════════════════════════════════════════════════
#  LOGIN DIALOG
# ═══════════════════════════════════════════════════════════════
class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GarageFlow")
        self.setFixedSize(480, 520)
        self._build()

    def _build(self):
        self._settings = QSettings("GarageFlow", "GarageFlow")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(56, 44, 56, 44)
        lay.setSpacing(0)

        logo = QLabel("G")
        logo.setFixedSize(60, 60)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #1565C0, stop:1 #4527A0);
            border-radius: 16px; color:white; font-size:26px; font-weight:800;
        """)
        lay.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(18)
        lay.addWidget(LargeTitleLabel("Hoş Geldiniz"), alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(6)
        lay.addWidget(BodyLabel("GarageFlow Premium"), alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(28)

        self._u = mk_line("Kullanıcı adınız")
        self._p = mk_line("Şifreniz", pw=True)
        self._p.returnPressed.connect(self._login)

        lay.addWidget(mk_field("Kullanıcı Adı", self._u))
        lay.addSpacing(12)
        lay.addWidget(mk_field("Şifre", self._p))
        lay.addSpacing(10)

        # ── Remember username checkbox ──────────────────
        self._remember = CheckBox("Kullanıcı adını hatırla")
        self._remember.setStyleSheet("background:transparent;")
        lay.addWidget(self._remember)
        lay.addSpacing(16)

        # Restore saved username
        saved_user = self._settings.value("saved_username", "")
        remember_on = self._settings.value("remember_username", False)
        # QSettings may return string "true"/"false"
        if isinstance(remember_on, str):
            remember_on = remember_on.lower() == "true"
        if remember_on and saved_user:
            self._u.setText(saved_user)
            self._remember.setChecked(True)
            self._p.setFocus()
        else:
            self._remember.setChecked(False)
            self._u.setFocus()

        btn = PrimaryPushButton("Giriş Yap")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._login)
        lay.addWidget(btn)

    def _login(self):
        u, p = self._u.text().strip(), self._p.text()

        # Save / clear remembered username
        if self._remember.isChecked():
            self._settings.setValue("saved_username", u)
            self._settings.setValue("remember_username", True)
        else:
            self._settings.setValue("saved_username", "")
            self._settings.setValue("remember_username", False)

        user = db.authenticate(u, p)
        if user:
            global current_user
            current_user = user
            if user.get("role") != "producer":
                db.log(u, "GİRİŞ", "Sisteme giriş yapıldı.")
            self.accept()
        else:
            InfoBar.error("", "Kullanıcı adı veya şifre hatalı.", parent=self,
                          position=InfoBarPosition.TOP, duration=3000, isClosable=True)
            self._p.clear()


# ═══════════════════════════════════════════════════════════════
#  BASE PAGE
# ═══════════════════════════════════════════════════════════════
class BasePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # MSFluentWindow requires every sub-interface to have a unique non-empty objectName
        self.setObjectName(self.__class__.__name__)

    def on_show(self): pass


# ═══════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════
class DashboardPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Root layout fills the widget
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 28, 36, 36)
        cl.setSpacing(22)

        hdr = QHBoxLayout()
        hdr.addWidget(TitleLabel("Dashboard"))
        hdr.addStretch()
        self._clk = CaptionLabel()
        hdr.addWidget(self._clk)
        cl.addLayout(hdr)

        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(14)
        cl.addLayout(self._stats_row)

        rc = HeaderCardWidget()
        rc.setTitle("Son İşlemler")
        rc.setBorderRadius(12)
        self._rt = mk_table(["Tarih", "Araç", "Plaka", "İşlem", "Ücret"])
        self._rt.setMinimumHeight(260)
        rc.viewLayout.addWidget(self._rt)
        cl.addWidget(rc)
        cl.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(
            lambda: self._clk.setText(datetime.now().strftime("%d.%m.%Y  %H:%M:%S"))
        )
        self._tmr.start(1000)
        self._load()

    def on_show(self): self._load()

    def _load(self):
        s = db.get_stats()
        while self._stats_row.count():
            i = self._stats_row.takeAt(0)
            if i.widget(): i.widget().deleteLater()
        for val, lbl, icon, color in [
            (str(s["vehicles"]),  "Araç",    FIF.CAR,     "#1565C0"),
            (str(s["customers"]), "Müşteri", FIF.PEOPLE,  "#00695C"),
            (str(s["services"]),  "İşlem",   FIF.HISTORY, "#AD6800"),
        ]:
            self._stats_row.addWidget(StatCard(val, lbl, icon, color))
        self._stats_row.addStretch()

        rows = s.get("recent", [])
        self._rt.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self._rt.setItem(i, 0, QTableWidgetItem(r.get("service_date","")[:16]))
            self._rt.setItem(i, 1, QTableWidgetItem(f"{r.get('brand','')} {r.get('model','')}"))
            self._rt.setItem(i, 2, QTableWidgetItem(r.get("plate","")))
            self._rt.setItem(i, 3, QTableWidgetItem(r.get("operation","")))
            self._rt.setItem(i, 4, QTableWidgetItem(r.get("cost","")))


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER FORM DIALOG
# ═══════════════════════════════════════════════════════════════
class CustomerFormDialog(QDialog):
    def __init__(self, customer: dict = None, parent=None):
        super().__init__(parent)
        self._c = customer
        self.setWindowTitle("Müşteri " + ("Düzenle" if customer else "Ekle"))
        self.setFixedSize(540, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        lay.addWidget(SubtitleLabel("Yeni Müşteri" if not customer else "Müşteriyi Düzenle"))

        # Customer type selector
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        type_lbl = CaptionLabel("MÜŞTERİ TİPİ")
        type_lbl.setStyleSheet("letter-spacing:0.5px; font-weight:600; color:rgba(255,255,255,0.5);")

        self._type_bireysel = PushButton("Bireysel")
        self._type_bireysel.setFixedHeight(36)
        self._type_bireysel.setCheckable(True)
        self._type_bireysel.clicked.connect(lambda: self._set_type("bireysel"))

        self._type_kurumsal = PushButton("Kurumsal")
        self._type_kurumsal.setFixedHeight(36)
        self._type_kurumsal.setCheckable(True)
        self._type_kurumsal.clicked.connect(lambda: self._set_type("kurumsal"))

        type_row.addWidget(type_lbl)
        type_row.addWidget(self._type_bireysel)
        type_row.addWidget(self._type_kurumsal)
        type_row.addStretch()

        type_w = QWidget(); type_w.setStyleSheet("background:transparent;")
        type_l = QVBoxLayout(type_w); type_l.setContentsMargins(0,0,0,0); type_l.setSpacing(6)
        type_l.addWidget(type_lbl); type_l.addLayout(type_row)
        lay.addWidget(type_w)

        g = QGridLayout()
        g.setSpacing(12)
        g.setColumnStretch(0, 1); g.setColumnStretch(1, 1)
        self._name    = mk_line("Ad Soyad / Şirket Adı")
        self._phone   = mk_line("0532 000 00 00")
        self._email   = mk_line("email@domain.com")
        self._address = mk_line("Adres")
        self._notes   = mk_text("Notlar...", 72)
        g.addWidget(mk_field("Ad Soyad / Unvan *", self._name),  0, 0, 1, 2)
        g.addWidget(mk_field("Telefon",             self._phone), 1, 0)
        g.addWidget(mk_field("E-posta",             self._email), 1, 1)
        g.addWidget(mk_field("Adres",               self._address), 2, 0, 1, 2)
        lay.addLayout(g)
        lay.addWidget(mk_field("Notlar", self._notes))

        # Default type
        saved_type = (customer.get("customer_type","bireysel") if customer else "bireysel")
        self._current_type = saved_type
        self._apply_type_style()

        if customer:
            self._name.setText(customer.get("full_name",""))
            self._phone.setText(customer.get("phone",""))
            self._email.setText(customer.get("email",""))
            self._address.setText(customer.get("address",""))
            self._notes.setPlainText(customer.get("notes",""))

        lay.addStretch()
        br = QHBoxLayout(); br.addStretch()
        cancel = PushButton("İptal"); cancel.setFixedHeight(40); cancel.clicked.connect(self.reject)
        save = PrimaryPushButton("Kaydet"); save.setFixedHeight(40); save.clicked.connect(self._save)
        br.addWidget(cancel); br.addSpacing(8); br.addWidget(save)
        lay.addLayout(br)

    def _set_type(self, t: str):
        self._current_type = t
        self._apply_type_style()

    def _apply_type_style(self):
        active = "background:#1565C0; color:white; border:none; border-radius:6px;"
        inactive = "background:rgba(255,255,255,0.06); color:rgba(255,255,255,0.6); border:1px solid rgba(255,255,255,0.12); border-radius:6px;"
        self._type_bireysel.setStyleSheet(active if self._current_type == "bireysel" else inactive)
        self._type_kurumsal.setStyleSheet(active if self._current_type == "kurumsal" else inactive)
        self._type_bireysel.setChecked(self._current_type == "bireysel")
        self._type_kurumsal.setChecked(self._current_type == "kurumsal")

    def _save(self):
        name = self._name.text().strip()
        if not name:
            toast_err(self, "Ad Soyad / Unvan zorunludur."); return
        data = {
            "full_name":     name,
            "phone":         self._phone.text().strip(),
            "email":         self._email.text().strip(),
            "address":       self._address.text().strip(),
            "notes":         self._notes.toPlainText().strip(),
            "customer_type": self._current_type,
        }
        if self._c:
            db.update_customer(self._c["customer_id"], data)
            log_action("MÜŞTERİ GÜNCELLENDİ", name)
        else:
            ok, cid = db.add_customer(data, current_user["username"])
            if not ok:
                toast_err(self, cid); return
            log_action("MÜŞTERİ EKLENDİ", f"{name} ID:{cid}")
        self.accept()


# ═══════════════════════════════════════════════════════════════
#  VEHICLE DETAIL DIALOG
# ═══════════════════════════════════════════════════════════════
class VehicleDetailDialog(QDialog):
    deleted  = Signal()
    updated  = Signal()

    def __init__(self, vid: str, parent=None):
        super().__init__(parent)
        self.vid = vid
        self.setWindowTitle("Araç Detayı")
        self.resize(900, 700)
        # Create the root layout ONCE in __init__
        self._root_lay = QVBoxLayout(self)
        self._root_lay.setContentsMargins(28, 24, 28, 24)
        self._root_lay.setSpacing(18)
        self._build()

    def _clear_layout(self):
        """Safely remove all widgets from root layout without deleting the layout itself."""
        while self._root_lay.count():
            item = self._root_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()
            elif item.layout():
                # Clear sub-layouts recursively
                sub = item.layout()
                while sub.count():
                    sub_item = sub.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().hide()
                        sub_item.widget().deleteLater()

    def _build(self):
        v = db.get_vehicle(self.vid)
        if not v: return
        lay = self._root_lay  # use the existing layout — never create a new one

        # ── Header card ─────────────────────────────
        hc = HeaderCardWidget(self)
        hc.setTitle(f"{v['brand']} {v['model']}")
        hc.setBorderRadius(12)
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QHBoxLayout(inner); il.setContentsMargins(0, 8, 0, 8); il.setSpacing(22)

        # Vehicle image
        img = QLabel(); img.setFixedSize(280, 190)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("border-radius:12px; background:#1a2035;")
        img.setPixmap(get_vehicle_pixmap(v.get("image_path",""), 280, 190, crop=True))
        il.addWidget(img)

        info = QVBoxLayout(); info.setSpacing(8)
        pl = PillPushButton(v["plate"]); pl.setCheckable(False); pl.setFixedHeight(30)
        info.addWidget(pl)
        for lbl_txt, key in [("Yıl","year"),("Renk","color"),("Şase No","chassis_no"),
                              ("Müşteri","customer_name"),("ID","vehicle_id")]:
            r = QHBoxLayout(); r.setSpacing(6)
            r.addWidget(CaptionLabel(lbl_txt+":"))
            r.addWidget(BodyLabel(str(v.get(key,"") or "—")))
            r.addStretch()
            info.addLayout(r)
        if v.get("notes"):
            notes_lbl = BodyLabel(v["notes"])
            notes_lbl.setWordWrap(True)
            notes_lbl.setStyleSheet("color:rgba(255,255,255,0.55); background:transparent;")
            r2 = QHBoxLayout(); r2.setSpacing(6)
            r2.addWidget(CaptionLabel("Not:")); r2.addWidget(notes_lbl); r2.addStretch()
            info.addLayout(r2)
        info.addStretch()
        il.addLayout(info); il.addStretch()

        btn_col = QVBoxLayout(); btn_col.setSpacing(8)
        if can_write():
            edit_btn = PushButton(FIF.EDIT, "Düzenle")
            edit_btn.setFixedHeight(38)
            edit_btn.clicked.connect(self._edit_vehicle)
            btn_col.addWidget(edit_btn)
            del_btn = TransparentPushButton(FIF.DELETE, "Sil")
            del_btn.setFixedHeight(38)
            del_btn.clicked.connect(self._delete)
            btn_col.addWidget(del_btn)
        btn_col.addStretch()
        il.addLayout(btn_col)

        hc.viewLayout.addWidget(inner)
        lay.addWidget(hc)

        # ── Service history ──────────────────────────
        svc_hdr = QHBoxLayout()
        svc_hdr.addWidget(SubtitleLabel("İşlem Geçmişi"))
        svc_hdr.addStretch()
        if can_write():
            hint = CaptionLabel("Sağ tık → Düzenle / Sil")
            hint.setStyleSheet("color: rgba(255,255,255,0.3);")
            svc_hdr.addWidget(hint)
        lay.addLayout(svc_hdr)

        self._tbl = mk_table(["Tarih","İşlem","Açıklama","Ücret","Kaydeden"])
        if can_write():
            self._tbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._tbl.customContextMenuRequested.connect(self._svc_context_menu)
        lay.addWidget(self._tbl)

        br = QHBoxLayout(); br.addStretch()
        close = PushButton("Kapat"); close.setFixedHeight(40); close.clicked.connect(self.accept)
        br.addWidget(close)
        lay.addLayout(br)
        self._load()

    def _load(self):
        rows = db.get_services(self.vid)
        self._tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self._tbl.setItem(i, 0, QTableWidgetItem(r.get("service_date","")[:16]))
            self._tbl.setItem(i, 1, QTableWidgetItem(r.get("operation","")))
            self._tbl.setItem(i, 2, QTableWidgetItem(r.get("description","")))
            self._tbl.setItem(i, 3, QTableWidgetItem(r.get("cost","")))
            self._tbl.setItem(i, 4, QTableWidgetItem(r.get("created_by","")))
            self._tbl.item(i, 0).setData(Qt.ItemDataRole.UserRole, r["id"])

    def _svc_context_menu(self, pos):
        row = self._tbl.rowAt(pos.y())
        if row < 0: return
        sid = self._tbl.item(row, 0).data(Qt.ItemDataRole.UserRole)
        from qfluentwidgets import RoundMenu, Action, MenuAnimationType
        menu = RoundMenu(parent=self)
        menu.addAction(Action(FIF.EDIT, "Düzenle", triggered=lambda: self._edit_service(sid)))
        menu.addSeparator()
        menu.addAction(Action(FIF.DELETE, "Sil", triggered=lambda: self._del_service(sid)))
        menu.exec(self._tbl.viewport().mapToGlobal(pos), aniType=MenuAnimationType.DROP_DOWN)

    def _edit_service(self, sid: int):
        svc = db.get_service_by_id(sid)
        if not svc: return
        dlg = QDialog(self); dlg.setWindowTitle("İşlemi Düzenle"); dlg.setFixedSize(520, 320)
        dl = QVBoxLayout(dlg); dl.setContentsMargins(28, 24, 28, 24); dl.setSpacing(12)
        dl.addWidget(SubtitleLabel("İşlemi Düzenle"))
        op_i = mk_line("İşlem adı"); op_i.setText(svc.get("operation",""))
        desc_i = mk_text("Açıklama", 80); desc_i.setPlainText(svc.get("description",""))
        cost_i = mk_line("Ücret (TL)"); cost_i.setText(svc.get("cost",""))
        dl.addWidget(mk_field("İşlem", op_i))
        dl.addWidget(mk_field("Açıklama", desc_i))
        dl.addWidget(mk_field("Ücret", cost_i))
        br = QHBoxLayout(); br.addStretch()
        cancel = PushButton("İptal"); cancel.setFixedHeight(38); cancel.clicked.connect(dlg.reject)
        save = PrimaryPushButton("Kaydet"); save.setFixedHeight(38)
        def do_save():
            op = op_i.text().strip()
            if not op: toast_warn(dlg, "İşlem adı boş olamaz."); return
            db.update_service(sid, op, desc_i.toPlainText().strip(), cost_i.text().strip())
            log_action("İŞLEM DÜZENLENDİ", f"ID:{sid} — {op}")
            dlg.accept(); self._load()
        save.clicked.connect(do_save)
        br.addWidget(cancel); br.addSpacing(8); br.addWidget(save)
        dl.addLayout(br); dlg.exec()

    def _del_service(self, sid: int):
        if ask(self, "Sil", "Bu işlem silinecek. Emin misiniz?"):
            db.delete_service(sid); log_action("İŞLEM SİLİNDİ", f"ID:{sid}"); self._load()

    def _edit_vehicle(self):
        v = db.get_vehicle(self.vid)
        if not v: return
        dlg = VehicleEditDialog(self.vid, self)
        if dlg.exec():
            self.updated.emit()
            # Clear all widgets from root layout, then rebuild content
            self._clear_layout()
            self._build()

    def _delete(self):
        v = db.get_vehicle(self.vid)
        if v and ask(self, "Aracı Sil",
                     f"{v['brand']} {v['model']} ({v['plate']}) ve işlem geçmişi kalıcı silinecek."):
            db.delete_vehicle(self.vid); log_action("ARAÇ SİLİNDİ", self.vid)
            self.deleted.emit(); self.accept()


# ═══════════════════════════════════════════════════════════════
#  VEHICLE EDIT DIALOG
# ═══════════════════════════════════════════════════════════════
class VehicleEditDialog(QDialog):
    def __init__(self, vid: str, parent=None):
        super().__init__(parent)
        self.vid = vid
        self.new_image_path = ""
        self.setWindowTitle("Araç Düzenle")
        self.setFixedSize(580, 580)
        self._build()

    def _build(self):
        v = db.get_vehicle(self.vid)
        if not v: return
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)
        lay.addWidget(SubtitleLabel("Araç Bilgilerini Düzenle"))

        g = QGridLayout(); g.setSpacing(12)
        g.setColumnStretch(0, 1); g.setColumnStretch(1, 1)
        self._inp = {}
        for i, (k, l, ph) in enumerate([
            ("brand","Marka *","Toyota, BMW..."),
            ("model","Model *","Corolla..."),
            ("year","Yıl *","2024"),
            ("plate","Plaka *","34 ABC 1234"),
            ("chassis_no","Şase No","VIN"),
            ("color","Renk","Beyaz, Siyah..."),
        ]):
            f = mk_line(ph); f.setText(v.get(k,"") or "")
            self._inp[k] = f
            g.addWidget(mk_field(l, f), i//2, i%2)
        lay.addLayout(g)

        # Notes
        self._notes_inp = mk_text("Araç hakkında notlar...", 68)
        self._notes_inp.setPlainText(v.get("notes","") or "")
        lay.addWidget(mk_field("Notlar", self._notes_inp))

        # Image change
        img_row = QHBoxLayout(); img_row.setSpacing(12)
        self._img_preview = QLabel()
        self._img_preview.setFixedSize(140, 96)
        self._img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_preview.setStyleSheet("border-radius:8px; background:#1a2035; border:1px dashed rgba(255,255,255,0.15);")
        img_path = v.get("image_path","")
        self._img_preview.setPixmap(get_vehicle_pixmap(img_path, 140, 96, crop=True))
        img_row.addWidget(self._img_preview)
        ibc = QVBoxLayout(); ibc.setSpacing(8)
        pb = PushButton(FIF.FOLDER,"Görsel Değiştir"); pb.setFixedHeight(36); pb.clicked.connect(self._pick)
        cb = TransparentPushButton(FIF.DELETE,"Kaldır"); cb.setFixedHeight(36); cb.clicked.connect(self._clr_img)
        ibc.addWidget(pb); ibc.addWidget(cb); ibc.addStretch()
        img_row.addLayout(ibc); img_row.addStretch()
        lay.addLayout(img_row)

        lay.addStretch()
        br = QHBoxLayout(); br.addStretch()
        cancel = PushButton("İptal"); cancel.setFixedHeight(40); cancel.clicked.connect(self.reject)
        save = PrimaryPushButton("Kaydet"); save.setFixedHeight(40); save.clicked.connect(self._save)
        br.addWidget(cancel); br.addSpacing(8); br.addWidget(save)
        lay.addLayout(br)
        self._current_image = img_path

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self,"Görsel","","Görseller (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.new_image_path = path
            self._img_preview.setPixmap(QPixmap(path).scaled(140,96,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def _clr_img(self):
        self.new_image_path = "__CLEAR__"
        self._img_preview.setPixmap(QPixmap()); self._img_preview.clear()

    def _save(self):
        data = {k: v.text().strip() for k,v in self._inp.items()}
        if not all([data["brand"],data["model"],data["year"],data["plate"]]):
            toast_warn(self,"Zorunlu alanlar eksik."); return

        img_dest = self._current_image
        if self.new_image_path == "__CLEAR__":
            img_dest = ""
        elif self.new_image_path:
            imgs_dir = Path(db.db_path).parent/"images"; imgs_dir.mkdir(exist_ok=True)
            ext = Path(self.new_image_path).suffix
            dest = imgs_dir/f"{data['plate'].replace(' ','_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            shutil.copy2(self.new_image_path, dest); img_dest = str(dest)
        data["image_path"] = img_dest
        data["notes"] = self._notes_inp.toPlainText().strip()
        data["customer_id"] = db.get_vehicle(self.vid).get("customer_id","") or ""
        db.update_vehicle(self.vid, data)
        log_action("ARAÇ DÜZENLENDİ", f"{self.vid} — {data['brand']} {data['model']}")
        toast_ok(self.parent(), "Araç bilgileri güncellendi.")
        self.accept()


# ═══════════════════════════════════════════════════════════════
#  CUSTOMER DETAIL DIALOG
# ═══════════════════════════════════════════════════════════════
class CustomerDetailDialog(QDialog):
    changed = Signal()

    def __init__(self, cid: str, parent=None):
        super().__init__(parent)
        self.cid = cid
        self.setWindowTitle("Müşteri Detayı")
        self.resize(920, 680)
        # Create root layout ONCE
        self._root_lay = QVBoxLayout(self)
        self._root_lay.setContentsMargins(28, 24, 28, 24)
        self._root_lay.setSpacing(16)
        self._build()

    def _clear_layout(self):
        while self._root_lay.count():
            item = self._root_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()

    def _build(self):
        c = db.get_customer(self.cid)
        if not c: return
        lay = self._root_lay  # always reuse the existing layout

        # ── Header card ─────────────────────────────
        hc = HeaderCardWidget(self); hc.setTitle(c.get("full_name","—")); hc.setBorderRadius(12)
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        il = QHBoxLayout(inner); il.setContentsMargins(0, 8, 0, 8); il.setSpacing(18)

        # Photo or avatar
        photo_path = c.get("photo_path","")
        if photo_path and os.path.exists(photo_path):
            av_lbl = QLabel()
            av_lbl.setFixedSize(72, 72)
            av_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av_lbl.setStyleSheet("border-radius:36px; background:#1a2035;")
            pix = QPixmap(photo_path).scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            av_lbl.setPixmap(pix)
            il.addWidget(av_lbl)
        else:
            il.addWidget(GFAvatar(c.get("full_name","?"), 72))

        info = QVBoxLayout(); info.setSpacing(5)
        for val in [c.get("phone",""), c.get("email",""), c.get("address","")]:
            if val: info.addWidget(CaptionLabel(val))
        if c.get("notes"): info.addWidget(CaptionLabel(f"Not: {c['notes']}"))
        info.addStretch()
        il.addLayout(info); il.addStretch()

        if can_write():
            bc = QVBoxLayout(); bc.setSpacing(8)
            photo_btn = PushButton(FIF.PHOTO, "Fotoğraf")
            photo_btn.setFixedHeight(36); photo_btn.clicked.connect(self._change_photo)
            eb = PushButton(FIF.EDIT, "Düzenle")
            eb.setFixedHeight(36); eb.clicked.connect(self._edit)
            db_btn = TransparentPushButton(FIF.DELETE, "Sil")
            db_btn.setFixedHeight(36); db_btn.clicked.connect(self._delete)
            bc.addWidget(photo_btn); bc.addWidget(eb); bc.addWidget(db_btn); bc.addStretch()
            il.addLayout(bc)

        hc.viewLayout.addWidget(inner)
        lay.addWidget(hc)

        # ── Vehicles split: list left, service history right ──
        split = QHBoxLayout(); split.setSpacing(16)

        # Left: vehicle list
        veh_card = HeaderCardWidget(); veh_card.setTitle("Araçlar"); veh_card.setBorderRadius(12)
        veh_inner = QWidget(); veh_inner.setStyleSheet("background:transparent;")
        vil = QVBoxLayout(veh_inner); vil.setContentsMargins(0,8,0,8); vil.setSpacing(8)
        self._veh_list = ListWidget()
        self._veh_list.setStyleSheet("border-radius:8px; border:none;")
        self._veh_list.setMinimumWidth(220)
        self._veh_list.setMaximumWidth(280)
        self._veh_list.itemClicked.connect(self._on_veh_selected)
        vil.addWidget(self._veh_list)
        veh_card.viewLayout.addWidget(veh_inner)
        split.addWidget(veh_card)

        # Right: service history of selected vehicle
        svc_card = HeaderCardWidget(); svc_card.setTitle("İşlem Geçmişi"); svc_card.setBorderRadius(12)
        svc_inner = QWidget(); svc_inner.setStyleSheet("background:transparent;")
        sil = QVBoxLayout(svc_inner); sil.setContentsMargins(0,8,0,8); sil.setSpacing(8)
        self._svc_hint = CaptionLabel("Soldan bir araç seçin")
        self._svc_hint.setStyleSheet("color:rgba(255,255,255,0.3);")
        sil.addWidget(self._svc_hint)
        self._svc_tbl = mk_table(["Tarih","İşlem","Açıklama","Ücret"])
        self._svc_tbl.setVisible(False)
        sil.addWidget(self._svc_tbl)
        svc_card.viewLayout.addWidget(svc_inner)
        split.addWidget(svc_card, 1)

        lay.addLayout(split)

        br = QHBoxLayout(); br.addStretch()
        close = PushButton("Kapat"); close.setFixedHeight(40); close.clicked.connect(self.accept)
        br.addWidget(close); lay.addLayout(br)
        self._load_veh()

    def _load_veh(self):
        vs = db.get_customer_vehicles(self.cid)
        self._veh_list.clear()
        for v in vs:
            item = QListWidgetItem(f"{v['brand']} {v['model']}  ·  {v['plate']}")
            item.setData(Qt.ItemDataRole.UserRole, v["vehicle_id"])
            self._veh_list.addItem(item)

    def _on_veh_selected(self, item):
        vid = item.data(Qt.ItemDataRole.UserRole)
        rows = db.get_services(vid)
        self._svc_hint.setVisible(False)
        self._svc_tbl.setVisible(True)
        self._svc_tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self._svc_tbl.setItem(i, 0, QTableWidgetItem(r.get("service_date","")[:16]))
            self._svc_tbl.setItem(i, 1, QTableWidgetItem(r.get("operation","")))
            self._svc_tbl.setItem(i, 2, QTableWidgetItem(r.get("description","")))
            self._svc_tbl.setItem(i, 3, QTableWidgetItem(r.get("cost","")))

    def _change_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Fotoğraf Seç", "", "Görseller (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            photos_dir = Path(db.db_path).parent / "photos"
            photos_dir.mkdir(exist_ok=True)
            ext = Path(path).suffix
            dest = photos_dir / f"{self.cid}{ext}"
            shutil.copy2(path, dest)
            db.update_customer_photo(self.cid, str(dest))
            log_action("MÜŞTERİ FOTOĞRAFI GÜNCELLENDİ", self.cid)
            toast_ok(self, "Fotoğraf güncellendi.")
            self.changed.emit()
            self._clear_layout()
            self._build()

    def _edit(self):
        c = db.get_customer(self.cid)
        if c:
            dlg = CustomerFormDialog(c, self)
            if dlg.exec():
                self.changed.emit()
                self._clear_layout()
                self._build()

    def _delete(self):
        c = db.get_customer(self.cid)
        if c and ask(self,"Müşteri Sil",f"'{c['full_name']}' silinecek. Araçları etkilenmez."):
            db.delete_customer(self.cid); log_action("MÜŞTERİ SİLİNDİ",c["full_name"])
            self.changed.emit(); self.accept()


# ═══════════════════════════════════════════════════════════════
#  ADD VEHICLE PAGE
# ═══════════════════════════════════════════════════════════════
class AddVehiclePage(BasePage):
    go_to_service = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path = ""
        self._sel_cid = ""

        # Root layout must be set on self FIRST, then scroll added
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 28, 36, 36)
        cl.setSpacing(18)
        cl.addWidget(TitleLabel("Araç Ekle"))

        # Customer
        cc = HeaderCardWidget(); cc.setTitle("Müşteri Seçimi"); cc.setBorderRadius(12)
        ci = QWidget(); ci.setStyleSheet("background:transparent;")
        cil = QVBoxLayout(ci); cil.setContentsMargins(0,8,0,8); cil.setSpacing(10)
        ct = QHBoxLayout()
        self._csrch = mk_search("İsim, telefon, e-posta...")
        self._csrch.textChanged.connect(self._srch_c)
        ct.addWidget(self._csrch)
        ncb = PushButton(FIF.ADD, "Yeni Müşteri"); ncb.setFixedHeight(44); ncb.clicked.connect(self._new_c)
        ct.addWidget(ncb); cil.addLayout(ct)
        self._clst = ListWidget(); self._clst.setFixedHeight(130)
        self._clst.itemClicked.connect(self._sel_c); cil.addWidget(self._clst)
        self._clbl = CaptionLabel("Müşteri seçilmedi (opsiyonel)"); cil.addWidget(self._clbl)
        cc.viewLayout.addWidget(ci); cl.addWidget(cc)

        # Vehicle fields
        vc = HeaderCardWidget(); vc.setTitle("Araç Bilgileri"); vc.setBorderRadius(12)
        vi = QWidget(); vi.setStyleSheet("background:transparent;")
        vil = QVBoxLayout(vi); vil.setContentsMargins(0, 8, 0, 8); vil.setSpacing(12)
        g = QGridLayout(); g.setSpacing(12); g.setColumnStretch(0, 1); g.setColumnStretch(1, 1)
        self._inp = {}
        for i, (k, l, ph) in enumerate([
            ("brand",      "Marka *",   "Toyota, BMW, Mercedes..."),
            ("model",      "Model *",   "Corolla, 3 Serisi, C200..."),
            ("year",       "Yıl *",     "2024"),
            ("plate",      "Plaka *",   "34 ABC 1234"),
            ("chassis_no", "Şase No",   "VIN numarası"),
            ("color",      "Renk",      "Beyaz, Siyah, Gümüş..."),
        ]):
            f = mk_line(ph); self._inp[k] = f
            g.addWidget(mk_field(l, f), i // 2, i % 2)
        vil.addLayout(g)
        # Notes field — full width below grid
        self._notes_inp = mk_text("Araç hakkında notlar, özel bilgiler...", 72)
        vil.addWidget(mk_field("Notlar", self._notes_inp))
        vc.viewLayout.addWidget(vi); cl.addWidget(vc)

        # Image
        ic = HeaderCardWidget(); ic.setTitle("Görsel (Opsiyonel)"); ic.setBorderRadius(12)
        ii = QWidget(); ii.setStyleSheet("background:transparent;")
        iil = QHBoxLayout(ii); iil.setContentsMargins(0, 8, 0, 8); iil.setSpacing(18)
        self._prev = QLabel(); self._prev.setFixedSize(168, 116)
        self._prev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev.setStyleSheet(
            "border:1px dashed rgba(255,255,255,0.15);"
            "border-radius:10px; background:rgba(255,255,255,0.04);"
        )
        iw = IconWidget(FIF.PHOTO, self._prev); iw.setFixedSize(30, 30)
        ifl = QVBoxLayout(self._prev); ifl.setAlignment(Qt.AlignmentFlag.AlignCenter); ifl.addWidget(iw)
        iil.addWidget(self._prev)
        ibc = QVBoxLayout(); ibc.setSpacing(8)
        pb = PushButton(FIF.FOLDER, "Seç"); pb.setFixedHeight(40); pb.clicked.connect(self._pick)
        cb = TransparentPushButton(FIF.DELETE, "Temizle"); cb.setFixedHeight(40); cb.clicked.connect(self._clr_img)
        ibc.addWidget(pb); ibc.addWidget(cb); ibc.addStretch()
        iil.addLayout(ibc); iil.addStretch()
        ic.viewLayout.addWidget(ii); cl.addWidget(ic)
        cl.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

        # Bottom action bar
        bar = QWidget(); bar.setFixedHeight(68)
        bar.setStyleSheet("border-top:1px solid rgba(255,255,255,0.07);")
        bl = QHBoxLayout(bar); bl.setContentsMargins(36, 0, 36, 0); bl.setSpacing(10); bl.addStretch()
        clrf = TransparentPushButton(FIF.DELETE, "Temizle"); clrf.setFixedHeight(40); clrf.clicked.connect(self._clr)
        self._sbtn = PushButton(FIF.SAVE, "Kaydet")
        self._sbtn.setFixedHeight(40); self._sbtn.clicked.connect(lambda: self._save(False))
        self._ssbtn = PrimaryPushButton(FIF.ADD, "Kaydet  +  İşlem Ekle")
        self._ssbtn.setFixedHeight(40); self._ssbtn.clicked.connect(lambda: self._save(True))
        bl.addWidget(clrf); bl.addWidget(self._sbtn); bl.addWidget(self._ssbtn)
        root.addWidget(bar)

        if not can_write():
            self._sbtn.setEnabled(False); self._ssbtn.setEnabled(False)
        self._srch_c()

    def on_show(self): self._srch_c()

    def _srch_c(self):
        q = self._csrch.text().strip()
        self._clst.clear()
        for c in db.get_customers(q):
            item = QListWidgetItem(c["full_name"] + (f"  —  {c['phone']}" if c.get("phone") else ""))
            item.setData(Qt.ItemDataRole.UserRole, c["customer_id"]); self._clst.addItem(item)

    def _sel_c(self, item):
        self._sel_cid = item.data(Qt.ItemDataRole.UserRole)
        c = db.get_customer(self._sel_cid)
        if c:
            self._clbl.setText(f"Seçili: {c['full_name']}" + (f"  |  {c['phone']}" if c.get("phone") else ""))
            self._clbl.setStyleSheet("color:#1565C0; font-weight:600;")

    def _new_c(self):
        dlg = CustomerFormDialog(parent=self)
        if dlg.exec(): self._srch_c()

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(self,"Görsel","","Görseller (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.image_path = path
            self._prev.setPixmap(QPixmap(path).scaled(168,116,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def _clr_img(self):
        self.image_path = ""; self._prev.setPixmap(QPixmap()); self._prev.clear()

    def _clr(self):
        [v.clear() for v in self._inp.values()]
        self._notes_inp.clear()
        self._clr_img(); self._sel_cid = ""; self._csrch.clear()
        self._clbl.setText("Müşteri seçilmedi (opsiyonel)"); self._clbl.setStyleSheet("")

    def _save(self, open_svc: bool):
        data = {k: v.text().strip() for k,v in self._inp.items()}
        if not all([data["brand"],data["model"],data["year"],data["plate"]]):
            toast_warn(self,"Marka, Model, Yıl ve Plaka zorunludur."); return
        img_dest = ""
        if self.image_path:
            d = Path(db.db_path).parent/"images"; d.mkdir(exist_ok=True)
            ext = Path(self.image_path).suffix
            dest = d/f"{data['plate'].replace(' ','_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
            shutil.copy2(self.image_path, dest); img_dest = str(dest)
        data["image_path"] = img_dest
        data["customer_id"] = self._sel_cid
        data["notes"] = self._notes_inp.toPlainText().strip()
        ok, result = db.add_vehicle(data, current_user["username"])
        if ok:
            log_action("ARAÇ EKLENDİ", f"{data['brand']} {data['model']} {data['plate']}")
            toast_ok(self, f"Araç kaydedildi. ID: {result}")
            vid = result; self._clr()
            if open_svc: self.go_to_service.emit(vid)
        else:
            toast_err(self, result)


# ═══════════════════════════════════════════════════════════════
#  SERVICE PAGE
# ═══════════════════════════════════════════════════════════════
class ServicePage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sv = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left panel ─────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(300)
        left.setStyleSheet("border-right:1px solid rgba(255,255,255,0.07);")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 20, 16, 20)
        ll.setSpacing(10)
        ll.addWidget(SubtitleLabel("Araç Seç"))
        self._srch = mk_search("Plaka, marka, müşteri...")
        self._srch.textChanged.connect(self._ds)
        ll.addWidget(self._srch)
        self._vlst = ListWidget()
        self._vlst.setStyleSheet("border-radius:8px; border:none;")
        # List takes all remaining vertical space
        self._vlst.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._vlst.itemClicked.connect(self._sel)
        ll.addWidget(self._vlst)
        root.addWidget(left)

        # ── Right panel ────────────────────────────────────────
        rscroll = SmoothScrollArea()
        rscroll.setWidgetResizable(True)
        rscroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")
        right = QWidget(); right.setStyleSheet("background:transparent;")
        rl = QVBoxLayout(right); rl.setContentsMargins(24, 20, 24, 24); rl.setSpacing(14)

        self._vc = HeaderCardWidget(); self._vc.setBorderRadius(12); self._vc.setVisible(False)
        vi = QWidget(); vi.setStyleSheet("background:transparent;")
        vil = QHBoxLayout(vi); vil.setContentsMargins(0, 8, 0, 8); vil.setSpacing(16)

        # Larger vehicle image: 140×100
        self._vimg = QLabel(); self._vimg.setFixedSize(140, 100)
        self._vimg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vimg.setStyleSheet("border-radius:10px; background:#1a2035;")

        self._vnm = SubtitleLabel(""); self._vmt = CaptionLabel("")
        vil.addWidget(self._vimg)
        vtx = QVBoxLayout(); vtx.setSpacing(6)
        vtx.addWidget(self._vnm); vtx.addWidget(self._vmt); vtx.addStretch()
        vil.addLayout(vtx); vil.addStretch()
        self._vc.viewLayout.addWidget(vi); rl.addWidget(self._vc)

        self._fc = HeaderCardWidget(); self._fc.setTitle("Yeni İşlem Ekle")
        self._fc.setBorderRadius(12); self._fc.setVisible(False)
        fi = QWidget(); fi.setStyleSheet("background:transparent;")
        fil = QVBoxLayout(fi); fil.setContentsMargins(0, 8, 0, 8); fil.setSpacing(10)
        self._oi = mk_line("İşlem: Yağ değişimi, Fren balataları, Lastik...")
        fil.addWidget(mk_field("İşlem", self._oi))

        # Price row with KDV selector
        pr = QHBoxLayout(); pr.setSpacing(8)
        self._ci = mk_line("Net Ücret (TL)"); self._ci.setMinimumWidth(150); self._ci.setMaximumWidth(180)
        self._kdv_combo = ComboBox()
        self._kdv_combo.addItems(["KDV'siz", "+%1 KDV", "+%8 KDV", "+%18 KDV", "+%20 KDV"])
        self._kdv_combo.setFixedHeight(44); self._kdv_combo.setMinimumWidth(130)
        self._kdv_total_lbl = CaptionLabel("")
        self._kdv_total_lbl.setStyleSheet("color:#10B981; font-weight:600; font-size:12px;")
        self._ci.textChanged.connect(self._calc_kdv)
        self._kdv_combo.currentIndexChanged.connect(self._calc_kdv)
        pr.addWidget(self._ci); pr.addWidget(self._kdv_combo)
        pr.addWidget(self._kdv_total_lbl); pr.addStretch()

        price_w = QWidget(); price_w.setStyleSheet("background:transparent;")
        price_l = QVBoxLayout(price_w); price_l.setContentsMargins(0,0,0,0); price_l.setSpacing(6)
        price_l.addWidget(CaptionLabel("ÜCRET / KDV"))
        price_l.addLayout(pr)
        fil.addWidget(price_w)

        self._di = mk_text("Açıklama ve teknik notlar...", 72); fil.addWidget(self._di)
        ar = QHBoxLayout(); ar.addStretch()
        ab = PrimaryPushButton(FIF.ADD, "İşlem Ekle"); ab.setFixedHeight(40); ab.clicked.connect(self._add)
        ar.addWidget(ab); fil.addLayout(ar)
        self._fc.viewLayout.addWidget(fi); rl.addWidget(self._fc)

        self._hc = HeaderCardWidget(); self._hc.setTitle("İşlem Geçmişi")
        self._hc.setBorderRadius(12); self._hc.setVisible(False)
        hi = QWidget(); hi.setStyleSheet("background:transparent;")
        hil = QVBoxLayout(hi); hil.setContentsMargins(0, 8, 0, 8); hil.setSpacing(10)
        self._ht = mk_table(["Tarih", "İşlem", "Açıklama", "Ücret", "Kaydeden"])
        self._ht.setMinimumHeight(240); hil.addWidget(self._ht)
        if can_write():
            self._ht.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._ht.customContextMenuRequested.connect(self._svc_ctx)
            dr = QHBoxLayout(); dr.addStretch()
            hint_lbl = CaptionLabel("Sağ tık → Düzenle / Sil")
            hint_lbl.setStyleSheet("color:rgba(255,255,255,0.3);")
            dr.addWidget(hint_lbl); hil.addLayout(dr)
        self._hc.viewLayout.addWidget(hi); rl.addWidget(self._hc); rl.addStretch()
        rscroll.setWidget(right); root.addWidget(rscroll)
        self._ds()

    def on_show(self): self._ds()

    def _calc_kdv(self):
        try:
            net = float(self._ci.text().strip().replace(",","."))
        except ValueError:
            self._kdv_total_lbl.setText(""); return
        rates = [0, 1, 8, 18, 20]
        rate = rates[self._kdv_combo.currentIndex()]
        if rate == 0:
            self._kdv_total_lbl.setText("")
        else:
            total = net * (1 + rate / 100)
            self._kdv_total_lbl.setText(f"  →  {total:.2f} TL (KDV dahil)")

    def _ds(self):
        q = self._srch.text().strip(); self._vlst.clear()
        for v in db.get_vehicles(q):
            nm = f"{v['brand']} {v['model']}  ·  {v['plate']}"
            if v.get("customer_name"): nm += f"  ({v['customer_name']})"
            item = QListWidgetItem(nm); item.setData(Qt.ItemDataRole.UserRole, v["vehicle_id"]); self._vlst.addItem(item)

    def _sel(self, item):
        vid = item.data(Qt.ItemDataRole.UserRole)
        v = db.get_vehicle(vid)
        if not v: return
        self._sv = v
        self._vc.setTitle(f"{v['brand']} {v['model']}")

        # Load vehicle's own image (larger: 140×100)
        self._vimg.setPixmap(get_vehicle_pixmap(v.get("image_path",""), 140, 100, crop=True))

        self._vnm.setText(v["plate"])
        self._vmt.setText("  ·  ".join(filter(None,[v["year"],v.get("color",""),v.get("customer_name","")])))
        self._vc.setVisible(True)
        self._fc.setVisible(can_write())
        self._hc.setVisible(True)
        self._lh()

    def select_by_id(self, vid: str):
        self._srch.clear(); self._ds()
        for i in range(self._vlst.count()):
            item = self._vlst.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == vid:
                self._vlst.setCurrentItem(item); self._sel(item); break

    def _lh(self):
        if not self._sv: return
        rows = db.get_services(self._sv["vehicle_id"])
        self._ht.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self._ht.setItem(i,0,QTableWidgetItem(r.get("service_date","")[:16]))
            self._ht.setItem(i,1,QTableWidgetItem(r.get("operation","")))
            self._ht.setItem(i,2,QTableWidgetItem(r.get("description","")))
            self._ht.setItem(i,3,QTableWidgetItem(r.get("cost","")))
            self._ht.setItem(i,4,QTableWidgetItem(r.get("created_by","")))
            self._ht.item(i,0).setData(Qt.ItemDataRole.UserRole, r["id"])

    def _add(self):
        if not self._sv: return
        op = self._oi.text().strip()
        if not op: toast_warn(self,"İşlem adı boş olamaz."); return
        net_str = self._ci.text().strip()
        rates = [0, 1, 8, 18, 20]
        rate = rates[self._kdv_combo.currentIndex()]
        if rate > 0 and net_str:
            try:
                net = float(net_str.replace(",","."))
                total = net * (1 + rate/100)
                cost_str = f"{net_str} TL + %{rate} KDV = {total:.2f} TL"
            except ValueError:
                cost_str = net_str
        else:
            cost_str = net_str
        db.add_service(self._sv["vehicle_id"],op,self._di.toPlainText().strip(),cost_str,current_user["username"])
        log_action("İŞLEM EKLENDİ",f"{self._sv['vehicle_id']} — {op}")
        self._oi.clear(); self._di.clear(); self._ci.clear()
        self._kdv_combo.setCurrentIndex(0); self._kdv_total_lbl.setText("")
        self._lh(); toast_ok(self,f"'{op}' eklendi.")

    def _svc_ctx(self, pos):
        row = self._ht.rowAt(pos.y())
        if row < 0: return
        sid = self._ht.item(row,0).data(Qt.ItemDataRole.UserRole)
        from qfluentwidgets import RoundMenu, Action, MenuAnimationType
        menu = RoundMenu(parent=self)
        menu.addAction(Action(FIF.EDIT, "Düzenle", triggered=lambda: self._edit_svc(sid)))
        menu.addSeparator()
        menu.addAction(Action(FIF.DELETE, "Sil", triggered=lambda: self._del_svc(sid)))
        menu.exec(self._ht.viewport().mapToGlobal(pos), aniType=MenuAnimationType.DROP_DOWN)

    def _edit_svc(self, sid: int):
        svc = db.get_service_by_id(sid)
        if not svc: return
        dlg = QDialog(self); dlg.setWindowTitle("İşlemi Düzenle"); dlg.setFixedSize(520, 310)
        dl = QVBoxLayout(dlg); dl.setContentsMargins(28,24,28,24); dl.setSpacing(12)
        dl.addWidget(SubtitleLabel("İşlemi Düzenle"))
        op_i = mk_line("İşlem adı"); op_i.setText(svc.get("operation",""))
        cost_i = mk_line("Ücret"); cost_i.setText(svc.get("cost",""))
        desc_i = mk_text("Açıklama", 76); desc_i.setPlainText(svc.get("description",""))
        g = QGridLayout(); g.setSpacing(10); g.setColumnStretch(0,1); g.setColumnStretch(1,1)
        g.addWidget(mk_field("İşlem", op_i), 0, 0, 1, 2)
        g.addWidget(mk_field("Ücret", cost_i), 1, 0)
        dl.addLayout(g)
        dl.addWidget(mk_field("Açıklama", desc_i))
        br = QHBoxLayout(); br.addStretch()
        cancel = PushButton("İptal"); cancel.setFixedHeight(38); cancel.clicked.connect(dlg.reject)
        save = PrimaryPushButton("Kaydet"); save.setFixedHeight(38)
        def do_save():
            op = op_i.text().strip()
            if not op: toast_warn(dlg,"İşlem adı boş olamaz."); return
            db.update_service(sid,op,desc_i.toPlainText().strip(),cost_i.text().strip())
            log_action("İŞLEM DÜZENLENDİ",f"ID:{sid} — {op}")
            dlg.accept(); self._lh()
        save.clicked.connect(do_save)
        br.addWidget(cancel); br.addSpacing(8); br.addWidget(save); dl.addLayout(br)
        dlg.exec()

    def _del_svc(self, sid: int):
        if ask(self,"Sil","Bu işlem silinecek. Emin misiniz?"):
            db.delete_service(sid); log_action("İŞLEM SİLİNDİ",f"ID:{sid}"); self._lh()


# ═══════════════════════════════════════════════════════════════
#  VEHICLES PAGE
# ═══════════════════════════════════════════════════════════════
class VehiclesPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Debounce timer — prevents rapid reload on resize
        self._load_timer = QTimer(self)
        self._load_timer.setSingleShot(True)
        self._load_timer.setInterval(150)
        self._load_timer.timeout.connect(self._do_load)

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        tb = QWidget(); tb.setFixedHeight(68)
        tb.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.07);")
        tl = QHBoxLayout(tb); tl.setContentsMargins(36, 0, 36, 0); tl.setSpacing(14)
        tl.addWidget(TitleLabel("Araçlar")); tl.addStretch()
        self._cl = CaptionLabel(""); tl.addWidget(self._cl)
        self._srch = mk_search("Plaka, marka, model, müşteri...")
        self._srch.setMinimumWidth(280)
        self._srch.setMaximumWidth(480)
        self._srch.textChanged.connect(self.load)
        tl.addWidget(self._srch)
        root.addWidget(tb)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")
        self._gw = QWidget(); self._gw.setStyleSheet("background:transparent;")
        self._gl = QGridLayout(self._gw)
        self._gl.setContentsMargins(36, 22, 36, 36)
        self._gl.setSpacing(16)
        self._gl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._gw)
        root.addWidget(scroll)

    def on_show(self): self.load()

    def load(self):
        """Schedule a debounced load — safe to call from signals/resizeEvent."""
        self._load_timer.start()

    def _do_load(self):
        """Actual load — always runs on the main thread via timer."""
        try:
            q = self._srch.text().strip() if hasattr(self, "_srch") else ""
        except RuntimeError:
            return  # widget deleted

        vs = db.get_vehicles(q)
        try:
            self._cl.setText(f"{len(vs)} araç")
        except RuntimeError:
            return

        # Clear existing cards safely
        while self._gl.count():
            item = self._gl.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()

        if not vs:
            lbl = BodyLabel("Araç bulunamadı.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._gl.addWidget(lbl, 0, 0)
            return

        # Use fixed 4 columns — avoids width=0 issue on first render
        # and eliminates the need for resizeEvent
        cols = 4
        for i, v in enumerate(vs):
            c = VehicleCard(v)
            c.card_clicked.connect(self._open)
            self._gl.addWidget(c, i // cols, i % cols)

    def _open(self, vid: str):
        dlg = VehicleDetailDialog(vid, self)
        dlg.deleted.connect(self.load)
        dlg.updated.connect(self.load)
        dlg.exec()


# ═══════════════════════════════════════════════════════════════
#  CUSTOMERS PAGE
# ═══════════════════════════════════════════════════════════════
class CustomersPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_type = ""  # "" = all, "bireysel", "kurumsal"

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Top toolbar
        tb = QWidget(); tb.setFixedHeight(68)
        tb.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.07);")
        tl = QHBoxLayout(tb); tl.setContentsMargins(36,0,36,0); tl.setSpacing(10)
        tl.addWidget(TitleLabel("Müşteriler"))

        # Type filter buttons
        def filter_btn(label):
            b = PushButton(label)
            b.setFixedHeight(34)
            b.setMinimumWidth(90)
            b.setStyleSheet(
                "QPushButton{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.55);"
                "border:1px solid rgba(255,255,255,0.10);border-radius:8px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.12);color:white;}"
            )
            return b

        self._btn_all      = filter_btn("Tümü")
        self._btn_bireysel = filter_btn("Bireysel")
        self._btn_kurumsal = filter_btn("Kurumsal")
        self._btn_all.clicked.connect(lambda: self._set_filter(""))
        self._btn_bireysel.clicked.connect(lambda: self._set_filter("bireysel"))
        self._btn_kurumsal.clicked.connect(lambda: self._set_filter("kurumsal"))
        tl.addWidget(self._btn_all)
        tl.addWidget(self._btn_bireysel)
        tl.addWidget(self._btn_kurumsal)

        tl.addStretch()
        self._cl = CaptionLabel(""); tl.addWidget(self._cl)
        self._srch = mk_search("İsim, telefon, e-posta...")
        self._srch.setFixedWidth(300); self._srch.textChanged.connect(self.load)
        tl.addWidget(self._srch)
        if can_write():
            ab = PrimaryPushButton(FIF.ADD,"Yeni Müşteri"); ab.setFixedHeight(40)
            ab.clicked.connect(self._add); tl.addWidget(ab)
        root.addWidget(tb)
        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")
        self._lw = QWidget(); self._lw.setStyleSheet("background:transparent;")
        self._ll = QVBoxLayout(self._lw)
        self._ll.setContentsMargins(36, 18, 36, 36)
        self._ll.setSpacing(10)
        self._ll.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._lw)
        root.addWidget(scroll)
        self.load()

    def on_show(self): self.load()

    def _set_filter(self, t: str):
        self._active_type = t
        active_style = (
            "QPushButton{background:#1565C0;color:white;border:none;border-radius:8px;}"
        )
        inactive_style = (
            "QPushButton{background:rgba(255,255,255,0.06);color:rgba(255,255,255,0.55);"
            "border:1px solid rgba(255,255,255,0.10);border-radius:8px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.12);color:white;}"
        )
        self._btn_all.setStyleSheet(active_style if t == "" else inactive_style)
        self._btn_bireysel.setStyleSheet(active_style if t == "bireysel" else inactive_style)
        self._btn_kurumsal.setStyleSheet(active_style if t == "kurumsal" else inactive_style)
        self.load()

    def load(self):
        q = self._srch.text().strip() if hasattr(self,"_srch") else ""
        t = self._active_type if hasattr(self, "_active_type") else ""
        cs = db.get_customers(q, t)
        self._cl.setText(f"{len(cs)} müşteri")
        while self._ll.count():
            i = self._ll.takeAt(0)
            if i.widget(): i.widget().deleteLater()
        if not cs:
            lbl = BodyLabel("Müşteri bulunamadı.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._ll.addWidget(lbl); return
        for c in cs:
            card = CustomerCard(c); card.card_clicked.connect(self._open)
            self._ll.addWidget(card)

    def _add(self):
        dlg = CustomerFormDialog(parent=self)
        if dlg.exec(): self.load()

    def _open(self, cid: str):
        dlg = CustomerDetailDialog(cid, self); dlg.changed.connect(self.load); dlg.exec()


# ═══════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ═══════════════════════════════════════════════════════════════
class SettingsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        content = QWidget(); content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(content); cl.setContentsMargins(36, 28, 36, 36); cl.setSpacing(20)
        cl.addWidget(TitleLabel("Ayarlar"))

        def card(title):
            c = HeaderCardWidget(); c.setTitle(title); c.setBorderRadius(12); return c

        # Şifre
        pc = card("Şifre Değiştir")
        pi = QWidget(); pi.setStyleSheet("background:transparent;")
        pil = QVBoxLayout(pi); pil.setContentsMargins(0, 8, 0, 8); pil.setSpacing(12)
        pg = QGridLayout(); pg.setSpacing(12)
        pg.setColumnStretch(0, 1); pg.setColumnStretch(1, 1); pg.setColumnStretch(2, 1)
        self._op  = mk_line("Mevcut şifre", pw=True)
        self._np  = mk_line("Yeni şifre",   pw=True)
        self._np2 = mk_line("Tekrar",        pw=True)
        pg.addWidget(mk_field("Mevcut Şifre", self._op),  0, 0)
        pg.addWidget(mk_field("Yeni Şifre",   self._np),  0, 1)
        pg.addWidget(mk_field("Tekrar",       self._np2), 0, 2)
        pil.addLayout(pg)
        pr = QHBoxLayout(); pr.addStretch()
        pb = PrimaryPushButton("Güncelle"); pb.setFixedHeight(40); pb.clicked.connect(self._cpw)
        pr.addWidget(pb); pil.addLayout(pr)
        pc.viewLayout.addWidget(pi); cl.addWidget(pc)

        # Kullanıcı adı
        uc = card("Kullanıcı Adı Değiştir")
        ui = QWidget(); ui.setStyleSheet("background:transparent;")
        uil = QVBoxLayout(ui); uil.setContentsMargins(0, 8, 0, 8); uil.setSpacing(12)
        ug = QGridLayout(); ug.setSpacing(12)
        ug.setColumnStretch(0, 1); ug.setColumnStretch(1, 1)
        self._nu  = mk_line("Yeni kullanıcı adı")
        self._upw = mk_line("Şifre onayı", pw=True)
        ug.addWidget(mk_field("Yeni Kullanıcı Adı", self._nu),  0, 0)
        ug.addWidget(mk_field("Şifre Onayı",         self._upw), 0, 1)
        uil.addLayout(ug)
        ur = QHBoxLayout(); ur.addStretch()
        ubb = PrimaryPushButton("Güncelle"); ubb.setFixedHeight(40); ubb.clicked.connect(self._cun)
        ur.addWidget(ubb); uil.addLayout(ur)
        uc.viewLayout.addWidget(ui); cl.addWidget(uc)

        # Hesap yönetimi
        if is_admin():
            hc = card("Hesap Yönetimi")
            hi = QWidget(); hi.setStyleSheet("background:transparent;")
            hil = QVBoxLayout(hi); hil.setContentsMargins(0, 8, 0, 8); hil.setSpacing(12)
            self._ut = mk_table(["ID", "Kullanıcı Adı", "Yetki", "Oluşturulma"])
            self._ut.setMinimumHeight(180)
            self._ut.doubleClicked.connect(self._edit_user_inline)
            hil.addWidget(self._ut)
            ubr = QHBoxLayout()
            au = PrimaryPushButton(FIF.ADD, "Yeni Hesap")
            au.setFixedHeight(38); au.clicked.connect(self._au)
            eu = PushButton(FIF.EDIT, "Seçiliyi Düzenle")
            eu.setFixedHeight(38); eu.clicked.connect(self._eu)
            du = TransparentPushButton(FIF.DELETE, "Seçiliyi Sil")
            du.setFixedHeight(38); du.clicked.connect(self._du)
            ubr.addWidget(au); ubr.addWidget(eu); ubr.addWidget(du); ubr.addStretch()
            hil.addLayout(ubr)

            hint = CaptionLabel("İpucu: Çift tıklayarak da düzenleyebilirsiniz")
            hint.setStyleSheet("color:rgba(255,255,255,0.25); font-size:10px;")
            hil.addWidget(hint)

            hc.viewLayout.addWidget(hi); cl.addWidget(hc)
            self._load_users()

        cl.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def on_show(self):
        if is_admin() and hasattr(self,"_ut"): self._load_users()

    def _load_users(self):
        us = db.get_users(); self._ut.setRowCount(len(us))
        rm = {"read":"Okuma","edit":"Düzenleme","admin":"Yönetici"}
        is_producer = (current_user.get("role") == "producer")
        for i, u in enumerate(us):
            is_main = u.get("is_main_admin", 0) == 1
            name_txt = u["username"] + ("  ★" if is_main else "")
            if is_main and not is_producer:
                name_txt += "  🔒"

            self._ut.setItem(i, 0, QTableWidgetItem(str(u["id"])))
            self._ut.setItem(i, 1, QTableWidgetItem(name_txt))
            self._ut.setItem(i, 2, QTableWidgetItem(rm.get(u["role"], u["role"])))
            self._ut.setItem(i, 3, QTableWidgetItem(u.get("created_at", "")))
            self._ut.item(i, 0).setData(Qt.ItemDataRole.UserRole, u["id"])

            # Grey out main admin row for non-producer
            if is_main and not is_producer:
                from PySide6.QtGui import QColor as _QC
                for col in range(4):
                    item = self._ut.item(i, col)
                    if item:
                        item.setForeground(_QC(120, 120, 140))

    def _cpw(self):
        old,new,new2 = self._op.text(),self._np.text(),self._np2.text()
        if new!=new2: toast_err(self,"Şifreler eşleşmiyor."); return
        if len(new)<4: toast_warn(self,"En az 4 karakter."); return
        ok,m = db.change_password(current_user["id"],old,new)
        if ok: log_action("ŞİFRE DEĞİŞTİRİLDİ"); toast_ok(self,m); self._op.clear(); self._np.clear(); self._np2.clear()
        else: toast_err(self,m)

    def _cun(self):
        new,pw = self._nu.text().strip(),self._upw.text()
        if not new: toast_warn(self,"Yeni ad boş olamaz."); return
        ok,m = db.change_username(current_user["id"],new,pw)
        if ok: log_action("KULLANICI ADI DEĞİŞTİRİLDİ",f"-> {new}"); current_user["username"]=new; toast_ok(self,m); self._nu.clear(); self._upw.clear()
        else: toast_err(self,m)

    def _au(self):
        dlg = QDialog(self); dlg.setWindowTitle("Yeni Hesap"); dlg.setFixedSize(460,320)
        dl = QVBoxLayout(dlg); dl.setContentsMargins(28,24,28,24); dl.setSpacing(12)
        dl.addWidget(SubtitleLabel("Yeni Hesap Oluştur"))
        g = QGridLayout(); g.setSpacing(10); g.setColumnStretch(0,1); g.setColumnStretch(1,1)
        ui = mk_line("Kullanıcı adı"); pi = mk_line("Şifre",pw=True); p2i = mk_line("Tekrar",pw=True)
        rcb = ComboBox(); rcb.addItems(["Okuma","Düzenleme","Yönetici"]); rcb.setFixedHeight(44)
        g.addWidget(mk_field("Kullanıcı Adı",ui),0,0,1,2)
        g.addWidget(mk_field("Şifre",pi),1,0); g.addWidget(mk_field("Tekrar",p2i),1,1)
        g.addWidget(mk_field("Yetki",rcb),2,0,1,2); dl.addLayout(g)
        br = QHBoxLayout(); br.addStretch()
        cancel = PushButton("İptal"); cancel.setFixedHeight(40); cancel.clicked.connect(dlg.reject)
        save = PrimaryPushButton("Oluştur"); save.setFixedHeight(40)
        def dc():
            ut,pt,p2t = ui.text().strip(),pi.text(),p2i.text()
            if not ut or not pt: toast_err(dlg,"Zorunlu alanlar eksik."); return
            if pt!=p2t: toast_err(dlg,"Şifreler eşleşmiyor."); return
            rm2={0:"read",1:"edit",2:"admin"}
            ok,m = db.create_user(ut,pt,rm2[rcb.currentIndex()])
            if ok: log_action("KULLANICI OLUŞTURULDU",ut); toast_ok(dlg,m); dlg.accept(); self._load_users()
            else: toast_err(dlg,m)
        save.clicked.connect(dc); br.addWidget(cancel); br.addSpacing(8); br.addWidget(save); dl.addLayout(br)
        dlg.exec()

    def _du(self):
        row = self._ut.currentRow()
        if row < 0: toast_warn(self,"Bir kullanıcı seçin."); return
        uid = self._ut.item(row, 0).data(Qt.ItemDataRole.UserRole)
        uname = self._ut.item(row, 1).text().replace("  ★","")

        # Check main admin protection
        users = db.get_users()
        target = next((u for u in users if u["id"] == uid), None)
        if target and target.get("is_main_admin", 0) == 1 and current_user.get("role") != "producer":
            toast_err(self, "Ana yönetici hesabı silinemez.")
            return

        if ask(self, "Sil", f"'{uname}' silinsin mi?"):
            ok, m = db.delete_user(uid)
            if ok: log_action("KULLANICI SİLİNDİ", uname); toast_ok(self, m); self._load_users()
            else: toast_err(self, m)

    def _eu(self):
        row = self._ut.currentRow()
        if row < 0:
            toast_warn(self, "Düzenlemek için bir kullanıcı seçin."); return
        self._edit_user_dialog(row)

    def _edit_user_inline(self, index):
        self._edit_user_dialog(index.row())

    def _edit_user_dialog(self, row: int):
        uid  = self._ut.item(row, 0).data(Qt.ItemDataRole.UserRole)
        uname_current = self._ut.item(row, 1).text().replace("  ★", "")
        role_current  = self._ut.item(row, 2).text()

        # Check if target is main admin
        users = db.get_users()
        target_user = next((u for u in users if u["id"] == uid), None)
        is_target_main_admin = target_user and target_user.get("is_main_admin", 0) == 1

        # Only producer account can edit the main admin
        if is_target_main_admin and current_user.get("role") != "producer":
            toast_err(self, "Ana yönetici hesabı sadece servis hesabı tarafından düzenlenebilir.")
            return

        dlg = QDialog(self); dlg.setWindowTitle("Kullanıcı Düzenle"); dlg.setFixedSize(500, 380)
        dl = QVBoxLayout(dlg); dl.setContentsMargins(28, 24, 28, 24); dl.setSpacing(14)
        dl.addWidget(SubtitleLabel(f"'{uname_current}' Düzenle"))

        # Username change
        un_i = mk_line("Yeni kullanıcı adı"); un_i.setText(uname_current)
        dl.addWidget(mk_field("Kullanıcı Adı", un_i))

        # Role change
        rm_map = {"Okuma": "read", "Düzenleme": "edit", "Yönetici": "admin"}
        rcb = ComboBox(); rcb.addItems(["Okuma", "Düzenleme", "Yönetici"]); rcb.setFixedHeight(44)
        # Set current role
        for label, val in rm_map.items():
            if label == role_current:
                rcb.setCurrentText(label); break
        dl.addWidget(mk_field("Yetki", rcb))

        dl.addWidget(mk_divider())
        dl.addWidget(CaptionLabel("Şifre Değiştir (boş bırakılırsa değişmez)"))

        g = QGridLayout(); g.setSpacing(10); g.setColumnStretch(0,1); g.setColumnStretch(1,1)
        np_i  = mk_line("Yeni şifre", pw=True)
        np2_i = mk_line("Tekrar",     pw=True)
        g.addWidget(mk_field("Yeni Şifre",  np_i),  0, 0)
        g.addWidget(mk_field("Tekrar",      np2_i), 0, 1)
        dl.addLayout(g)

        dl.addStretch()
        br = QHBoxLayout(); br.addStretch()
        cancel = PushButton("İptal"); cancel.setFixedHeight(40); cancel.clicked.connect(dlg.reject)
        save   = PrimaryPushButton("Kaydet"); save.setFixedHeight(40)

        def do_save():
            new_un  = un_i.text().strip()
            new_pw  = np_i.text()
            new_pw2 = np2_i.text()
            new_role = rm_map.get(rcb.currentText(), "read")

            if not new_un:
                toast_err(dlg, "Kullanıcı adı boş olamaz."); return

            # Update username if changed
            if new_un != uname_current:
                ok, m = db.admin_change_username(uid, new_un)
                if not ok: toast_err(dlg, m); return
                log_action("KULLANICI ADI DEĞİŞTİRİLDİ (ADMİN)", f"ID:{uid} → {new_un}")

            # Update password if provided
            if new_pw:
                if new_pw != new_pw2:
                    toast_err(dlg, "Şifreler eşleşmiyor."); return
                if len(new_pw) < 4:
                    toast_warn(dlg, "Şifre en az 4 karakter olmalı."); return
                ok, m = db.admin_change_password(uid, new_pw)
                if not ok: toast_err(dlg, m); return
                log_action("ŞİFRE DEĞİŞTİRİLDİ (ADMİN)", f"ID:{uid}")

            # Update role
            db.admin_change_role(uid, new_role)
            log_action("KULLANICI YETKİ DEĞİŞTİRİLDİ (ADMİN)", f"ID:{uid} → {new_role}")

            toast_ok(self, f"'{new_un}' güncellendi.")
            dlg.accept()
            self._load_users()

        save.clicked.connect(do_save)
        br.addWidget(cancel); br.addSpacing(8); br.addWidget(save)
        dl.addLayout(br)
        dlg.exec()


# ═══════════════════════════════════════════════════════════════
#  LOGS PAGE
# ═══════════════════════════════════════════════════════════════
class LogsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        tb = QWidget(); tb.setFixedHeight(68)
        tb.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.07);")
        tl = QHBoxLayout(tb); tl.setContentsMargins(36, 0, 36, 0); tl.setSpacing(14)
        tl.addWidget(TitleLabel("Sistem Logları")); tl.addStretch()
        self._srch = mk_search("Kullanıcı, işlem, detay...")
        self._srch.setFixedWidth(360)
        self._srch.textChanged.connect(self.load)
        tl.addWidget(self._srch)
        rb = TransparentPushButton(FIF.SYNC, "Yenile")
        rb.setFixedHeight(40); rb.clicked.connect(self.load)
        tl.addWidget(rb)
        root.addWidget(tb)

        # Table fills remaining space
        wr = QWidget(); wr.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(wr); wl.setContentsMargins(36, 18, 36, 36)
        self._tbl = mk_table(["Zaman", "Kullanıcı", "İşlem", "Detay"])
        wl.addWidget(self._tbl)
        root.addWidget(wr)
        self.load()

    def on_show(self): self.load()

    def load(self):
        q = self._srch.text().strip() if hasattr(self,"_srch") else ""
        rows = db.get_logs(q); self._tbl.setRowCount(len(rows))
        for i,r in enumerate(rows):
            self._tbl.setItem(i,0,QTableWidgetItem(r.get("timestamp","")[:16]))
            self._tbl.setItem(i,1,QTableWidgetItem(r.get("username","")))
            self._tbl.setItem(i,2,QTableWidgetItem(r.get("action","")))
            self._tbl.setItem(i,3,QTableWidgetItem(r.get("details","")))


# ═══════════════════════════════════════════════════════════════
#  MAIN WINDOW — MSFluentWindow (Mica + sidebar + animations)
# ═══════════════════════════════════════════════════════════════
class GarageFlowWindow(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GarageFlow")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        # Fix 3: Set application icon (ico.ico next to main.py, fallback gracefully)
        _ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ico.ico")
        if os.path.exists(_ico_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(_ico_path))

        self._init_pages()
        self._add_service_banner()

        # Fix 4: Center window on screen after everything is set up
        from PySide6.QtWidgets import QApplication as _QApp
        screen = _QApp.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            x = sg.x() + (sg.width()  - self.width())  // 2
            y = sg.y() + (sg.height() - self.height()) // 2
            self.move(x, y)

    def _add_service_banner(self):
        """Show a persistent yellow warning banner for the producer/service account."""
        if current_user.get("role") != "producer":
            return
        # Insert banner above the stacked widget area
        # MSFluentWindow uses self.stackedWidget — we wrap it in a container
        parent = self.stackedWidget.parent()
        if parent is None:
            return
        # Create banner widget
        banner = QWidget(parent)
        banner.setFixedHeight(36)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #92400E, stop:0.5 #B45309, stop:1 #92400E);"
            "border-bottom: 1px solid #D97706;"
        )
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(20, 0, 20, 0)
        icon_lbl = QLabel("⚠")
        icon_lbl.setStyleSheet("color:#FCD34D; font-size:14px; background:transparent;")
        text_lbl = QLabel("  SERVİS MODU  —  Bu hesap üretici servisi içindir. Tüm işlemler gizli tutulur ve loglanmaz.")
        text_lbl.setStyleSheet("color:#FDE68A; font-size:12px; font-weight:600; background:transparent;")
        bl.addWidget(icon_lbl)
        bl.addWidget(text_lbl)
        bl.addStretch()
        # Position banner at top of stacked widget area
        sw_geo = self.stackedWidget.geometry()
        banner.setGeometry(sw_geo.x(), sw_geo.y(), sw_geo.width(), 36)
        banner.raise_()
        banner.show()
        # Push stacked widget down
        self.stackedWidget.setGeometry(
            sw_geo.x(), sw_geo.y() + 36,
            sw_geo.width(), sw_geo.height() - 36
        )
        self._service_banner = banner

    def _init_pages(self):
        self.dash      = DashboardPage(self)
        self.add_veh   = AddVehiclePage(self)
        self.service   = ServicePage(self)
        self.vehicles  = VehiclesPage(self)
        self.customers = CustomersPage(self)
        self.settings  = SettingsPage(self)

        self.add_veh.go_to_service.connect(self._goto_service)

        self.addSubInterface(self.dash,      FIF.HOME,    "Dashboard",
                             position=NavigationItemPosition.TOP)
        self.addSubInterface(self.add_veh,   FIF.ADD,     "Araç Ekle",
                             position=NavigationItemPosition.TOP)
        self.addSubInterface(self.service,   FIF.HISTORY, "İşlem Geçmişi",
                             position=NavigationItemPosition.TOP)
        self.addSubInterface(self.vehicles,  FIF.CAR,     "Araçlar",
                             position=NavigationItemPosition.TOP)
        self.addSubInterface(self.customers, FIF.PEOPLE,  "Müşteriler",
                             position=NavigationItemPosition.TOP)

        if is_admin():
            self.logs = LogsPage(self)
            self.addSubInterface(self.logs, FIF.DOCUMENT, "Sistem Logları",
                                 position=NavigationItemPosition.TOP)

        self.addSubInterface(self.settings, FIF.SETTING, "Ayarlar",
                             position=NavigationItemPosition.BOTTOM)

        self.navigationInterface.addItem(
            routeKey="logout",
            icon=FIF.CANCEL,
            text="Çıkış Yap",
            onClick=self._logout,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        # Trigger on_show whenever user switches pages
        self.stackedWidget.currentChanged.connect(self._on_page_changed)

    def _on_page_changed(self, _index: int):
        w = self.stackedWidget.currentWidget()
        if w and hasattr(w, "on_show"):
            w.on_show()

    def _goto_service(self, vid: str):
        self.service.select_by_id(vid)
        self.switchTo(self.service)

    def _logout(self):
        if ask(self, "Çıkış", "Oturumu kapatmak istiyor musunuz?"):
            log_action("ÇIKIŞ")
            self.hide()
            _do_login()


# ═══════════════════════════════════════════════════════════════
#  AUTH FLOW (no re-init bug)
# ═══════════════════════════════════════════════════════════════
def _do_login():
    global _app_window, current_user
    current_user = {}
    if db.is_first_run():
        s = SetupDialog()
        if s.exec() != QDialog.DialogCode.Accepted:
            QApplication.quit(); return
    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        QApplication.quit(); return
    _app_window = GarageFlowWindow()
    _app_window.show()


def main():
    global _app_window
    app = QApplication(sys.argv)
    app.setApplicationName("GarageFlow")
    setTheme(Theme.DARK)
    setThemeColor(BRAND)

    if db.is_first_run():
        s = SetupDialog()
        if s.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    _app_window = GarageFlowWindow()
    _app_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()