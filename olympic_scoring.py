#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QComboBox, QMessageBox, QGroupBox, QFormLayout, QHeaderView
)

# 计分规则常量
POINTS_TOP3 = [5, 3, 2]
POINTS_TOP5 = [7, 5, 3, 2, 1]

@dataclass
class EventConfig:
    event_id: int
    gender: str  # '男' or '女'
    top_n: int   # 3 or 5

class OlympicsScoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("奥运会积分统计器")
        self.resize(1100, 700)

        # 全局参数
        self.n_countries: int = 0
        self.m_men: int = 0
        self.w_women: int = 0

        # 项目配置（行号 -> EventConfig）
        self.event_configs: Dict[int, EventConfig] = {}

        # UI
        self._build_ui()

    # --------------------------- UI 构建 ---------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 顶部初始化区域
        init_box = QGroupBox("比赛规模设置")
        init_layout = QFormLayout(init_box)
        self.edit_n = QLineEdit(); self.edit_n.setValidator(QIntValidator(1, 9999))
        self.edit_m = QLineEdit(); self.edit_m.setValidator(QIntValidator(0, 9999))
        self.edit_w = QLineEdit(); self.edit_w.setValidator(QIntValidator(0, 9999))
        self.edit_n.setPlaceholderText("国家数量 n (>=1)")
        self.edit_m.setPlaceholderText("男子项目数 m (>=0)")
        self.edit_w.setPlaceholderText("女子项目数 w (>=0)")
        init_layout.addRow("国家数量 n:", self.edit_n)
        init_layout.addRow("男子项目数 m:", self.edit_m)
        init_layout.addRow("女子项目数 w:", self.edit_w)
        btn_init = QPushButton("初始化比赛与录入表")
        btn_init.clicked.connect(self.on_initialize)
        init_layout.addRow(btn_init)
        root.addWidget(init_box)

        # 选项卡
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        # 选项卡切换时，确保录入表列宽立即刷新
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 录入页
        self.tab_entry = QWidget(); self.tabs.addTab(self.tab_entry, "① 成绩录入")
        self._build_entry_tab()

        # 统计页
        self.tab_stats = QWidget(); self.tabs.addTab(self.tab_stats, "② 排名统计")
        self._build_stats_tab()

        # 查询页
        self.tab_query = QWidget(); self.tabs.addTab(self.tab_query, "③ 条件查询")
        self._build_query_tab()

    def _build_entry_tab(self):
        layout = QVBoxLayout(self.tab_entry)
        tip = QLabel("提示：初始化后在下表逐行录入各项目的名次(国家编号 1..n)。选择‘前三/前五’会自动启用/禁用第4/5名列。")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # 成绩录入表
        self.table_entry = QTableWidget(0, 9)
        self.table_entry.setHorizontalHeaderLabels([
            "项目ID", "性别", "前三/前五", "第一名", "第二名", "第三名", "第四名", "第五名", "校验状态"
        ])
        # 录入表列宽：前8列等宽，最后一列更宽；并随窗口宽度自适应
        self.table_entry.setEditTriggers(QTableWidget.AllEditTriggers)
        layout.addWidget(self.table_entry, 1)
        self._configure_entry_header()

        # 操作区
        ops = QHBoxLayout()
        self.btn_validate = QPushButton("快速校验全部")
        self.btn_validate.clicked.connect(self.validate_all_rows)
        self.btn_compute = QPushButton("统计得分")
        self.btn_compute.clicked.connect(self.compute_scores_and_refresh)
        self.btn_fill = QPushButton("填充示例数据（含初始化）")
        self.btn_fill.clicked.connect(self.fill_example_data)
        ops.addWidget(self.btn_validate)
        ops.addWidget(self.btn_compute)
        ops.addWidget(self.btn_fill)
        ops.addStretch(1)
        layout.addLayout(ops)

    def _build_stats_tab(self):
        layout = QVBoxLayout(self.tab_stats)

        # 排序按钮区
        sort_bar = QHBoxLayout()
        sort_bar.addWidget(QLabel("排序方式："))
        self.btn_sort_id = QPushButton("按国家编号↑")
        self.btn_sort_total = QPushButton("按总分↓")
        self.btn_sort_male = QPushButton("按男团总分↓")
        self.btn_sort_female = QPushButton("按女团总分↓")
        for b in (self.btn_sort_id, self.btn_sort_total, self.btn_sort_male, self.btn_sort_female):
            sort_bar.addWidget(b)
        sort_bar.addStretch(1)
        layout.addLayout(sort_bar)

        self.btn_sort_id.clicked.connect(lambda: self.refresh_stats_table(sort_key=("id", True)))
        self.btn_sort_total.clicked.connect(lambda: self.refresh_stats_table(sort_key=("total", False)))
        self.btn_sort_male.clicked.connect(lambda: self.refresh_stats_table(sort_key=("male", False)))
        self.btn_sort_female.clicked.connect(lambda: self.refresh_stats_table(sort_key=("female", False)))

        # 统计表
        self.table_stats = QTableWidget(0, 4)
        self.table_stats.setHorizontalHeaderLabels(["国家编号", "总分", "男团总分", "女团总分"])
        # 让所有列等比例分配宽度
        self.table_stats.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_stats, 1)

    def _build_query_tab(self):
        layout = QVBoxLayout(self.tab_query)

        # 按国家查
        box_country = QGroupBox("按国家编号查询")
        f1 = QFormLayout(box_country)
        self.edit_query_country = QLineEdit(); self.edit_query_country.setValidator(QIntValidator(1, 999999))
        btn_q1 = QPushButton("查询国家参赛情况")
        btn_q1.clicked.connect(self.query_by_country)
        f1.addRow("国家编号:", self.edit_query_country)
        f1.addRow(btn_q1)
        layout.addWidget(box_country)

        self.table_q_country = QTableWidget(0, 5)
        self.table_q_country.setHorizontalHeaderLabels(["项目ID", "性别", "名次", "得分", "说明"])
        # 让所有列等比例分配宽度
        self.table_q_country.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_q_country)

        # 按项目查
        box_event = QGroupBox("按项目编号查询")
        f2 = QFormLayout(box_event)
        self.edit_query_event = QLineEdit(); self.edit_query_event.setValidator(QIntValidator(1, 10**9))
        btn_q2 = QPushButton("查询该项目获奖国家")
        btn_q2.clicked.connect(self.query_by_event)
        f2.addRow("项目编号:", self.edit_query_event)
        f2.addRow(btn_q2)
        layout.addWidget(box_event)

        self.table_q_event = QTableWidget(0, 3)
        self.table_q_event.setHorizontalHeaderLabels(["名次", "国家编号", "得分"])
        # 让所有列等比例分配宽度
        self.table_q_event.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_q_event)

    # --------------------------- 列宽控制（录入表） ---------------------------
    def _configure_entry_header(self):
        """将录入表设置为可交互列宽，并做比例分配：0..7 等宽，列8为双倍。"""
        header = self.table_entry.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(60)
        # 监听视口尺寸变化，避免初次显示时留白
        self.table_entry.viewport().installEventFilter(self)
        self._resize_entry_columns()

    def _resize_entry_columns(self):
        if not hasattr(self, 'table_entry'):
            return
        # 优先用 viewport 宽度；若为 0，退化为表格宽度估计
        total_w = self.table_entry.viewport().width()
        if total_w <= 0:
            total_w = max(0, self.table_entry.width() - self.table_entry.verticalHeader().width() - 4)
        # 10 份：前8列各1份，最后一列2份
        unit = max(1, total_w // 10)
        for c in range(8):
            self.table_entry.setColumnWidth(c, unit)
        self.table_entry.setColumnWidth(8, unit * 2)

    def _on_tab_changed(self, idx: int):
        # 切到录入页立即刷新列宽，避免初次显示留白
        w = self.tabs.widget(idx)
        if w is self.tab_entry:
            QTimer.singleShot(0, self._resize_entry_columns)

    def showEvent(self, event):
        super().showEvent(event)
        # 窗口首次显示后，等布局稳定再拉伸一次，修复初始右侧留白
        QTimer.singleShot(0, self._resize_entry_columns)

    def eventFilter(self, obj, event):
        # 视口尺寸变化时重算列宽（例如首次布局、切换 DPI、显示滚动条等）
        if obj is getattr(self, 'table_entry', None) and event.type() == QEvent.Resize:
            self._resize_entry_columns()
        if hasattr(self, 'table_entry') and obj is self.table_entry.viewport() and event.type() == QEvent.Resize:
            self._resize_entry_columns()
        return super().eventFilter(obj, event)

    def _resize_entry_columns(self):
        if not hasattr(self, 'table_entry'):
            return
        total_w = max(0, self.table_entry.viewport().width())
        # 10 份：前8列各1份，最后一列2份
        unit = max(1, total_w // 10)
        for c in range(8):
            self.table_entry.setColumnWidth(c, unit)
        self.table_entry.setColumnWidth(8, unit * 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 窗口尺寸变化时，重新按比例分配录入表列宽
        if hasattr(self, 'table_entry'):
            self._resize_entry_columns()

    # --------------------------- 初始化/构表 ---------------------------
    def on_initialize(self):
        try:
            n = int(self.edit_n.text())
            m = int(self.edit_m.text())
            w = int(self.edit_w.text())
        except ValueError:
            QMessageBox.warning(self, "参数错误", "请正确输入 n / m / w 为整数。")
            return
        if n < 1 or m < 0 or w < 0:
            QMessageBox.warning(self, "参数错误", "需满足 n>=1, m>=0, w>=0。")
            return
        if m == 0 and w == 0:
            QMessageBox.warning(self, "参数错误", "至少需要 1 个项目。")
            return

        self.n_countries, self.m_men, self.w_women = n, m, w
        total_events = m + w

        # 重置录入表
        self.table_entry.setRowCount(total_events)
        self.event_configs.clear()

        for row in range(total_events):
            event_id = row + 1
            gender = '男' if event_id <= m else '女'
            # 项目ID
            self._set_item(self.table_entry, row, 0, str(event_id), editable=False)
            # 性别
            self._set_item(self.table_entry, row, 1, gender, editable=False)
            # 前三/前五
            combo = QComboBox()
            combo.addItems(["前三", "前五"])  # 默认前三
            combo.currentIndexChanged.connect(lambda _i, r=row: self.on_topn_changed(r))
            self.table_entry.setCellWidget(row, 2, combo)
            # 排名输入(1..5)
            for col in range(3, 8):  # 第1名~第5名
                le = QLineEdit(); le.setPlaceholderText("国家编号")
                le.setValidator(QIntValidator(1, self.n_countries))
                self.table_entry.setCellWidget(row, col, le)
            # 校验状态
            self._set_item(self.table_entry, row, 8, "未校验", editable=False)

            # 保存配置，默认前三
            self.event_configs[row] = EventConfig(event_id=event_id, gender=gender, top_n=3)
            self._apply_topn_ui(row)

        # 初始化后立即按比例设置列宽
        self._resize_entry_columns()
        QMessageBox.information(self, "初始化完成", f"已创建 {total_events} 个项目（男 {m}、女 {w}），国家数 {n}。")

    def on_topn_changed(self, row: int):
        combo: QComboBox = self.table_entry.cellWidget(row, 2)  # type: ignore
        top_n = 3 if combo.currentText() == "前三" else 5
        cfg = self.event_configs.get(row)
        if cfg:
            cfg.top_n = top_n
        self._apply_topn_ui(row)

    def _apply_topn_ui(self, row: int):
        """根据 top_n 启/禁用第4/5名输入。"""
        cfg = self.event_configs[row]
        enable_4_5 = (cfg.top_n == 5)
        for col in (6, 7):  # 第四名、第 五名列
            widget = self.table_entry.cellWidget(row, col)
            if widget:
                widget.setEnabled(enable_4_5)
                if not enable_4_5:
                    # 清空以防误统计
                    widget.setProperty('text', '')
                    if isinstance(widget, QLineEdit):
                        widget.clear()

    # --------------------------- 校验与读表 ---------------------------
    def validate_row(self, row: int) -> Tuple[bool, str]:
        cfg = self.event_configs[row]
        # 读取名次
        ranks: List[Optional[int]] = []
        for idx in range(5):
            col = 3 + idx
            widget = self.table_entry.cellWidget(row, col)
            if isinstance(widget, QLineEdit) and widget.isEnabled():
                txt = widget.text().strip()
                ranks.append(int(txt) if txt else None)
            else:
                ranks.append(None)

        # 至少前三应完整；如选择前五，则前四/前五也应完整
        need = 3 if cfg.top_n == 3 else 5
        # 基础完整性
        for i in range(need):
            if ranks[i] is None:
                return False, f"缺少第{i+1}名"
            if not (1 <= ranks[i] <= self.n_countries):
                return False, f"第{i+1}名超范围(1..{self.n_countries})"

        # 不得重复
        seen = set()
        for i in range(need):
            r = ranks[i]
            if r in seen:
                return False, f"国家编号重复: {r}"
            seen.add(r)

        return True, "通过"

    def validate_all_rows(self):
        total = self.table_entry.rowCount()
        all_ok = True
        for row in range(total):
            ok, msg = self.validate_row(row)
            self._set_item(self.table_entry, row, 8, msg, editable=False)
            if not ok:
                all_ok = False
        if all_ok:
            QMessageBox.information(self, "校验完成", "所有项目录入有效。")
        else:
            QMessageBox.warning(self, "校验完成", "存在录入问题，请根据‘校验状态’列逐项修正。")

    def _read_event_row(self, row: int) -> Tuple[EventConfig, List[int]]:
        cfg = self.event_configs[row]
        ranks: List[int] = []
        need = 3 if cfg.top_n == 3 else 5
        for i in range(need):
            col = 3 + i
            widget = self.table_entry.cellWidget(row, col)
            val = 0
            if isinstance(widget, QLineEdit):
                txt = widget.text().strip()
                if txt:
                    val = int(txt)
            ranks.append(val)
        return cfg, ranks

    # --------------------------- 统计与展示 ---------------------------
    def compute_scores(self) -> Tuple[Dict[int, int], Dict[int, int], Dict[int, int]]:
        if self.n_countries <= 0:
            return {}, {}, {}
        total_scores = {i: 0 for i in range(1, self.n_countries + 1)}
        male_scores = {i: 0 for i in range(1, self.n_countries + 1)}
        female_scores = {i: 0 for i in range(1, self.n_countries + 1)}

        total_events = self.table_entry.rowCount()
        for row in range(total_events):
            cfg, ranks = self._read_event_row(row)
            if cfg.top_n == 3 and len(ranks) == 3:
                pts = POINTS_TOP3
            else:
                pts = POINTS_TOP5

            for pos, country in enumerate(ranks):
                if country is None or country == 0:
                    # 该项目尚未完整录入，跳过
                    continue
                if not (1 <= country <= self.n_countries):
                    continue
                score = pts[pos]
                total_scores[country] += score
                if cfg.gender == '男':
                    male_scores[country] += score
                else:
                    female_scores[country] += score
        return total_scores, male_scores, female_scores

    def compute_scores_and_refresh(self):
        self.validate_all_rows()
        self.s_total, self.s_male, self.s_female = self.compute_scores()
        self.refresh_stats_table()
        self.tabs.setCurrentWidget(self.tab_stats)

    def refresh_stats_table(self, sort_key: Tuple[str, bool] = ("id", True)):
        if not hasattr(self, 's_total'):
            self.s_total, self.s_male, self.s_female = self.compute_scores()
        rows = []
        for cid in range(1, self.n_countries + 1):
            rows.append({
                'id': cid,
                'total': self.s_total.get(cid, 0),
                'male': self.s_male.get(cid, 0),
                'female': self.s_female.get(cid, 0)
            })
        key, asc = sort_key
        rows.sort(key=lambda x: x[key], reverse=not asc)

        self.table_stats.setRowCount(len(rows))
        for r, rec in enumerate(rows):
            self._set_item(self.table_stats, r, 0, str(rec['id']))
            self._set_item(self.table_stats, r, 1, str(rec['total']))
            self._set_item(self.table_stats, r, 2, str(rec['male']))
            self._set_item(self.table_stats, r, 3, str(rec['female']))

    # --------------------------- 示例数据填充 ---------------------------
    def fill_example_data(self):
        """一键填充示例：n=7, m=3, w=2，并预置每个项目的名次。"""
        # 1) 设置规模并初始化
        self.edit_n.setText("7"); self.edit_m.setText("3"); self.edit_w.setText("2")
        self.on_initialize()

        # 2) 逐项目配置：("前三"/"前五", [第一, 第二, 第三, (可选)第四, (可选)第五])
        sample = [
            ("前五", [1, 2, 3, 4, 5]),
            ("前三", [3, 1, 2]),
            ("前五", [2, 4, 6, 1, 7]),
            ("前三", [5, 4, 1]),
            ("前五", [7, 5, 2, 3, 6]),
        ]
        for row, (mode, ranks) in enumerate(sample):
            combo = self.table_entry.cellWidget(row, 2)
            if isinstance(combo, QComboBox):
                combo.setCurrentText(mode)
                self.on_topn_changed(row)
            for i, val in enumerate(ranks):
                w = self.table_entry.cellWidget(row, 3 + i)
                if isinstance(w, QLineEdit):
                    w.setText(str(val))

        # 3) 校验并统计，切换到统计页
        self.validate_all_rows()
        self.compute_scores_and_refresh()
        self.tabs.setCurrentWidget(self.tab_stats)

    # --------------------------- 查询 ---------------------------
    def query_by_country(self):
        if self.n_countries <= 0:
            QMessageBox.warning(self, "未初始化", "请先在顶部完成初始化并录入成绩。")
            return
        try:
            cid = int(self.edit_query_country.text())
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的国家编号。")
            return
        if not (1 <= cid <= self.n_countries):
            QMessageBox.warning(self, "输入错误", f"国家编号需在 1..{self.n_countries}。")
            return

        # 统计（确保最新）
        self.s_total, self.s_male, self.s_female = self.compute_scores()

        # 遍历每个项目，找到该国家的名次与得分
        out: List[Tuple[int, str, Optional[int], int, str]] = []
        total_events = self.table_entry.rowCount()
        for row in range(total_events):
            cfg, ranks = self._read_event_row(row)
            pts = POINTS_TOP3 if cfg.top_n == 3 else POINTS_TOP5
            place = None; score = 0; note = ""
            if ranks:
                for i, c in enumerate(ranks):
                    if c == cid:
                        place = i + 1
                        score = pts[i]
                        break
            if place is None:
                note = "未上榜"
            out.append((cfg.event_id, cfg.gender, place, score, note))

        # 填表
        self.table_q_country.setRowCount(len(out))
        for r, (eid, g, place, score, note) in enumerate(out):
            self._set_item(self.table_q_country, r, 0, str(eid))
            self._set_item(self.table_q_country, r, 1, g)
            self._set_item(self.table_q_country, r, 2, (str(place) if place else "-"))
            self._set_item(self.table_q_country, r, 3, str(score))
            self._set_item(self.table_q_country, r, 4, note)

    def query_by_event(self):
        if self.n_countries <= 0:
            QMessageBox.warning(self, "未初始化", "请先在顶部完成初始化并录入成绩。")
            return
        try:
            eid = int(self.edit_query_event.text())
        except ValueError:
            QMessageBox.warning(self, "输入错误", "请输入有效的项目编号。")
            return
        total_events = self.table_entry.rowCount()
        if not (1 <= eid <= total_events):
            QMessageBox.warning(self, "输入错误", f"项目编号需在 1..{total_events}。")
            return

        row = eid - 1
        cfg, ranks = self._read_event_row(row)
        pts = POINTS_TOP3 if cfg.top_n == 3 else POINTS_TOP5

        # 输出该项目的上榜国家
        self.table_q_event.setRowCount(len(ranks))
        for i, cid in enumerate(ranks):
            self._set_item(self.table_q_event, i, 0, f"第{i+1}名")
            self._set_item(self.table_q_event, i, 1, str(cid) if cid else "-")
            self._set_item(self.table_q_event, i, 2, str(pts[i]))

    # --------------------------- 工具函数 ---------------------------
    def _set_item(self, table: QTableWidget, row: int, col: int, text: str, editable: bool = True):
        item = QTableWidgetItem(text)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if editable:
            flags |= Qt.ItemIsEditable
        item.setFlags(flags)
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)


def main():
    import sys
    from PyQt5 import QtGui

    app = QApplication(sys.argv)

    if sys.platform.startswith("win"):
        # 优先用 UI 版微软雅黑，更适合界面显示；没有就回退
        families = ["Microsoft YaHei UI", "Microsoft YaHei"]
        db = QtGui.QFontDatabase()
        for fam in families:
            if fam in db.families():
                app.setFont(QtGui.QFont(fam, 11))  # 这里 11 是字号，可调整
                break

    # 针对高分屏做一点点优化
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    win = OlympicsScoringApp()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
