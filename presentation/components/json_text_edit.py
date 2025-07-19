import json
import re
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QColor, QTextFormat, QPainter
from PyQt5.QtCore import Qt, QSize, QRect, pyqtSignal, QPoint
from PyQt5.QtWidgets import QWidget, QPlainTextEdit, QLabel, QTextEdit


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)


class JSONTextEdit(QPlainTextEdit):
    jsonValidityChanged = pyqtSignal(bool)
    BRACKET_PAIRS = {'(': ')', '[': ']', '{': '}'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.suggestionProvider = None

        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

        self.notification_label = QLabel(self)
        self.notification_label.setStyleSheet("color: #e37e5c; padding:2px; font-size:16px;")
        self.notification_label.hide()

        self._suggestion = ""
        self.textChanged.connect(self._updateSuggestion)

        self._last_valid_state = None
        self.jsonValidityChanged.connect(self._on_json_validity_changed)
        self.validate_json()

    def _updateSuggestion(self):
        self.validate_json()
        if callable(self.suggestionProvider):
            tc = self.textCursor()
            tc.select(QTextCursor.WordUnderCursor)
            prefix = tc.selectedText()
            full = self.suggestionProvider(prefix)
            if full and full.startswith(prefix):
                self._suggestion = full[len(prefix):]
            else:
                self._suggestion = ""
        else:
            self._suggestion = ""
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._suggestion:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(150, 150, 150))
            cr = self.cursorRect()
            pt = QPoint(cr.x(), cr.y() + self.fontMetrics().ascent())
            painter.drawText(pt, self._suggestion)
            painter.end()

    def _insert_newline_and_indent(self):
        cursor = self.textCursor()
        cursor.insertText('\n')
        self.setTextCursor(cursor)
        block = cursor.block().previous()
        prev = block.text().rstrip()
        indent = re.match(r'(\s*)', prev).group(1)
        if prev.endswith(('{', '[')):
            indent = '    '
        cursor.insertText(indent)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        text = event.text()
        tab = '    '

        if text in ('{', '[') and not self._is_inside_string():
            block_text = cursor.block().text()
            base_indent = re.match(r'(\s*)', block_text).group(1)
            self.blockSignals(True)
            super().keyPressEvent(event)
            self.insertPlainText('\n' + base_indent + tab)
            pos = self.textCursor().position()
            closing = self.BRACKET_PAIRS[text]
            self.insertPlainText('\n' + base_indent + closing)
            new_cursor = self.textCursor()
            new_cursor.setPosition(pos)
            self.setTextCursor(new_cursor)
            self.blockSignals(False)
            self._updateSuggestion()
            return

        if event.key() == Qt.Key_Tab and self._suggestion:
            suggestion = self._suggestion
            cursor.insertText(suggestion)
            self.setTextCursor(cursor)
            if suggestion and suggestion[0] in (',', '}', ']'):
                self._insert_newline_and_indent()
            self._suggestion = ""
            return

        if text in (',', '}', ']') and not self._is_inside_string():
            super().keyPressEvent(event)
            self._insert_newline_and_indent()
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            super().keyPressEvent(event)
            prev = self.textCursor().block().previous().text().rstrip()
            indent = re.match(r'(\s*)', prev).group(1)
            self.insertPlainText(indent + ('    ' if prev.endswith(('{', '[')) else ''))
            return

        super().keyPressEvent(event)

    def _calculate_indent(self) -> str:
        txt = self.toPlainText()
        level = txt.count('{') + txt.count('[') - txt.count('}') - txt.count(']')
        level = max(level, 0)
        return ' ' * (4 * level)

    def textUnderCursor(self) -> str:
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def handleTextChanged(self):
        self.validate_json()

    def _on_json_validity_changed(self, valid: bool):
        if not valid:
            self.notification_label.setText(self.toolTip())
            self.notification_label.show()
        else:
            self.notification_label.hide()

    def validate_json(self):
        text = self.toPlainText()
        self.setExtraSelections([])
        valid, tip = True, ""
        if text.strip():
            try:
                json.loads(text)
            except json.JSONDecodeError as e:
                valid = False
                block = self.document().findBlockByNumber(e.lineno - 1)
                if block.isValid():
                    pos = block.position() + e.colno - 1
                    c = QTextCursor(self.document())
                    c.setPosition(pos)
                    c.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
                    fmt = QTextCharFormat()
                    fmt.setUnderlineColor(QColor("red"))
                    fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
                    sel = QTextEdit.ExtraSelection()
                    sel.cursor, sel.format = c, fmt
                    self.setExtraSelections([sel])
                tip = f"JSON inválido: {e.msg}"
        self.setToolTip(tip)
        if self._last_valid_state is None or self._last_valid_state != valid:
            self._last_valid_state = valid
            self.jsonValidityChanged.emit(valid)

    def focusOutEvent(self, event):
        self.validate_json()
        super().focusOutEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(),
                                              self.lineNumberAreaWidth(), cr.height()))
        lbl_h = self.notification_label.sizeHint().height()
        vp = self.viewport().geometry()
        self.notification_label.setGeometry(vp.left(), vp.bottom() - lbl_h + 1,
                                            vp.width(), lbl_h)

    def lineNumberAreaWidth(self):
        digits = len(str(self.blockCount()))
        return 10 + self.fontMetrics().width('9') * digits + 20

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(),
                                       self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#171717"))
        block = self.firstVisibleBlock()
        top = int(self.blockBoundingGeometry(block)
                  .translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        num = block.blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(Qt.white)
                painter.drawText(0, top, self.lineNumberArea.width(),
                                 self.fontMetrics().height(),
                                 Qt.AlignHCenter|Qt.AlignVCenter,
                                 str(num+1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            num += 1

    def highlightCurrentLine(self):
        sels = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#171717").lighter(160))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            sels.append(sel)
        brace = self._bracket_highlight()
        if brace:
            sels.extend(brace)
        self.setExtraSelections(sels)

    def _bracket_highlight(self):
        text = self.toPlainText()
        pos = self.textCursor().position()
        for idx in (pos-1, pos):
            if 0 <= idx < len(text):
                ch = text[idx]
                if ch in self.BRACKET_PAIRS or ch in self.BRACKET_PAIRS.values():
                    match = self._find_matching(text, idx, ch)
                    if match is not None:
                        out = []
                        for p in (idx, match):
                            c = QTextCursor(self.document())
                            c.setPosition(p)
                            c.movePosition(QTextCursor.NextCharacter,
                                           QTextCursor.KeepAnchor)
                            fmt = QTextCharFormat()
                            fmt.setBackground(QColor('orange'))
                            sel = QTextEdit.ExtraSelection()
                            sel.cursor, sel.format = c, fmt
                            out.append(sel)
                        return out
        return None

    def _find_matching(self, text, index, ch):
        opens = '([{'
        closes = ')]}'
        pairs = self.BRACKET_PAIRS
        rev = {v: k for k, v in pairs.items()}
        if ch in opens:
            stack, match = 1, pairs[ch]
            for i in range(index+1, len(text)):
                if text[i] == ch: stack += 1
                if text[i] == match: stack -= 1
                if stack == 0: return i
        elif ch in closes:
            stack, open_ch = 1, rev[ch]
            for i in range(index-1, -1, -1):
                if text[i] == ch: stack += 1
                if text[i] == open_ch: stack -= 1
                if stack == 0: return i
        return None

    def _is_inside_string(self, pos=None) -> bool:
        """
        Retorna True se a posição estiver dentro de um literal de string JSON.
        Conta aspas não-escapadas até pos.
        """
        if pos is None:
            pos = self.textCursor().position()
        txt = self.toPlainText()[:pos]
        count = 0
        escaped = False
        for ch in txt:
            if ch == '\\' and not escaped:
                escaped = True
                continue
            if ch == '"' and not escaped:
                count += 1
            escaped = False
        return (count % 2) == 1


