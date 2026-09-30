"""Policy Engine page: the policy list + the access-decision evaluator.

The evaluator is the point of the module: pick a user, a time and (optionally) a device and
see the decision the engine reaches, with the trace that produced it. The maths live in
core/policy.py; this page only collects input and renders the result.
"""
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout,
                               QLineEdit, QMessageBox, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)
from landar.core.constants import ACTIONS, DEFAULT_GROUPS, ZONES
from landar.core.permissions import PermissionDenied
from landar.services import bandwidth, devices, policies, users
from landar.ui.components import SectionCard, button, caps, chip, dot, hbox, icon, label
from landar.ui.pages.base import Page, confirm, fill_table, form_dialog, new_table, selected_id
from landar.ui.theme import C, MONO


def zone_dialog(parent, zones: dict):
    """Grid of every zone with an Allow/Deny/Reject selector. Returns {zone: action} or None."""
    d = QDialog(parent); d.setWindowTitle("Zone rules"); d.setMinimumWidth(440)
    v = QVBoxLayout(d); v.setContentsMargins(20, 18, 20, 14); v.setSpacing(8)
    v.addWidget(caps("Per-zone verdict"))
    grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(6)
    combos = {}
    for i, zone in enumerate(ZONES):
        grid.addWidget(label(zone, size=12), i, 0)
        cb = QComboBox(); cb.addItems(ACTIONS); cb.setCurrentText(zones.get(zone, "Deny")); combos[zone] = cb
        grid.addWidget(cb, i, 1)
    v.addLayout(grid)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); bb.accepted.connect(d.accept); bb.rejected.connect(d.reject); v.addWidget(bb)
    if not d.exec(): return None
    return {z: combos[z].currentText() for z in ZONES if combos[z].currentText() != "Deny" or z in zones}


