from PyQt5.QtWidgets import QTableWidget, QCheckBox, QHeaderView, QStyledItemDelegate, QLineEdit, QCompleter
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QTableWidgetItem, QAbstractItemView

class CompleterDelegate(QStyledItemDelegate):
    def __init__(self, items: list[str], parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        completer = QCompleter(self.items, editor)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setWidget(editor)
        editor.setCompleter(completer)
        return editor

class DynamicCompleterDelegate(QStyledItemDelegate):
    def __init__(self, screen, for_params: bool, parent=None):
        super().__init__(parent)
        self.screen = screen
        self.for_params = for_params
        self.assist_ctrl = screen.assist_ctrl

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        method = self.screen.method_combo.currentText()
        url    = self.screen.url_input.text().strip()
        if self.for_params:
            items = self.assist_ctrl.get_param_keys(method, url)
        else:
            items = self.assist_ctrl.get_header_keys(method, url)
        completer = QCompleter(items, editor)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        editor.setCompleter(completer)
        return editor


class DynamicValueDelegate(QStyledItemDelegate):
    def __init__(self, screen, for_params: bool, parent=None):
        super().__init__(parent)
        self.screen = screen
        self.for_params = for_params
        self.assist = screen.assist_ctrl

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)

        method = self.screen.method_combo.currentText()
        url    = self.screen.url_input.text().strip()
        row    = index.row()
        key = ( self.screen.query_table.item(row, 1).text()
                if self.for_params else
                self.screen.headers_table.item(row, 1).text()
              )

        if self.for_params:
            items = self.assist.get_param_values(method, url, key)
        else:
            items = self.assist.get_header_values(method, url, key)

        completer = QCompleter(items, editor)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        editor.setCompleter(completer)

        QTimer.singleShot(0, completer.complete)

        return editor

class ParameterTableWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Ativo", "Chave", "Valor"])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.setColumnWidth(0, 30)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(QAbstractItemView.InternalMove)

        self.setStyleSheet("""
            QTableWidget::item:selected,
            QTableWidget::item:hover {
                background-color: rgba(0, 120, 215, 0.1);
            }
            QTableWidget::item {
                color: white;
            }
        """)

    def dropEvent(self, event):
        if event.source() is not self or event.dropAction() != Qt.MoveAction:
            return super().dropEvent(event)

        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        dropRow = self.rowAt(event.pos().y())
        if dropRow < 0:
            dropRow = self.rowCount()

        rowsData = []
        for r in rows:
            rowData = []
            for c in range(self.columnCount()):
                if c == 0:
                    cb = self.cellWidget(r, c)
                    rowData.append(bool(cb.isChecked()) if isinstance(cb, QCheckBox) else False)
                else:
                    item = self.item(r, c)
                    rowData.append(item.text() if item else "")
            rowsData.append(rowData)

        for r in reversed(rows):
            self.removeRow(r)
            if r < dropRow:
                dropRow -= 1

        for i, rowData in enumerate(rowsData):
            self.insertRow(dropRow + i)
            for c, value in enumerate(rowData):
                if c == 0:
                    cb = QCheckBox()
                    cb.setChecked(value)
                    self.setCellWidget(dropRow + i, c, cb)
                else:
                    self.setItem(dropRow + i, c, QTableWidgetItem(value))

        event.accept()
