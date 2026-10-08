# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""QML presentation adapter. Business operations remain behind the existing controller."""
import datetime
import os
import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QEvent, QTimer, QUrl, Signal, Slot, QAbstractListModel, QModelIndex, Qt, QSettings
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QFileDialog

from desktop_events import CODES, STAGES, classify, render, fault_context
from desktop_gui import UserError
from desktop_version import VERSION, WINDOW_TITLE, UI_ENTRY
from desktop_console import ConsoleRows, display_entry
import desktop_tutorial


_step_sound_lock = threading.Lock()


def play_step_sound():
    """A quiet ascending two-note cue, built in memory; no files or audio downloads."""
    if os.name != "nt" or not _step_sound_lock.acquire(blocking=False):
        return
    def play():
        try:
            import io
            import math
            import struct
            import wave
            import winsound
            rate = 22050
            samples = []
            for index in range(int(rate * .32)):
                t = index / rate
                value = 0.0
                for onset, frequency in ((0, 660), (.105, 880)):
                    age = t - onset
                    if 0 <= age < .20:
                        envelope = min(1, age / .012) * math.exp(-age * 20) * min(1, (.20 - age) / .025)
                        value += .095 * envelope * (math.sin(2 * math.pi * frequency * age) + .16 * math.sin(4 * math.pi * frequency * age))
                samples.append(struct.pack("<h", int(max(-1, min(1, value)) * 32767)))
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as sound:
                sound.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                sound.writeframes(b"".join(samples))
            winsound.PlaySound(buffer.getvalue(), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        except Exception:
            pass  # Sound unavailable must never interrupt the workflow.
        finally:
            _step_sound_lock.release()
    try:
        threading.Thread(target=play, daemon=True).start()
    except Exception:
        _step_sound_lock.release()


class EventRows(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def roleNames(self):
        return {Qt.ItemDataRole.UserRole: b"entry"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.UserRole and 0 <= index.row() < len(self.rows):
            return self.rows[index.row()]
        return None

    def append(self, entries):
        if not entries:
            return
        entries = entries[-500:]
        remove = max(0, len(self.rows) + len(entries) - 500)
        if remove:
            self.beginRemoveRows(QModelIndex(), 0, remove - 1)
            del self.rows[:remove]
            self.endRemoveRows()
        offset = len(self.rows)
        self.beginInsertRows(QModelIndex(), offset, offset + len(entries) - 1)
        self.rows.extend(entries)
        self.endInsertRows()


class Workbench(QObject):
    changed = Signal()
    logsChanged = Signal()
    confirmationChanged = Signal()
    registered = Signal()
    accountsReset = Signal()
    reopened = Signal()
    escapePressed = Signal()
    metricsChanged = Signal()
    tutorialChanged = Signal()

    def __init__(self, controller, application):
        super().__init__()
        self.controller, self.application = controller, application
        self.messages = queue.Queue()
        self.busy = False
        self.selected = ""
        self._state, self._logs = {}, []
        self.event_rows = ConsoleRows(self) if UI_ENTRY == "Retro.qml" else EventRows(self)
        self.ui_settings = QSettings(str(Path(controller.bridge._data_dir) / "interface.ini"), QSettings.Format.IniFormat)
        self._first_launch = not self.ui_settings.value("tutorial_seen", False, type=bool)
        self._confirmation = None
        self._notice, self._error = "请登记本人账号。", ""
        self.last_seq, self.last_heartbeat, self.active_since = 0, 0, None
        self.last_job = ""
        self.last_failure = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(350)
        self.poll()

        from desktop_metrics import SystemSampler
        self.system_sampler = SystemSampler()
        self._metrics = {"cpu": None, "ram": None, "disk": None, "seconds": 0}
        self.metrics_queue = queue.Queue(maxsize=1)
        self.metrics_lock = threading.Lock()
        self.metrics_enabled = False
        self.metrics_timer = QTimer(self)
        self.metrics_timer.setInterval(2000)
        self.metrics_timer.timeout.connect(self.sample_metrics)

    @Property('QVariantMap', notify=metricsChanged)
    def metrics(self):
        return self._metrics

    @Property(bool, notify=tutorialChanged)
    def firstLaunch(self):
        return self._first_launch

    @Property('QVariantMap', constant=True)
    def tutorial(self):
        return {"title": desktop_tutorial.TITLE, "intro": desktop_tutorial.INTRO,
                "steps": desktop_tutorial.STEPS, "tip": desktop_tutorial.TIP,
                "disclaimer": desktop_tutorial.DISCLAIMER, "attribution": desktop_tutorial.ATTRIBUTION}

    @Slot()
    def tutorialRead(self):
        # UI preference only: never clears accounts or grants submit consent.
        self.ui_settings.setValue("tutorial_seen", True)
        self._first_launch = False
        self.tutorialChanged.emit()

    @Property(bool, constant=True)
    def semanticColors(self):
        return not bool(os.environ.get("NO_COLOR"))

    @Property('QVariantMap', notify=logsChanged)
    def latestConsoleEntry(self):
        return self.event_rows.latest if isinstance(self.event_rows, ConsoleRows) else (self._logs[-1] if self._logs else {})

    @Slot(bool)
    def setMetricsEnabled(self, enabled):
        self.metrics_enabled = enabled
        if enabled:
            self.metrics_timer.start()
            self.sample_metrics()
        else:
            self.metrics_timer.stop()

    def sample_metrics(self):
        while not self.metrics_queue.empty():
            self._metrics = self.metrics_queue.get_nowait()
            self.metricsChanged.emit()
        if not self.metrics_enabled or not self.metrics_lock.acquire(blocking=False):
            return
        def worker():
            try:
                value = self.system_sampler.sample()
                if self.metrics_queue.empty():
                    self.metrics_queue.put_nowait(value)
            except Exception:
                pass  # Optional telemetry must never interrupt account/network recovery.
            finally:
                self.metrics_lock.release()
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            self.metrics_lock.release()

    @Property('QVariantMap', notify=changed)
    def state(self):
        return self._state

    @Property('QVariantList', notify=logsChanged)
    def logs(self):
        return self._logs

    @Property(QObject, constant=True)
    def logModel(self):
        return self.event_rows

    @Property('QVariantMap', notify=confirmationChanged)
    def confirmation(self):
        if not self._confirmation:
            return {"open": False, "seconds": 0}
        info = self._confirmation
        return {"open": True, "name": info["name"], "member": info["member"],
                "preview": info["preview"], "seconds": max(0, int(info["expires"] - time.monotonic()))}

    @Property(str, constant=True)
    def version(self):
        return VERSION

    @Property(str, constant=True)
    def uiFont(self):
        return self.application.font().family()

    @Slot(str)
    def selectMember(self, member):
        if self._state.get("blocked"):
            return
        if member in [x["key"] for x in self._state.get("members", [])]:
            self.selected = member
            self.poll()

    @Slot()
    def stepFeedback(self):
        play_step_sound()

    def failure(self, exc):
        code = getattr(exc, "code", None)
        code = code if isinstance(code, str) and code in CODES else classify(exc)
        self._error, self._notice = code, CODES[code]
        context = fault_context(exc)
        signature = (code, tuple(context.items()))
        if not (isinstance(exc, UserError) and exc.reported) and signature != self.last_failure:
            self.controller.events.emit("ui", code, "ERROR", **context)
        self.last_failure = signature

    def task(self, function, kind="action"):
        if self.busy:
            return
        self.busy, self._error = True, ""
        self.last_failure = None
        self._notice = "处理中，请留意授权弹窗。"
        self.poll()
        def worker():
            try:
                self.messages.put((kind, True, function()))
            except Exception as exc:
                self.messages.put((kind, False, exc))
        threading.Thread(target=worker, daemon=True).start()

    @Slot(str, str)
    def register(self, name, student):
        self.task(lambda: self.controller.action("add", {"name": name, "student_num": student}), "register")

    @Slot(bool)
    def resetAccounts(self, acknowledged):
        if self._state.get("blocked"):
            return
        self.task(lambda: self.controller.reset_accounts(acknowledged), "reset")

    @Slot(str)
    def action(self, name):
        if name not in ("capture", "build", "watch", "desktop-recover", "stop-job", "desktop-exit"):
            self.failure(ValueError("不允许未登记的业务操作"))
            self.poll()
            return
        if self._confirmation:
            self._error, self._notice = "E_BUSY", "请先取消或完成提交确认窗口。"
            self.poll()
            return
        selected = self.selected
        self.task(lambda: self.controller.action(name, {"member": selected}))

    @Slot()
    def prepare(self):
        if self._confirmation or self.busy:
            return
        selected = self.selected
        self.task(lambda: self.controller.prepare_submission(selected), "prepare")

    @Slot()
    def cancelConfirmation(self):
        if self._confirmation:
            self.controller.cancel_confirmation()
            self.controller.events.emit("submit", "cancelled", "WARN")
        self._confirmation = None
        self.confirmationChanged.emit()
        self.poll()

    @Slot(bool, bool)
    def commit(self, source_ack, account_ack):
        info = self._confirmation
        if not info or source_ack is not True or account_ack is not True:
            self.failure(ValueError("提交确认无效"))
            self.cancelConfirmation()
            return
        self._confirmation = None
        self.confirmationChanged.emit()
        self.task(lambda: self.controller.submit_confirmation(info["nonce"], acknowledged=True))

    @Slot()
    def exportDiagnostics(self):
        if self.busy or self._state.get("capturing") or self._confirmation:
            return
        destination, _ = QFileDialog.getSaveFileName(None, "保存脱敏诊断 ZIP",
            "pipeRun-diagnostic-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip", "ZIP 诊断包 (*.zip)")
        if destination:
            self.task(lambda: self.controller.export(destination))

    @Slot()
    def copyLogs(self):
        self.application.clipboard().setText("\n".join(x["text"] for x in self._logs))
        self._notice = "已复制脱敏日志。"
        self.poll()

    @Slot(str, result=str)
    def document(self, name):
        if name not in ("DESKTOP.md", "LICENSE", "NOTICE", "DISCLAIMER.md", "third_party/desktop/qt/PROVENANCE.md", "third_party/desktop/fonts/OFL.txt", "third_party/desktop/fonts/FusionPixel-OFL.txt", "third_party/desktop/fonts/FUSION-PIXEL.md"):
            return ""
        try:
            return (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")
        except OSError:
            return "说明文件未能读取，请查看发行包中的同名文件。"

    def poll(self):
        if self.controller.platform.exit_event.is_set():
            self.timer.stop()
            self.application.quit()
            return
        while not self.messages.empty():
            kind, ok, result = self.messages.get_nowait()
            self.busy = False
            if not ok:
                self.failure(result)
            elif kind == "prepare":
                self._confirmation = result
                self._notice = "请核对记录来源和本人账号。"
                self.confirmationChanged.emit()
            else:
                self._notice = str(result or "操作完成。")
                if kind == "register":
                    self.registered.emit()
                elif kind == "reset":
                    self.selected = ""
                    self.last_job = ""
                    self.accountsReset.emit()
        try:
            raw = self.controller.snapshot()
            members = [dict(member, label=member["name"] + " · " + member["key"]) for member in raw["members"]]
            capture, job = raw["capture"], raw["job"]
            keys = [x["key"] for x in members]
            if self.selected not in keys:
                self.selected = keys[0] if keys else ""
            member = next((x for x in members if x["key"] == self.selected), {})
            capturing = bool(raw["pending"] or capture.get("listening"))
            running = bool(job.get("running"))
            stage = raw["stage"] if raw["stage"] in STAGES else "ui"
            if job.get("message") and job["message"] != self.last_job:
                self.last_job = job["message"]
                self._notice = self.last_job
            if capturing or running:
                now = time.monotonic()
                self.active_since = self.active_since or now
                if now - self.last_heartbeat >= 2:
                    self.last_heartbeat = now
                    self.controller.events.emit(stage, "capture_sample" if capture.get("active") else "waiting",
                        elapsed=int(now - self.active_since), **{k: capture[k] for k in
                        ("remaining", "connections", "target", "tls_ok", "tls_failed", "requests") if capturing and k in capture})
            else:
                self.active_since = None
            entries = []
            console_entries = []
            for event in self.controller.events.since(self.last_seq):
                full_text = render(event, self.controller.events.clock + datetime.timedelta(milliseconds=event["ms"]), details=False)
                entries.append({"seq": event["seq"], "level": event["level"], "stage": STAGES[event["stage"]],
                    "code": event["code"], "text": full_text})
                if isinstance(self.event_rows, ConsoleRows):
                    console_entries.append(display_entry(event, full_text))
                self.last_seq = event["seq"]
                if event["level"] == "ERROR":
                    self._error, self._notice = event["code"], CODES[event["code"]]
                elif event["code"] in ("capture_ready", "identity_matched", "credential_saved", "restored"):
                    self._notice = CODES[event["code"]]
            if entries:
                self._logs = (self._logs + entries)[-500:]
                self.event_rows.append(console_entries if isinstance(self.event_rows, ConsoleRows) else entries)
                if isinstance(self.event_rows, ConsoleRows) and not (self.busy or capturing or running):
                    self.event_rows.settle()
                self.logsChanged.emit()
            elif isinstance(self.event_rows, ConsoleRows) and self.event_rows.active and not (self.busy or capturing or running):
                self.event_rows.settle()
                self.logsChanged.emit()
            self._state = {"members": members, "selected": self.selected, "member": member,
                "blocked": bool(self.busy or capturing or running or self._confirmation),
                "capturing": capturing, "running": running, "busy": self.busy,
                "recoveryPending": bool(raw.get("recovery_pending")),
                "capturePhase": ("preparing" if capturing and stage in ("precheck", "ca", "consent", "watchdog", "proxy") else
                    "stabilizing" if capturing and capture.get("active") and "身份已匹配" in str(capture.get("message", "")) else
                    "waiting_login" if capturing and capture.get("active") else "finishing" if capturing and capture.get("has_started") else "idle"),
                "pending": raw["pending"], "capture": capture, "jobKind": raw["job_kind"],
                "stage": STAGES[stage], "stageKey": stage, "notice": self._notice, "error": self._error,
                "nextStep": 0 if not members else 4 if member.get("attempted") and member.get("can_watch") else 3 if member.get("can_submit") else 2 if member.get("ready") else 1}
        except Exception as exc:
            self.failure(exc)
            self._state.update(notice=self._notice, error=self._error)
        if self._confirmation:
            if time.monotonic() >= self._confirmation["expires"]:
                self.cancelConfirmation()
                self._error, self._notice = "E_CONFIRM", CODES["E_CONFIRM"]
                self._state.update(notice=self._notice, error=self._error)
            self.confirmationChanged.emit()
        self.changed.emit()


class CloseGuard(QObject):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def eventFilter(self, window, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            # Cancel reliably even just after window activation/focus changes.
            # This never interrupts or retries an already launched submission.
            self.model.escapePressed.emit()
            return True
        if event.type() == QEvent.Type.Close and not self.model.controller.platform.exit_event.is_set():
            event.ignore()
            self.model.action("desktop-exit")
            return True
        return False


def create_window(controller, application=None):
    app = application or QApplication.instance() or QApplication([])
    app.setApplicationName("pipeRun")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "assets" / "pipeRun.ico")))
    font_directory = Path(__file__).resolve().parent / "third_party" / "desktop" / "fonts"
    if UI_ENTRY == "Retro.qml":
        pixel_file = font_directory / "fusion-pixel-10px-monospaced-zh_hans.otf"
        pixel_id = QFontDatabase.addApplicationFont(str(pixel_file))
        pixel_families = QFontDatabase.applicationFontFamilies(pixel_id) if pixel_id >= 0 else []
        if not pixel_families:
            raise RuntimeError("内置像素字体未能加载")
        pixel_font = QFont(pixel_families[0])
        pixel_font.setPixelSize(20)
        app.setFont(pixel_font)
    QQuickStyle.setStyle("Basic")
    model = Workbench(controller, app)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", model)
    if UI_ENTRY != "Retro.qml":
        raise RuntimeError("界面入口无效")
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "desktop_ui" / UI_ENTRY)))
    if not engine.rootObjects():
        model.timer.stop()
        controller.events.emit("ui", "E_UI", level="ERROR")
        raise UserError("E_UI", reported=True)
    window = engine.rootObjects()[0]
    window.setTitle(WINDOW_TITLE)
    guard = CloseGuard(model)
    window.installEventFilter(guard)
    return app, engine, model, window, guard


def run(controller):
    # These animations use no shaders; software rendering avoids requiring a working GPU driver.
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    app, engine, model, window, guard = create_window(controller)
    from desktop_instance import serve_activation
    activation_server = serve_activation(controller.platform.directory, window, model)
    try:
        return app.exec()
    finally:
        activation_server.close()