class PolicyEnginePage(Page):
    title, subtitle = "Policy Engine", "Security & Access"
    def __init__(self, actor):
        super().__init__(actor)
        top = QHBoxLayout(); self.tabs = []
        for i, name in enumerate(("Policies", "Access Evaluator")):
            b = button(name, on_click=lambda _=False, i=i: self.set_tab(i)); top.addWidget(b); self.tabs.append(b)
        top.addStretch(); self.root.addLayout(top)
        self.stack = QStackedWidget(); self.root.addWidget(self.stack, 1)
        self.stack.addWidget(self._policies_tab()); self.stack.addWidget(self._evaluator_tab())
        self.set_tab(0)

    def set_tab(self, i):
        for k, b in enumerate(self.tabs):
            b.setProperty("kind", "primary" if k == i else ""); b.style().unpolish(b); b.style().polish(b)
        self.stack.setCurrentIndex(i)

    # ---- policies tab ----------------------------------------------------------
    def _policies_tab(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 4, 0, 0); v.setSpacing(12)
        bar = QHBoxLayout(); bar.setSpacing(8)
        for text, fn, kind in (("Add policy", self.add, "primary"), ("Edit", self.edit, ""), ("Delete", self.delete, "danger")):
            b = button(text, kind, on_click=fn); b.setEnabled(self.actor.can("network.configure")); bar.addWidget(b)
        bar.addStretch()
        self.matrix = SectionCard("Effective bandwidth by role", "speed", "Resolved")
        v.addLayout(bar)
        self.t_pol = new_table(); v.addWidget(self.t_pol, 2)
        self._fill_matrix(self.matrix); v.addWidget(self.matrix, 1)
        return w

    def _fill_matrix(self, card):
        card.clear()
        try: rows = bandwidth.role_matrix(self.actor)
        except PermissionDenied: rows = []
        t = new_table(); t.setMinimumHeight(120)
        fill_table(t, ["Role", "Download", "Upload", "Policy"], [(r["role"], r["down"], r["up"], r["policy"]) for r in rows], ("Download", "Upload"))
        card.body.addWidget(t)

    def _zones_summary(self, zones):
        return "  ".join(f"{z}:{a[0]}" for z, a in zones.items() if a != "Deny") or "deny all"

    def load_policies(self):
        try: rows = policies.list_policies(self.actor)
        except PermissionDenied: return []
        return [(p["id"], p["name"], p["applies_group"] or "Any group", p["priority"], self._zones_summary(p["zones"]), p["status"]) for p in rows]

    def _form(self, title, p=None):
        name = QLineEdit((p or {}).get("name") or "")
        grp = QComboBox(); grp.addItem("Any group", None)
        for g in DEFAULT_GROUPS: grp.addItem(g, g)
        if p and p.get("applies_group"): grp.setCurrentText(p["applies_group"])
        prio = QSpinBox(); prio.setRange(1, 9999); prio.setValue((p or {}).get("priority") or 100)
        desc = QLineEdit((p or {}).get("description") or "")
        on = QCheckBox("Enabled"); on.setChecked(True if not p else bool(p["enabled"]))
        zones = zone_dialog(self, (p or {}).get("zones") or {})
        if zones is None: return None
        if form_dialog(self, title, [("Name", name), ("Applies to group", grp), ("Priority", prio), ("Description", desc), ("", on)]):
            return (name.text(), grp.currentData(), prio.value(), zones, on.isChecked(), desc.text())

    def add(self):
        v = self._form("Add access policy")
        if v: self.safely(policies.create_policy, self.actor, *v)
    def edit(self):
        pid = selected_id(self.t_pol); p = next((x for x in policies.list_policies(self.actor) if x["id"] == pid), None)
        if p and (v := self._form("Edit access policy", p)): self.safely(policies.update_policy, self.actor, pid, *v)
    def delete(self):
        pid = selected_id(self.t_pol)
        if pid and confirm(self, "Delete this access policy?"): self.safely(policies.delete_policy, self.actor, pid)

    # ---- evaluator tab ---------------------------------------------------------
    def _evaluator_tab(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 4, 0, 0); v.setSpacing(12)
        card = SectionCard("Access decision", "tune", "Live evaluation")
        row = QHBoxLayout(); row.setSpacing(8)
        self.user = QComboBox(); self.user.setMinimumWidth(180)
        self.device = QComboBox(); self.device.setMinimumWidth(200)
        self.when = QLineEdit(datetime.now().strftime("%Y-%m-%d %H:%M")); self.when.setMaximumWidth(160)
        row.addWidget(caps("User")); row.addWidget(self.user); row.addWidget(caps("Device")); row.addWidget(self.device)
        row.addWidget(caps("When")); row.addWidget(self.when)
        row.addWidget(button("Evaluate", "primary", "arrow_forward", self.evaluate)); row.addStretch()
        card.body.addLayout(row)
        self.verdict = QHBoxLayout(); card.body.addLayout(self.verdict)
        self.zones_box = QGridLayout(); card.body.addLayout(self.zones_box)
        self.trace = SectionCard("Decision trace", "account_tree", "Why")
        v.addWidget(card); v.addWidget(self.trace, 1)
        return w

    def _load_choices(self):
        cur_u, cur_d = self.user.currentData(), self.device.currentData()
        self.user.clear()
        try: rows = users.list_users(self.actor)
        except PermissionDenied: rows = []
        for u in rows: self.user.addItem(f"{u['username']} ({u['status']})", u["username"])
        if cur_u and self.user.findData(cur_u) >= 0: self.user.setCurrentData(cur_u)
        self.device.clear(); self.device.addItem("(no device)", None)
        try: ds = devices.list_devices(self.actor)
        except PermissionDenied: ds = []
        for d in ds: self.device.addItem(f"{d['hostname'] or d['mac']} · {d['state']}", d["id"])
        if cur_d and self.device.findData(cur_d) >= 0: self.device.setCurrentData(cur_d)

    def evaluate(self):
        try: when = datetime.strptime(self.when.text().strip(), "%Y-%m-%d %H:%M")
        except ValueError: QMessageBox.warning(self, "LANDAR", "Time must look like 2026-09-30 10:00"); return
        if self.user.currentData() is None: return
        ok, res = self.call(policies.preview, self.actor, self.user.currentData(), when, self.device.currentData())
        if not ok: return
        self._render(res)

    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            elif it.layout(): PolicyEnginePage._clear(it.layout())

    def _render(self, r):
        self._clear(self.verdict); self._clear(self.zones_box); self.trace.clear()
        col = C["tertiary"] if r["allowed"] else C["error"]
        self.verdict.addWidget(dot(col, 10)); self.verdict.addWidget(label("ACCESS GRANTED" if r["allowed"] else "ACCESS DENIED", col, 15, bold=True))
        self.verdict.addWidget(chip(r["reason"])); self.verdict.addStretch()
        if r["matched_policy"]: self.verdict.addWidget(caps(f"via {r['matched_policy']}"))
        bw = r["bandwidth"]
        self.verdict.addWidget(caps(f"BW {bw['down']//1000}/{bw['up']//1000} {bw['unit']}" if bw else "BW no policy"))
        self.verdict.addWidget(caps(f"SCHEDULE {r['schedule']['name']}" if r["schedule"] else "NO SCHEDULE"))
        for i, (zone, allowed) in enumerate(r["zones"].items()):
            row = hbox(icon("check_circle" if allowed else "close", C["tertiary"] if allowed else C["outline_variant"], 15),
                       label(zone, C["on_surface"] if allowed else C["outline"], 11), spacing=6)
            self.zones_box.addWidget(row, i // 3, i % 3)
        for step in r["trace"]: self.trace.body.addWidget(label("· " + step, C["on_surface_variant"], 11, mono=True))

    # ---- lifecycle -------------------------------------------------------------
    def refresh(self):
        fill_table(self.t_pol, ["ID", "Name", "Applies to", "Priority", "Zones", "Status"], self.load_policies(),
                   ("ID", "Priority"), ("Status",))
        self._fill_matrix(self.matrix); self._load_choices()
        if self.user.currentData() is not None: self.evaluate()
