# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Bounded presentation-only console rows; never changes the original event log."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from desktop_events import CODES, STAGES, OPERATIONS


def display_entry(event, full_text):
    prefix_parts = full_text.split("] ", 2)
    prefix = "] ".join(prefix_parts[:2]) + "] "
    body = prefix_parts[2] if len(prefix_parts) == 3 else full_text
    code, stage = event["code"], event["stage"]
    outcome = "info"
    if event["level"] == "ERROR" or code.startswith("E_") or code in ("invalid", "tls_rejected"):
        outcome = "error"
    elif code in ("ok", "credential_saved", "restored", "dryrun_ok", "valid", "exported", "ca_present", "tls_ok", "request_ok"):
        outcome = "success"
    elif code in ("start", "capture_ready", "waiting", "capture_sample", "verify_wait"):
        outcome = "running"
    if code == "start":
        body = OPERATIONS.get(event.get("operation"), "") if stage == "ui" else ""
    elif code == "ok":
        body = OPERATIONS.get(event.get("operation"), "") if stage == "ui" else ""
    counters = " · ".join(label + " " + str(event[key]) + unit for key, label, unit in (
        ("remaining", "剩余", " 秒"), ("elapsed", "已等待", " 秒"), ("requests", "收到", " 条信息")) if key in event)
    return {**event, "stageKey": stage, "prefix": prefix, "body": body, "text": body,
            "fullText": full_text, "outcome": outcome, "counters": counters}


class ConsoleRows(QAbstractListModel):
    """Fold stage heartbeats/completion in place; unconfirmed exits stay neutral."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows, self.active = [], {}
        self.latest = {}
        self.capture_saved = False

    def roleNames(self):
        return {Qt.ItemDataRole.UserRole: b"entry"}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.UserRole and 0 <= index.row() < len(self.rows):
            return self.rows[index.row()]
        return None

    def _index(self, sequence):
        return next((i for i, row in enumerate(self.rows) if row["seq"] == sequence), None)

    def _replace(self, index, **values):
        self.rows[index] = dict(self.rows[index], **values)
        self.latest = self.rows[index]
        position = self.index(index, 0)
        self.dataChanged.emit(position, position, [Qt.ItemDataRole.UserRole])

    def _finish_operation(self, operation, outcome):
        index = self._index(self.active.get("ui"))
        if index is not None and self.rows[index].get("operation") == operation:
            self._replace(index, outcome=outcome, counters="")
            self.active.pop("ui", None)

    def append(self, entries):
        terminal_codes = {"ok", "restored", "ca_present", "dryrun_ok", "credential_saved",
                          "valid", "invalid", "pending", "cancelled"}
        for incoming in entries[-500:]:
            row = dict(incoming)
            stage, code = row["stageKey"], row["code"]
            index = self._index(self.active.get(stage))
            heartbeat = code in ("waiting", "capture_sample", "identity_matched")
            finish = code in terminal_codes or row["outcome"] == "error"
            if index is not None and (heartbeat or finish):
                previous = self.rows[index]
                body = previous["body"] if code in ("waiting", "capture_sample", "ok") else row["body"]
                self._replace(index, body=body, text=body, fullText=row["fullText"],
                              outcome=previous["outcome"] if heartbeat else row["outcome"],
                              counters=row["counters"] if heartbeat else "", level=row["level"], code=code)
                if finish:
                    self.active.pop(stage, None)
            else:
                if row["outcome"] == "running":
                    if index is not None:
                        self._replace(index, outcome="info", counters="")
                    self.active[stage] = row["seq"]
                if len(self.rows) >= 500:
                    self.beginRemoveRows(QModelIndex(), 0, 0)
                    removed = self.rows.pop(0)["seq"]
                    self.endRemoveRows()
                    self.active = {key: seq for key, seq in self.active.items() if seq != removed}
                offset = len(self.rows)
                self.beginInsertRows(QModelIndex(), offset, offset)
                self.rows.append(row)
                self.endInsertRows()
                self.latest = row
            if code == "credential_saved":
                self.capture_saved = True
            if code == "restored" and self.capture_saved:
                self._finish_operation("capture", "success")
                self.capture_saved = False
            elif code == "dryrun_ok":
                self._finish_operation("build", "success")
            elif code in ("valid", "invalid", "pending"):
                self._finish_operation("watch", row["outcome"])
            if row["outcome"] == "error":
                ui = self._index(self.active.get("ui"))
                if ui is not None:
                    self._replace(ui, outcome="error", fullText=row["fullText"], level=row["level"], counters="")
                    self.active.pop("ui", None)
            if code == "start" and row.get("operation") == "capture":
                self.capture_saved = False

    def settle(self):
        for sequence in self.active.values():
            index = self._index(sequence)
            if index is not None:
                self._replace(index, outcome="info", counters="")
        self.active.clear()
