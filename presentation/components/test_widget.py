import json

from PyQt5.QtCore import Qt, QLine, QEvent
from PyQt5.QtGui import QGuiApplication, QKeySequence, QColor, QPen, QFont
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QWidget, QVBoxLayout, QLabel, QComboBox, QTextEdit, QCheckBox, \
    QTableWidgetItem, QLineEdit, QTableWidget, QHeaderView, QShortcut, QMessageBox, QStyledItemDelegate

import qtawesome as qta

import genson

from controller.request_assistant_controller import RequestsAssistantController
from presentation.components.json_text_edit import JSONTextEdit
from presentation.components.parameter_table import DynamicCompleterDelegate, ParameterTableWidget, DynamicValueDelegate


class CollapsibleTestWidget(QWidget):
    def __init__(self, title, on_rename, on_duplicate, on_delete, on_run, parent=None):
        super().__init__(parent)

        main = QVBoxLayout(self)
        main.setAlignment(Qt.AlignTop)

        self.assist_ctrl = RequestsAssistantController()

        self.toggle_btn = QPushButton(title)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self._toggle)

        self.run_btn = QPushButton(qta.icon("fa5s.play", color="green"), "")
        self.run_btn.setToolTip("Executar Teste")
        self.run_btn.setFixedSize(30, 30)
        self.run_btn.clicked.connect(on_run)

        self.status_lbl = QLabel()

        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        header_bar.addWidget(self.toggle_btn)
        header_bar.addWidget(self.status_lbl)
        header_bar.addStretch()
        header_bar.addWidget(self.run_btn, alignment=Qt.AlignRight)

        main.addLayout(header_bar)

        self.method_combo = QComboBox()
        self.method_combo.setEnabled(False)
        self.method_combo.addItems(["GET", "POST", "PUT", "DELETE", "PATCH"])
        self.method_combo.setToolTip("Método HTTP")
        self.method_combo.setFixedWidth(100)
        self.method_combo.setCurrentText("GET")
        main.addWidget(self.method_combo)

        self.url_input = QLineEdit()
        self.url_input.setEnabled(False)
        self.url_input.setToolTip("URL do endpoint")
        self.url_input.setMinimumWidth(300)
        main.addWidget(self.url_input)

        header_bar = QHBoxLayout()
        header_bar.addWidget(self.toggle_btn)
        for icon, tip, cb in (
            ("fa5s.pencil-alt", "Renomear", on_rename),
            ("fa5s.copy",        "Duplicar", on_duplicate),
            ("fa5s.trash",       "Remover",  on_delete),
        ):
            btn = QPushButton(qta.icon(icon, color="gray"), "")
            btn.setToolTip(tip)
            btn.setFixedSize(24, 24)
            btn.clicked.connect(cb)
            header_bar.addWidget(btn)
        header_bar.addStretch(1)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content.setVisible(False)

        # 1) Query Parameters
        self.query_table = ParameterTableWidget(minimumHeight=300)
        self.query_table.setItemDelegateForColumn(1, DynamicCompleterDelegate(self, True, self.query_table))
        self.query_table.setItemDelegateForColumn(2, DynamicValueDelegate(self, True, self.query_table))
        add_q = QPushButton("Adicionar Query Param")
        add_q.clicked.connect(lambda: self._add_row(self.query_table))
        self.content_layout.addWidget(QLabel("Query Parameters:"))
        self.content_layout.addWidget(self.query_table)
        self.content_layout.addWidget(add_q, alignment=Qt.AlignRight)

        # 2) Headers
        self.headers_table = ParameterTableWidget(minimumHeight=300)
        self.headers_table.setItemDelegateForColumn(1, DynamicCompleterDelegate(self, False, self.headers_table))
        self.headers_table.setItemDelegateForColumn(2, DynamicValueDelegate(self, False, self.headers_table))
        add_h = QPushButton("Adicionar Header")
        add_h.clicked.connect(lambda: self._add_row(self.headers_table))
        self.content_layout.addWidget(QLabel("Headers:"))
        self.content_layout.addWidget(self.headers_table)
        self.content_layout.addWidget(add_h, alignment=Qt.AlignRight)

        # 3) Body
        self.body_edit = JSONTextEdit()
        self.body_edit.setPlaceholderText("Digite o corpo do teste aqui…")
        self.body_edit.setMinimumHeight(300)
        self.content_layout.addWidget(QLabel("Body:"))
        self.content_layout.addWidget(self.body_edit)

        exp_bar = QHBoxLayout()
        exp_bar.addWidget(QLabel("Status esperado:"))
        self.expected_status = QComboBox()
        self.expected_status.addItems([str(s) for s in (200, 201, 204, 400, 404, 500)])
        exp_bar.addWidget(self.expected_status)
        self.content_layout.addLayout(exp_bar)

        self.expected_body = QTextEdit()
        self.expected_body.setPlaceholderText("Corpo de resposta esperado…")
        self.expected_body.setMinimumHeight(300)
        self.content_layout.addWidget(QLabel("Body esperado:"))
        self.content_layout.addWidget(self.expected_body)

        self.assertions_table = ParameterTableWidget(minimumHeight=300)
        self.assertions_table.setColumnCount(3)
        self.assertions_table.setHorizontalHeaderLabels(["Tipo", "Campo/JSON Path", "Valor Esperado"])
        self.assertions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.content_layout.addWidget(QLabel("Verificações:"))
        self.content_layout.addWidget(self.assertions_table)

        add_assert_btn = QPushButton("Adicionar Verificação")
        add_assert_btn.clicked.connect(self.add_assertion_row)
        self.content_layout.addWidget(add_assert_btn, alignment=Qt.AlignRight)

        self.content_layout.addWidget(QLabel("JSON Schema:"))
        self.schema_edit = QTextEdit()
        self.schema_edit.setPlaceholderText("Cole ou gere aqui o JSON Schema para validação…")
        self.schema_edit.setMinimumHeight(200)
        self.content_layout.addWidget(self.schema_edit)

        btn_gen_schema = QPushButton("🧬 Gerar Schema")
        btn_gen_schema.setToolTip("Gera um JSON Schema a partir do corpo do teste")
        btn_gen_schema.clicked.connect(self.generate_schema)
        self.content_layout.addWidget(btn_gen_schema, alignment=Qt.AlignRight)

        main.addLayout(header_bar)
        main.addWidget(self.content)

        for tbl in (self.query_table, self.headers_table, self.assertions_table):
            tbl.viewport().installEventFilter(self)

        self._register_shortcuts()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonDblClick:
            for tbl in (self.query_table, self.headers_table, self.assertions_table):
                if obj is tbl.viewport():
                    pos = event.pos()
                    idx = tbl.indexAt(pos)
                    if idx.row() == -1:
                        self._add_row(tbl)
                        return True
        return super().eventFilter(obj, event)

    def _toggle(self):
        self.content.setVisible(self.toggle_btn.isChecked())

    def _add_row(self, table):
        """Adiciona uma nova linha na tabela especificada."""
        if table is self.assertions_table:
            self.add_assertion_row()
            return

        r = table.rowCount()
        table.insertRow(r)
        cb = QCheckBox(); cb.setChecked(True)
        table.setCellWidget(r, 0, cb)
        table.setItem(r, 1, QTableWidgetItem(""))
        table.setItem(r, 2, QTableWidgetItem(""))

    def get_expected_status(self):
        return int(self.expected_status.currentText())

    def get_expected_body(self):
        return self.expected_body.toPlainText().strip()

    def add_param_row(self, table, name, value, is_required):
        r = table.rowCount()
        table.insertRow(r)
        cb = QCheckBox()
        cb.setChecked(True)
        cb.setToolTip("Habilitar este parâmetro")
        if is_required:
            cb.setEnabled(False)
            cb.setToolTip("Este parâmetro é obrigatório e não pode ser desabilitado")

        table.setCellWidget(r, 0, cb)
        item_name = QTableWidgetItem(name)
        if is_required:
            item_name.setToolTip("Campo obrigatório")
            font: QFont = item_name.font()
            font.setBold(True)
            item_name.setFont(font)
        table.setItem(r, 1, item_name)
        table.setItem(r, 2, QTableWidgetItem(value if value else ""))

    def add_assertion_row(self):
        row = self.assertions_table.rowCount()
        self.assertions_table.insertRow(row)

        combo = QComboBox()
        combo.addItems([
            "HTTP Status Equals",
            "Body Contains",
            "Body Equals",
            "Header Equals",
            "JSON Path Equals",
            "Regex Matches"
        ])
        self.assertions_table.setCellWidget(row, 0, combo)
        self.assertions_table.setItem(row, 1, QTableWidgetItem(""))
        self.assertions_table.setItem(row, 2, QTableWidgetItem(""))

    def load_assertions(self, assertions: list[dict]):
        self.assertions_table.setRowCount(0)
        for a in assertions:
            self.add_assertion_row()
            row = self.assertions_table.rowCount() - 1
            widget = self.assertions_table.cellWidget(row, 0)
            widget.setCurrentText(a.get("type", ""))
            self.assertions_table.item(row, 1).setText(str(a.get("target", "")))
            self.assertions_table.item(row, 2).setText(str(a.get("expected", "")))

    def get_assertions(self) -> list[dict]:
        result = []
        for row in range(self.assertions_table.rowCount()):
            typ = self.assertions_table.cellWidget(row, 0).currentText()
            target = self.assertions_table.item(row, 1).text()
            exp = self.assertions_table.item(row, 2).text()
            result.append({"type": typ, "target": target, "expected": exp})
        return result

    def _register_shortcuts(self):
        shortcuts = [
            (self.query_table, lambda: self.copy_selected_rows(self.query_table), QKeySequence.Copy),
            (self.query_table, lambda: self.duplicate_selected(self.query_table), QKeySequence("Ctrl+D")),
            (self.query_table, lambda: self.paste_rows(self.query_table), QKeySequence.Paste),
            (self.query_table, lambda: self.delete_rows(self.query_table), QKeySequence.Delete),
            (self.headers_table, lambda: self.copy_selected_rows(self.headers_table), QKeySequence.Copy),
            (self.headers_table, lambda: self.paste_rows(self.headers_table), QKeySequence.Paste),
            (self.headers_table, lambda: self.delete_rows(self.headers_table), QKeySequence.Delete),
            (self.assertions_table, lambda: self.delete_rows(self.assertions_table), QKeySequence.Delete),
        ]
        for widget, callback, seq in shortcuts:
            sc = QShortcut(seq, widget)
            sc.activated.connect(callback)
            sc.setContext(Qt.WidgetShortcut)


    def duplicate_selected(self, table):
        self.copy_selected_rows(table)
        self.paste_rows(table)

    def copy_selected_rows(self, table):
        """Copia key e value das linhas selecionadas para o clipboard."""
        rows = table.selectionModel().selectedRows()
        lines = []
        for idx in sorted(rows, key=lambda x: x.row()):
            r = idx.row()
            key = table.item(r, 1)
            val = table.item(r, 2)
            if key and val:
                lines.append(f"{key.text()}\t{val.text()}")
        QGuiApplication.clipboard().setText("\n".join(lines))

    def paste_rows(self, table):
        """Cola do clipboard nas colunas Key/Value da tabela."""
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            return
        for line in text.splitlines():
            parts = line.split("\t")
            key = parts[0]
            value = parts[1] if len(parts) > 1 else ""
            r = table.rowCount()
            table.insertRow(r)
            cb = QCheckBox()
            cb.setChecked(True)
            table.setCellWidget(r, 0, cb)
            table.setItem(r, 1, QTableWidgetItem(key))
            table.setItem(r, 2, QTableWidgetItem(value))

    def delete_rows(self, table):
        selection = table.selectionModel().selectedRows()
        if not selection:
            selected_cells = set(idx.row() for idx in table.selectedIndexes())
            selection = [table.model().index(row, 0) for row in selected_cells]
        for idx in sorted(selection, key=lambda x: x.row(), reverse=True):
            table.removeRow(idx.row())

    def generate_schema(self):
        """Gera um JSON Schema com base no conteúdo atual do body_edit."""
        try:
            body_text = self.body_edit.toPlainText().strip() or "{}"
            data = json.loads(body_text)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Erro de JSON", f"Corpo inválido:\n{e}")
            return

        builder = genson.SchemaBuilder()
        builder.add_object(data)
        schema = builder.to_schema()
        self.schema_edit.setPlainText(json.dumps(schema, indent=2))

    def load_schema(self, schema_str: str):
        """Carrega o schema salvo na configuração do teste."""
        self.schema_edit.setPlainText(schema_str or "")

    def get_schema(self) -> str:
        """Retorna o JSON Schema atual como string."""
        return self.schema_edit.toPlainText().strip()