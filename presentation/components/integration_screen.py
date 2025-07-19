import difflib
import json
import logging
import os
import re
from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtGui import QColor, QBrush, QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem,
    QLabel, QFileDialog, QMessageBox, QInputDialog, QSplitter, QMenu, QScrollArea, QPlainTextEdit, QShortcut,
    QHeaderView, QComboBox, QToolButton
)
from PyQt5.QtCore import Qt, QPoint, QThreadPool
import qtawesome as qta
from jsonschema import validate, ValidationError

from controller.integration_tests_controller import IntegrationTestsController
from presentation.components.performance_component import PerformanceWidget
from presentation.components.test_widget import CollapsibleTestWidget
from services.integration_tests_service import JavaImportWorker
from services.test_worker import TestRunnable
from utils.requests import join_url

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegrationTestsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.import_worker = None
        self.performance_window = None
        self.setWindowTitle("Testes Integrados (Beta)")
        self.current_project = None
        self.current_controller = None
        self.current_endpoint = None
        self.logs = []
        self._running_all = False
        self._pending_tests = 0

        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(5)
        logger.info(f"ThreadPool configurado com max {self.thread_pool.maxThreadCount()} threads")

        self.total_line_breaker = 100
        self.color_map = {
            "GET": "#28a745",  # verde
            "POST": "#007bff",  # azul
            "PUT": "#fd7e14",  # laranja
            "DELETE": "#dc3545",  # vermelho
            "PATCH": "#6f42c1",  # roxo
            "OPTIONS": "#20c997",  # teal
            "HEAD": "#6c757d",  # cinza
            "CONSUMER": "#ffc107"  # amarelo
        }

        self.setMinimumSize(700, 400)
        self.controller = IntegrationTestsController()
        self._setup_ui()
        self.load_projects()

    def _setup_ui(self):
        splitter = QSplitter(Qt.Horizontal, self)

        btn_new_proj = QPushButton()
        btn_new_proj.setIcon(qta.icon("fa5s.plus-circle", color="orange"))
        btn_new_proj.setFixedSize(36, 36)
        btn_new_proj.setToolTip("Novo Projeto")
        btn_new_proj.clicked.connect(self.on_new_project)

        btn_sel_proj = QPushButton()
        btn_sel_proj.setIcon(qta.icon("fa5s.folder-open", color="orange"))
        btn_sel_proj.setFixedSize(36, 36)
        btn_sel_proj.setToolTip("Selecionar Projeto Existente")
        btn_sel_proj.clicked.connect(self.on_import_java_project)

        btn_import = QPushButton()
        btn_import.setIcon(qta.icon("fa5s.file-import", color="orange"))
        btn_import.setFixedSize(36, 36)
        btn_import.setToolTip("Faça upload de um arquivo .java e gere endpoints automaticamente")
        btn_import.clicked.connect(self.on_import_java)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(btn_new_proj)
        top_buttons.addWidget(btn_sel_proj)
        top_buttons.addWidget(btn_import)
        top_buttons.addStretch(1)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Método", "Endpoint"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        self.tree.itemSelectionChanged.connect(self.on_tree_selected)

        self.delete_shortcut = QShortcut(QKeySequence.Delete, self.tree)
        self.delete_shortcut.setContext(Qt.WidgetShortcut)
        self.delete_shortcut.activated.connect(self.on_tree_delete)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.addLayout(top_buttons)
        sidebar_layout.addWidget(self.tree)
        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar_layout)
        splitter.addWidget(sidebar_widget)

        main_layout = QVBoxLayout()

        self.info_label = QLabel("Selecione um projeto ou controlador para ver detalhes.")
        main_layout.addWidget(self.info_label)

        header_btn_layout = QHBoxLayout()
        header_btn_layout.setAlignment(Qt.AlignRight)
        self.btn_new = QPushButton("➕ Novo Teste")
        self.btn_new.setToolTip("Cria um novo teste para o endpoint selecionado")
        self.btn_new.setEnabled(False)
        header_btn_layout.addWidget(self.btn_new)

        self.btn_ai = QPushButton("🧠 Gerar Testes (IA)")
        self.btn_ai.setToolTip("Use IA para gerar casos de teste automaticamente")
        self.btn_ai.clicked.connect(self.on_generate_tests_ai)
        header_btn_layout.addWidget(self.btn_ai)
        main_layout.addLayout(header_btn_layout)

        self.tests_area = QWidget()
        self.tests_layout = QVBoxLayout(self.tests_area)
        self.tests_layout.setAlignment(Qt.AlignTop)

        self.tests_scroll = QScrollArea()
        self.tests_scroll.setWidgetResizable(True)
        self.tests_scroll.setWidget(self.tests_area)

        main_layout.addWidget(self.tests_scroll)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignRight)

        self.run_all_btn = QPushButton("▶ Executar Todos os Testes")
        self.run_all_btn.setToolTip("Executa todos os testes deste endpoint")
        self.run_all_btn.clicked.connect(self.on_run_all_tests)
        btn_layout.addWidget(self.run_all_btn)

        btn_perf = QPushButton("🏃 Performance")
        btn_perf.setToolTip("Executar teste de carga/performance")
        btn_perf.clicked.connect(self.on_performance)
        btn_layout.addWidget(btn_perf)

        export_btn = QToolButton()
        export_btn.setText("📤 Exportar")
        export_btn.setToolTip("Escolha o formato de exportação")

        menu = QMenu(export_btn)
        act_pytest = menu.addAction("pytest")
        act_insomnia = menu.addAction("Insomnia Collection")
        act_hoppscotch = menu.addAction("Hoppscotch")

        act_pytest.triggered.connect(self.on_export_pytest)
        act_insomnia.triggered.connect(self.on_export_insomnia)
        act_hoppscotch.triggered.connect(self.on_export_hoppscotch)
        export_btn.setMenu(menu)

        export_btn.setPopupMode(QToolButton.InstantPopup)
        btn_layout.addWidget(export_btn)

        main_layout.addLayout(btn_layout)

        filter_layout = QHBoxLayout()
        filter_layout.setAlignment(Qt.AlignLeft)
        filter_layout.addWidget(QLabel("Filtrar por teste:"))
        self.log_filter_combo = QComboBox()
        self.log_filter_combo.setToolTip("Selecione um teste para filtrar os logs")
        self.log_filter_combo.setMinimumWidth(500)
        self.log_filter_combo.addItem("Todos")
        self.log_filter_combo.setEnabled(False)
        self.log_filter_combo.currentIndexChanged.connect(self.refresh_log_view)
        filter_layout.addWidget(self.log_filter_combo)

        main_layout.addLayout(filter_layout)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Aqui aparecem os logs de execução…")
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self.open_log_context_menu)
        main_layout.addWidget(self.log_view)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        splitter.addWidget(main_widget)

        layout = QHBoxLayout(self)
        layout.addWidget(splitter)

    def open_log_context_menu(self, pos):
        menu = self.log_view.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction("Limpar Log", self.clear_logs)
        menu.exec_(self.log_view.mapToGlobal(pos))

    def clear_logs(self):
        self.logs.clear()
        self.log_view.clear()

    def refresh_log_view(self):
        selected = self.log_filter_combo.currentText()
        self.log_view.clear()
        for test_name, entry in self.logs:
            if selected == "Todos" or test_name == selected:
                self.log_view.appendPlainText(entry)

    def append_log(self, message, test_name=None):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if test_name:
            entry = f"{ts} [{test_name}] – {message}"
        else:
            entry = f"{ts} – {message}"
        self.logs.append((test_name, entry))
        if not self.log_filter_combo.isEnabled() or self.log_filter_combo.currentText() == "Todos" or test_name == self.log_filter_combo.currentText():
            self.log_view.appendPlainText(entry)

    def load_projects(self):
        self.tree.setUpdatesEnabled(False)
        self.tree.clear()
        data = self.controller.get_projects()
        for project, project_data in data.items():
            proj_item = QTreeWidgetItem([project])
            proj_item.setData(0, Qt.UserRole, ("project", project))
            for ctrl, ctrl_data in project_data.get("controllers", {}).items():
                ctrl_item = QTreeWidgetItem([ctrl])
                ctrl_item.setData(0, Qt.UserRole, ("controller", project, ctrl))
                for ep, ep_data in ctrl_data.get("endpoints", {}).items():
                    method = ep_data.get("method", "GET").upper()
                    ep_item = QTreeWidgetItem([f"{method}", ep])
                    ep_item.setData(0, Qt.UserRole, ("endpoint", project, ctrl, ep))
                    brush_method = QBrush(QColor(self.color_map.get(method, "#000000")))
                    ep_item.setForeground(0, brush_method)
                    ep_item.setForeground(1, QBrush(QColor("#ffffff")))
                    ctrl_item.addChild(ep_item)
                proj_item.addChild(ctrl_item)
            self.tree.addTopLevelItem(proj_item)
            proj_item.setExpanded(True)

        self.tree.setUpdatesEnabled(True)
        logger.info("[IntegrationTestsScreen] Árvore de endpoints recarregada")

    def open_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        menu = QMenu(self)
        if data and data[0] == "project":
            menu.addAction("Adicionar controlador", lambda: self.on_new_controller(item))
            menu.addSeparator()
            menu.addAction("Editar URL base", lambda: self.on_edit_base_url(item))
            menu.addSeparator()
            menu.addAction("Renomear projeto", lambda: self.on_rename_project(item))
            menu.addSeparator()
            menu.addAction("Selecionar diretório", lambda: self.on_select_project_path(item))
            menu.addSeparator()
            menu.addAction("Remover projeto", lambda: self.on_remove_project(item))
            menu.addSeparator()
            menu.addAction("Exportar Projeto", lambda: self.on_export_project(item))
        elif data and data[0] == "controller":
            menu.addAction("Adicionar endpoint", lambda: self.on_new_endpoint(item))
            menu.addSeparator()
            menu.addAction("Editar path do controlador", lambda: self.on_edit_controller_path(item))
            menu.addSeparator()
            menu.addAction("Renomear controlador", lambda: self.on_rename_controller(item))
            menu.addSeparator()
            menu.addAction("Remover controlador", lambda: self.on_remove_controller(item))
            menu.addSeparator()
            menu.addAction("Exportar Controlador", lambda: self.on_export_controller(item))
        elif data and data[0] == "endpoint":
            menu.addAction("Editar path do endpoint", lambda: self.on_edit_endpoint_path(item))
            menu.addSeparator()
            menu.addAction("Renomear endpoint", lambda: self.on_rename_endpoint(item))
            menu.addSeparator()
            menu.addAction("Duplicar endpoint", lambda: self.on_duplicate_endpoint(item))
            menu.addSeparator()
            menu.addAction("Remover endpoint", lambda: self.on_remove_endpoint(item))
            menu.addSeparator()
            menu.addAction("Exportar Endpoint", lambda: self.on_export_endpoint(item))
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def on_new_project(self):
        name, ok = QInputDialog.getText(self, "Novo Projeto", "Nome do projeto:")
        if ok and name:
            try:
                self.controller.add_project(name, "")
                self.load_projects()
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def on_edit_base_url(self, item):
        project = item.text(0)
        current_url = self.controller.get_projects().get(project, {}).get("base_url", "")
        url, ok = QInputDialog.getText(self, "Editar URL base", "URL base do projeto:", text=current_url)
        if ok:
            self.controller.set_project_base_url(project, url)
            self.load_projects()

            if self.current_project and self.current_controller and self.current_endpoint:
                self.load_tests(
                    self.current_project,
                    self.current_controller,
                    self.current_endpoint
                )

    def on_edit_controller_path(self, item):
        project = item.parent().text(0)
        controller = item.text(0)
        current_path = self.controller.get_projects().get(project, {}).get("controllers", {}).get(controller, {}).get(
            "path", "")
        path, ok = QInputDialog.getText(self, "Editar Path do Controlador", "Path do controlador (ex: /user):",
                                        text=current_path)
        if ok:
            self.controller.set_controller_path(project, controller, path)
            self.load_projects()

            if self.current_project and self.current_controller and self.current_endpoint:
                self.load_tests(
                    self.current_project,
                    self.current_controller,
                    self.current_endpoint
                )

    def on_import_java_project(self):
        projects = list(self.controller.get_projects().keys())
        project, ok = QInputDialog.getItem(
            self,
            "Selecione o Projeto",
            "Projeto:",
            projects,
            0,
            False
        )
        if not ok or not project:
            return

        project_path = QFileDialog.getExistingDirectory(self, "Selecione o diretório raiz do projeto Java (src/)")
        if not project_path:
            return

        self.setEnabled(False)
        self.info_label.setText("Importando projeto Java...")

        self.import_worker = JavaImportWorker(self.controller, project, project_path)
        self.import_worker.finished.connect(self._on_import_finished)
        self.import_worker.error.connect(self._on_import_error)
        self.import_worker.start()

    def _on_import_finished(self, controllers):
        logger.info(f"[IntegrationTestsScreen] Projeto Java importado com {len(controllers)} controladores")
        logger.info(f"[IntegrationTestsScreen] Controladores importados: {', '.join(controllers)}")
        self.setEnabled(True)
        self.load_projects()
        QMessageBox.information(
            self,
            "Importação Concluída",
            f"Controllers importados: {controllers if controllers else 'Nenhum encontrado'}"
        )
        self.info_label.setText("Importação concluída.")

    def _on_import_error(self, error_msg):
        logger.error(f"[IntegrationTestsScreen] Erro ao importar projeto Java: {error_msg}")
        self.setEnabled(True)
        QMessageBox.warning(self, "Erro na Importação", error_msg)
        self.info_label.setText("Falha ao importar projeto Java.")

    def on_new_controller(self, item=None):
        if not item:
            item = self.tree.currentItem()
        if not item or item.data(0, Qt.UserRole) is None or item.data(0, Qt.UserRole)[0] != "project":
            QMessageBox.warning(self, "Aviso", "Selecione um projeto para adicionar controlador.")
            return
        project = item.text(0)
        name, ok = QInputDialog.getText(self, "Novo Controlador", "Nome do controlador:")
        if ok and name:
            try:
                self.controller.add_controller(project, name)
                self.load_projects()
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def on_rename_project(self, item):
        if not item or item.data(0, Qt.UserRole)[0] != "project":
            return
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Renomear Projeto", "Novo nome do projeto:", text=old_name)
        if ok and new_name and new_name != old_name:
            projects = self.controller.get_projects()
            if new_name in projects:
                QMessageBox.warning(self, "Erro", "Já existe um projeto com esse nome.")
                return
            projects[new_name] = projects.pop(old_name)
            self.controller.service.save(projects)
            self.load_projects()

    def on_remove_project(self, item=None):
        if not item:
            item = self.tree.currentItem()
        if not item or item.data(0, Qt.UserRole)[0] != "project":
            QMessageBox.warning(self, "Aviso", "Selecione um projeto para remover.")
            return
        name = item.text(0)
        confirm = QMessageBox.question(self, "Confirmar", f"Remover projeto '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.controller.remove_project(name)
            self.load_projects()

    def on_rename_controller(self, item):
        if not item or item.data(0, Qt.UserRole)[0] != "controller":
            return
        project = item.parent().text(0)
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Renomear Controlador", "Novo nome do controlador:", text=old_name)
        if ok and new_name and new_name != old_name:
            projects = self.controller.get_projects()
            controllers = projects[project]["controllers"]
            if new_name in controllers:
                QMessageBox.warning(self, "Erro", "Já existe um controlador com esse nome.")
                return
            controllers[new_name] = controllers.pop(old_name)
            self.controller.service.save(projects)
            self.load_projects()

    def on_remove_controller(self, item=None):
        if not item:
            item = self.tree.currentItem()
        if not item or item.data(0, Qt.UserRole)[0] != "controller":
            QMessageBox.warning(self, "Aviso", "Selecione um controlador para remover.")
            return
        info = item.data(0, Qt.UserRole)
        project, ctrl = info[1], info[2]
        confirm = QMessageBox.question(self, "Confirmar", f"Remover controlador '{ctrl}' do projeto '{project}'?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.controller.remove_controller(project, ctrl)
            self.load_projects()

    def on_tree_selected(self):
        selected = self.tree.currentItem()
        if not selected:
            self.info_label.setText("Selecione um projeto ou controlador para ver detalhes.")
            return

        data = selected.data(0, Qt.UserRole)
        all_projects = self.controller.get_projects()

        if data:
            kind = data[0]

            if kind == "project":
                project = data[1]
                info = all_projects.get(project, {})
                base_url = info.get("base_url", "")
                path = info.get("project_path", "")
                msg = f"<b>Projeto:</b> {project}"
                if base_url:
                    msg += f"<br><b>URL base:</b> {base_url}"
                if path:
                    msg += f"<br><b>Path local:</b> {path}"
                self.info_label.setText(msg)
                self.current_project = project
                self.current_controller = None
                self.current_endpoint = None
                self.clear_tests()
                self.btn_new.setEnabled(False)

            elif kind == "controller":
                project, ctrl = data[1], data[2]
                proj_info = all_projects.get(project, {})
                base_url = proj_info.get("base_url", "")
                ctrl_info = proj_info.get("controllers", {}).get(ctrl, {})
                ctrl_path = ctrl_info.get("path", "")
                desc = ctrl_info.get("description", "")
                full_url = f"{base_url}{ctrl_path}" if base_url or ctrl_path else ""
                msg = (
                    f"<b>Projeto:</b> {project}"
                    f"<br><b>Controller:</b> {ctrl}"
                )
                if ctrl_path:
                    msg += f"<br><b>Path:</b> {ctrl_path}"
                if full_url:
                    msg += f"<br><b>URL completa:</b> {full_url}"
                if desc:
                    msg += f"<br><b>Descrição:</b> {desc}"
                self.info_label.setText(msg)
                self.current_project = project
                self.current_controller = ctrl
                self.current_endpoint = None
                self.clear_tests()
                self.btn_new.setEnabled(False)

            elif kind == "endpoint":
                project, ctrl, ep = data[1], data[2], data[3]
                endpoints = (
                    all_projects
                    .get(project, {})
                    .get("controllers", {})
                    .get(ctrl, {})
                    .get("endpoints", {})
                )
                if ep not in endpoints:
                    self.clear_tests()
                    self.current_project = None
                    self.current_controller = None
                    self.current_endpoint = None
                    self.btn_new.setEnabled(False)
                    self.info_label.setText(f"Endpoint '{ep}' não encontrado. Selecione outro.")
                    return

                # carrega detalhes do endpoint
                ep_info = endpoints[ep]
                method = ep_info.get("method", "")
                ep_path = ep_info.get("path", "")
                desc = ep_info.get("description", "")
                base_url = all_projects[project].get("base_url", "")
                ctrl_path = all_projects[project]["controllers"][ctrl].get("path", "")
                url = join_url(base_url, ctrl_path, ep_path)

                msg = (
                    f"<b>Projeto:</b> {project}"
                    f"<br><b>Controller:</b> {ctrl}"
                    f"<br><b>Endpoint:</b> {ep}"
                )
                if ep_path:
                    msg += f"<br><b>Path do endpoint:</b> {ep_path}"
                if method:
                    msg += f"<br><b>Método:</b> {method}"
                msg += f"<br><b>URL completa:</b> {url}"
                if desc:
                    msg += f"<br><b>Descrição:</b> {desc}"
                self.info_label.setText(msg)

                self.current_project = project
                self.current_controller = ctrl
                self.current_endpoint = ep
                self.load_tests(project, ctrl, ep)

        else:
            self.info_label.setText("Selecione um projeto ou controlador para ver detalhes.")

    def on_export_pytest(self):
        if not (self.current_project and self.current_controller and self.current_endpoint):
            QMessageBox.warning(self, "Atenção", "Selecione primeiro um endpoint.")
            return
        code = self.controller.export_tests(
            self.current_project,
            self.current_controller,
            self.current_endpoint,
            "python"
        )
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar pytest",
            f"{self.current_endpoint}_test.py",
            "Python Files (*.py)"
        )
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(code)
            QMessageBox.information(self, "Exportação", f"pytest salvo em:\n{fname}")

    def on_export_insomnia(self):
        if not (self.current_project and self.current_controller and self.current_endpoint):
            QMessageBox.warning(self, "Atenção", "Selecione primeiro um endpoint.")
            return
        coll = self.controller.export_postman_collection(
            self.current_project,
            self.current_controller,
            self.current_endpoint
        )
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Insomnia Collection",
            f"{self.current_endpoint}_insomnia.json",
            "JSON Files (*.json)"
        )
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(json.dumps(coll, indent=2))
            QMessageBox.information(self, "Exportação", f"Insomnia Collection salvo em:\n{fname}")

    def on_export_hoppscotch(self):
        if not (self.current_project and self.current_controller and self.current_endpoint):
            QMessageBox.warning(self, "Atenção", "Selecione primeiro um endpoint.")
            return
        coll = self.controller.export_postman_collection(
            self.current_project,
            self.current_controller,
            self.current_endpoint
        )
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Hoppscotch Collection",
            f"{self.current_endpoint}_hoppscotch.json",
            "JSON Files (*.json)"
        )
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(json.dumps(coll, indent=2))
            QMessageBox.information(self, "Exportação", f"Hoppscotch collection salvo em:\n{fname}")


    def clear_tests(self):
        while self.tests_layout.count():
            item = self.tests_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def load_tests(self, project, controller, endpoint):
        self.clear_tests()
        self.logs.clear()
        self.log_view.clear()
        tests = self.controller.get_projects()[project]["controllers"][controller]["endpoints"][endpoint].get("tests",{})
        self.log_filter_combo.clear()
        self.log_filter_combo.addItem("Todos")
        for name in tests.keys():
            self.log_filter_combo.addItem(name)
        self.log_filter_combo.setEnabled(bool(tests))

        proj_info = self.controller.get_projects()[project]
        ctrl_info = proj_info["controllers"][controller]
        ep_info = ctrl_info["endpoints"][endpoint]
        base_url = proj_info.get("base_url", "")
        ctrl_path = ctrl_info.get("path", "")
        ep_path = ep_info.get("path", "")
        full_url = join_url(base_url, ctrl_path, ep_path)
        ep_method = ep_info.get("method", "GET").upper()

        for i in reversed(range(self.tests_layout.count() - 1)):
            w = self.tests_layout.takeAt(i).widget()
            w.deleteLater()
        tests = self.controller.get_projects()[project]["controllers"][controller]["endpoints"].get(endpoint, {}).get(
            "tests", {})
        for test_name, cfg in tests.items():
            def mk_cb(name): return lambda: self.on_rename_test(project, controller, endpoint, name)
            def mk_dup(name): return lambda: self.on_duplicate_test(project, controller, endpoint, name)
            def mk_del(name): return lambda: self.on_remove_test(project, controller, endpoint, name)
            def mk_run(name, widget): return lambda: self.on_run_test(project, controller, endpoint, name, widget)

            w = CollapsibleTestWidget(
                test_name,
                on_rename=mk_cb(test_name),
                on_duplicate=mk_dup(test_name),
                on_delete=mk_del(test_name),
                on_run = mk_run(test_name, None)
            )
            w.method_combo.setCurrentText(ep_method)
            w.url_input.setText(full_url)

            param_defs = {p['name']: p for p in ep_info.get("query_params", [])}
            test_qparams = cfg.get("query_params", {})
            for p in ep_info.get("query_params", []):
                name = p['name']
                is_required = p.get('required', False)
                value = test_qparams.get(name, "")
                w.add_param_row(w.query_table, name, value, is_required)

            header_defs = {p['name']: p for p in ep_info.get("headers", [])}
            test_pvars = cfg.get("headers", {})
            for p in ep_info.get("headers", []):
                name = p['name']
                is_required = p.get('required', False)
                value = test_pvars.get(name, "")
                w.add_param_row(w.headers_table, name, value, is_required)

            w.body_edit.setPlainText(cfg.get("body", ""))
            if ep_info.get("body_required", False):
                w.body_edit.setStyleSheet("border: 2px solid #e57373;")
                w.body_edit.setToolTip("Body obrigatório para este endpoint")
            else:
                w.body_edit.setStyleSheet("")
                w.body_edit.setToolTip("")
            w.expected_status.setCurrentText(str(cfg.get("expected_status", 200)))
            w.expected_body.setPlainText(cfg.get("expected_body", ""))

            w.load_assertions(cfg.get("assertions", []))
            w.load_schema(cfg.get("json_schema", ""))
            w.toggle_btn.toggled.connect(lambda expanded, wi=w, tn=test_name:
                                         self.save_test_config_if_collapsed(expanded, project, controller, endpoint, tn,
                                                                            wi)
                                         )

            w.run_btn.clicked.disconnect()
            w.run_btn.clicked.connect(mk_run(test_name, w))

            w.method_combo.setEnabled(False)
            w.url_input.setEnabled(False)

            self.tests_layout.addWidget(w)
        self.btn_new.clicked.connect(lambda: self.on_new_test(project, controller, endpoint))
        self.btn_new.setEnabled(True)

    def on_run_all_tests(self):
        try:
            if self._running_all:
                return

            if not (self.current_project and self.current_controller and self.current_endpoint):
                QMessageBox.warning(
                    self,
                    "Atenção",
                    "Selecione primeiro um endpoint com testes carregados."
                )
                return

            self._running_all = True
            self._pending_tests = 0
            self.run_all_btn.setEnabled(False)

            tests_to_run = []
            for i in range(self.tests_layout.count()):
                try:
                    widget = self.tests_layout.itemAt(i).widget()
                    if not isinstance(widget, CollapsibleTestWidget):
                        continue
                    test_name = widget.toggle_btn.text()
                    try:
                        self.save_test_config_if_collapsed(
                            expanded=False,
                            project=self.current_project,
                            controller=self.current_controller,
                            endpoint=self.current_endpoint,
                            test_name=test_name,
                            widget=widget
                        )
                    except Exception as e:
                        logger.error(f"Erro ao salvar estado do teste '{test_name}': {e}", exc_info=True)
                        continue
                    tests_to_run.append((test_name, widget))
                except Exception as e:
                    logger.error(f"Erro ao preparar widget na posição {i}: {e}", exc_info=True)

            if not tests_to_run:
                self._running_all = False
                self.run_all_btn.setEnabled(True)
                return

            self._pending_tests = len(tests_to_run)
            for test_name, widget in tests_to_run:
                try:
                    tests = self.controller.list_tests(
                        self.current_project,
                        self.current_controller,
                        self.current_endpoint
                    )
                except Exception as e:
                    logger.error(f"Erro ao listar testes para '{test_name}': {e}", exc_info=True)
                    self._on_single_test_finished()
                    continue

                test_desc = next((t for t in tests if t["name"] == test_name), None)
                if not test_desc:
                    logger.error(f"Descriptor não encontrado para teste '{test_name}'")
                    self._on_single_test_finished()
                    continue

                try:
                    def make_on_success(w):
                        return lambda td, data: self._handle_test_success(td, data, w)

                    def make_on_error():
                        return lambda td, err: self._handle_test_error(td, err)

                    runnable = TestRunnable(
                        self.current_project,
                        self.controller,
                        test_desc,
                        on_success=make_on_success(widget),
                        on_error=make_on_error()
                    )
                except Exception as e:
                    logger.error(f"Erro ao criar TestRunnable para '{test_name}': {e}", exc_info=True)
                    self._on_single_test_finished()
                    continue

                try:
                    runnable.signals.result.connect(self._on_test_result)
                    runnable.signals.error.connect(self._on_test_error)
                    runnable.signals.finished.connect(lambda td, data: self._on_single_test_finished())
                    self.thread_pool.start(runnable)
                    logger.info(f"[IntegrationTestsScreen] Agendado '{test_name}' no pool")
                except Exception as e:
                    logger.error(f"Erro ao agendar TestRunnable para '{test_name}': {e}", exc_info=True)
                    self._on_single_test_finished()

        except Exception as e:
            logger.error(f"Erro inesperado em on_run_all_tests: {e}", exc_info=True)
            self._running_all = False
            self.run_all_btn.setEnabled(True)

    def on_run_test(self, project, controller, endpoint, test_name, widget):
        self.save_test_config_if_collapsed(
            expanded=False,
            project=project,
            controller=controller,
            endpoint=endpoint,
            test_name=test_name,
            widget=widget
        )

        ep_info = (
            self.controller.get_projects()
            [project]["controllers"][controller]["endpoints"][endpoint]
        )

        ok, msg = self.validate_required(widget, ep_info)
        if not ok:
            QMessageBox.warning(self, "Campos obrigatórios", msg)
            return

        try:
            self.append_log(f"▶ Iniciando teste '{test_name}'", test_name)
            self.append_log("*" * self.total_line_breaker, test_name)
            self.controller.run_test(
                project, controller, endpoint, test_name,
                on_success=lambda data, w=widget, n=test_name: self.on_success(data, w, n),
                on_error=lambda data, n=test_name: self.on_error(data, n)
            )
        except Exception as e:
            logging.error(f"[IntegrationTestsScreen] Erro ao executar teste: {e}")
            QMessageBox.critical(self, "Erro ao executar teste", str(e))

    @staticmethod
    def validate_required(widget, ep_info):
        param_defs = {p['name']: p for p in ep_info.get("query_params", [])}
        for r in range(widget.query_table.rowCount()):
            name = widget.query_table.item(r, 1).text().replace(" *", "")
            is_required = param_defs.get(name, {}).get('required', False)
            value = widget.query_table.item(r, 2).text().strip()
            if is_required and not value:
                return False, f"Preencha o parâmetro obrigatório: {name}"

        path_defs = {p['name']: p for p in ep_info.get("path_variables", [])}
        for r in range(widget.headers_table.rowCount()):
            name = widget.headers_table.item(r, 1).text().replace(" *", "")
            is_required = path_defs.get(name, {}).get('required', False)
            value = widget.headers_table.item(r, 2).text().strip()
            if is_required and not value:
                return False, f"Preencha a variável de caminho obrigatória: {name}"

        if ep_info.get('body_required', False) and not widget.body_edit.toPlainText().strip():
            return False, "O body é obrigatório para este endpoint."

        return True, ""

    def _on_single_test_finished(self):
        """
        Chamado sempre que um teste termina (sucesso ou erro),
        para reativar o botão quando tudo acabar.
        """
        self._pending_tests -= 1
        if self._pending_tests <= 0:
            self._running_all = False
            self.run_all_btn.setEnabled(True)

    def _handle_test_success(self, td, data, widget):
        """
        Roteia pra on_success, e depois trata contagem.
        """
        self.on_success(data, widget, td["name"])

    @QtCore.pyqtSlot(object, object)
    def _on_test_result(self, test, response):
        """
        Recebe o resultado de um teste e atualiza a UI (log, status, etc).
        """
        self.append_log(f"✔️ {test['name']}: {response.status_code}", test['name'])
        self._update_test_status(test, success=True, detail=response)

    @QtCore.pyqtSlot(object, str)
    def _on_test_error(self, test, traceback_str):
        """
        Recebe erro e exibe no log/UI.
        """
        self.append_log(f"❌ {test['name']}: erro\n{traceback_str}", test['name'])
        self._update_test_status(test, success=False, detail=traceback_str)

    def _update_test_status(self, test, success: bool, detail):
        """
        Encontra o widget CollapsibleTestWidget pelo nome do teste e
        atualiza seu rótulo de status.
        """
        for i in range(self.tests_layout.count()):
            w = self.tests_layout.itemAt(i).widget()
            if hasattr(w, "toggle_btn") and w.toggle_btn.text() == test["name"]:
                if success:
                    w.status_lbl.setStyleSheet("color: green;")
                    w.status_lbl.setText("✅ Teste passou")
                else:
                    w.status_lbl.setStyleSheet("color: red;")
                    w.status_lbl.setText("❌ Teste falhou")
                break

    def on_success(self, data: dict, widget: CollapsibleTestWidget, test_name):
        logging.info(f"[IntegrationTestsScreen] Teste executado com sucesso: {data}")
        if not widget:
            logging.warning("[IntegrationTestsScreen] Widget não fornecido para exibir o resultado do teste.")
            return

        current_status = data.get("status", 0)
        current_body = data.get("body", "")
        current_headers = data.get("headers", {})

        self.append_log(f"Teste '{test_name}' executado!", test_name)
        self.append_log(f"Status da execução: {current_status}", test_name)
        self.append_log(f"Headers da resposta: {current_headers}", test_name)
        self.append_log(f"Body da resposta:\n{current_body.strip()}", test_name)
        self.append_log("*" * self.total_line_breaker, test_name)

        expected_status = widget.get_expected_status()
        expected_body = widget.get_expected_body().strip()

        status_passed = (current_status == expected_status)

        body_passed = True
        diff_text = ""
        if expected_body:
            try:
                exp_json = json.loads(expected_body)
                curr_json = json.loads(current_body)
                body_passed = (exp_json == curr_json)
                if not body_passed:
                    exp_lines = json.dumps(exp_json, indent=2).splitlines()
                    curr_lines = json.dumps(curr_json, indent=2).splitlines()
                    diff = difflib.unified_diff(exp_lines, curr_lines, lineterm="")
                    diff_text = "\n".join(diff)
            except json.JSONDecodeError:
                body_passed = (expected_body in current_body)
                if not body_passed:
                    exp_lines = expected_body.splitlines()
                    curr_lines = current_body.splitlines()
                    diff = difflib.unified_diff(exp_lines, curr_lines, lineterm="")
                    diff_text = "\n".join(diff)

        assertion_errors = []
        try:
            curr_json = json.loads(current_body)
        except:
            curr_json = None

        for a in widget.get_assertions():
            typ = a["type"]
            target = a["target"]
            exp_val = a["expected"]
            ok = True

            if typ == "HTTP Status Equals":
                ok = (current_status == int(exp_val))

            elif typ == "Body Contains":
                ok = (exp_val in current_body)

            elif typ == "Body Equals":
                ok = (current_body.strip() == exp_val.strip())

            elif typ == "Header Equals":
                ok = (current_headers.get(target, "") == exp_val)

            elif typ == "JSON Path Equals" and curr_json is not None:
                val = curr_json
                for key in target.split("."):
                    val = val.get(key, None) if isinstance(val, dict) else val[int(key)] if isinstance(val, list) and key.isdigit() else None
                ok = (val == exp_val)

            elif typ == "Regex Matches":
                ok = (re.search(exp_val, current_body) is not None)

            if not ok:
                assertion_errors.append(f"{typ}: esperado '{exp_val}' em '{target}'")

        schema_str = widget.get_schema()
        if schema_str:
            try:
                schema = json.loads(schema_str)
                curr_json = json.loads(current_body)
                try:
                    validate(instance=curr_json, schema=schema)
                    self.append_log("✅ JSON Schema validado com sucesso", test_name)
                except ValidationError as ve:
                    assertion_errors.append(f"JSON Schema Falhou: {ve.message}")
                    self.append_log(f"✖ Falha JSON Schema: {ve.message}", test_name)
            except json.JSONDecodeError as je:
                self.append_log(f"✖ JSON Schema inválido: {je}", test_name)

        passed = status_passed and body_passed and not assertion_errors

        if passed:
            self.append_log(f"✔ Teste '{test_name}' passou (status={current_status})", test_name)
            widget.status_lbl.setStyleSheet("color: green;")
            widget.status_lbl.setText("✅ Teste passou")
        else:
            widget.status_lbl.setStyleSheet("color: red;")
            widget.status_lbl.setText("❌ Teste falhou")

            details = []
            if not status_passed:
                details.append(f"Status esperado: {expected_status}, obtido: {current_status}")
            if expected_body and not body_passed:
                details.append("Diferença no body:\n" + (diff_text or "<nenhum diff gerado>"))
            for err in assertion_errors:
                details.append("Verificação: " + err)
            self.append_log(f"✖ Teste '{test_name}' falhou: status esperado {expected_status}, obtido {current_status}", test_name)
            self.append_log("Falha no teste:\n" + "\n\n".join(details), test_name)

        self.append_log("*" * self.total_line_breaker, test_name)

    def on_error(self, response, test_name):
        msg = f"Erro teste '{test_name}': {response}"
        self.append_log(msg, test_name)

    def on_new_test(self, project, controller, endpoint):
        name, ok = QInputDialog.getText(self, "Novo Teste", "Nome do teste:")
        if ok and name:
            try:
                self.controller.add_test(project, controller, endpoint, name)
                self.load_tests(project, controller, endpoint)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def on_rename_test(self, project, controller, endpoint, old_name):
        new_name, ok = QInputDialog.getText(self, "Renomear Teste", "Novo nome:", text=old_name)
        if ok and new_name and new_name != old_name:
            try:
                self.controller.rename_test(project, controller, endpoint, old_name, new_name)
                self.load_tests(project, controller, endpoint)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def on_duplicate_test(self, project, controller, endpoint, test_name):
        try:
            self.controller.duplicate_test(project, controller, endpoint, test_name)
            self.load_tests(project, controller, endpoint)
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))

    def on_remove_test(self, project, controller, endpoint, test_name):
        confirm = QMessageBox.question(self, "Confirmar", f"Remover teste '{test_name}'?",
                                       QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                self.controller.remove_test(project, controller, endpoint, test_name)
                self.load_tests(project, controller, endpoint)
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def on_new_endpoint(self, item):
        project = item.parent().text(0)
        controller = item.text(0)
        name, ok = QInputDialog.getText(self, "Novo Endpoint", "Nome do endpoint (ex: listarUsuarios):")
        if not (ok and name):
            return

        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "CONSUMER"]
        method, ok_method = QInputDialog.getItem(self, "Método do Endpoint", "Selecione o método:", methods, 0, False)
        if not ok_method:
            return

        path, ok_path = QInputDialog.getText(self, "Path do endpoint", "Path do endpoint (ex: /listar):")
        if not ok_path:
            path = ""
        try:
            self.controller.add_endpoint(project, controller, name, path, method)
            self.load_projects()
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))

    def on_edit_endpoint_path(self, item):
        info = item.data(0, Qt.UserRole)
        project, controller, endpoint = info[1], info[2], info[3]
        endpoints = self.controller.get_projects()[project]["controllers"][controller]["endpoints"]
        current_path = endpoints[endpoint].get("path", "")
        path, ok = QInputDialog.getText(self, "Editar Path do Endpoint", "Novo path do endpoint:", text=current_path)
        if ok:
            self.controller.set_endpoint_path(project, controller, endpoint, path)
            self.load_projects()

    def on_remove_endpoint(self, item):
        info = item.data(0, Qt.UserRole)
        project, controller, endpoint = info[1], info[2], info[3]
        confirm = QMessageBox.question(self, "Confirmar", f"Remover endpoint '{endpoint}'?",
                                       QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.controller.remove_endpoint(project, controller, endpoint)
            self.load_projects()

    def on_duplicate_endpoint(self, item):
        info = item.data(0, Qt.UserRole)
        project, controller, endpoint = info[1], info[2], info[3]
        try:
            self.controller.duplicate_endpoint(project, controller, endpoint)
            self.load_projects()
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))

    def on_rename_endpoint(self, item):
        info = item.data(0, Qt.UserRole)
        project, controller, endpoint = info[1], info[2], info[3]
        endpoints = self.controller.get_projects()[project]["controllers"][controller]["endpoints"]
        new_name, ok = QInputDialog.getText(self, "Renomear Endpoint", "Novo nome do endpoint:", text=endpoint)
        if ok and new_name and new_name != endpoint:
            if new_name in endpoints:
                QMessageBox.warning(self, "Erro", "Já existe um endpoint com esse nome.")
                return
            try:
                self.controller.rename_endpoint(project, controller, endpoint, new_name)
                self.load_projects()
            except Exception as e:
                QMessageBox.warning(self, "Erro", str(e))

    def save_test_config_if_collapsed(self, expanded, project, controller, endpoint, test_name, widget):
        if expanded:
            return

        headers = {}
        for r in range(widget.headers_table.rowCount()):
            cb = widget.headers_table.cellWidget(r, 0)
            k = widget.headers_table.item(r, 1)
            v = widget.headers_table.item(r, 2)
            if cb and cb.isChecked() and k and k.text():
                headers[k.text()] = v.text() if v else ""

        query_params = {}
        for r in range(widget.query_table.rowCount()):
            cb = widget.query_table.cellWidget(r, 0)
            k = widget.query_table.item(r, 1)
            v = widget.query_table.item(r, 2)
            if cb and cb.isChecked() and k and k.text():
                query_params[k.text()] = v.text() if v else ""

        body = widget.body_edit.toPlainText()
        expected_status = widget.get_expected_status()
        expected_body = widget.get_expected_body()
        assertions = widget.get_assertions()

        new_cfg = {"description": "", "headers": headers, "query_params": query_params, "body": body,
                   "expected_status": expected_status, "expected_body": expected_body, "assertions": assertions,
                   "json_schema": widget.get_schema()}

        self.controller.update_test(project, controller, endpoint, test_name, new_cfg)

    def on_export_endpoint(self, item):
        project, ctrl, ep = item.data(0, Qt.UserRole)[1:]
        code = self.controller.export_tests(project, ctrl, ep, self._ask_language())
        ext = {"python": ".py", "node": ".js", "java": ".java"}[self._ask_language()]
        fname, _ = QFileDialog.getSaveFileName(
            self, "Salvar Endpoint", f"{ep}{ext}", f"*{ext}"
        )
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(code)
            QMessageBox.information(self, "Exportação", f"Endpoint salvo em {fname}")

    def on_export_controller(self, item):
        project = item.parent().text(0)
        controller = item.text(0)
        lang = self._ask_language()
        code = self.controller.export_controller_tests(project, controller, lang)
        ext = {"python": ".py", "node": ".js", "java": ".java"}[lang]
        fname, _ = QFileDialog.getSaveFileName(
            self, "Salvar Controlador", f"{controller}{ext}", f"*{ext}"
        )
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(code)
            QMessageBox.information(self, "Exportação", f"Controlador salvo em {fname}")

    def on_export_project(self, item):
        project = item.text(0)
        lang = self._ask_language()
        codes = self.controller.export_project_tests(project, lang)
        folder = QFileDialog.getExistingDirectory(self, "Selecione pasta para exportar o projeto")
        if not folder:
            return
        for ctrl, code in codes.items():
            ext = {"python": ".py", "node": ".js", "java": ".java"}[lang]
            path = os.path.join(folder, f"{ctrl}{ext}")
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
        QMessageBox.information(self, "Exportação", f"Projeto '{project}' exportado em {folder}")

    def _ask_language(self):
        langs = ["python", "node", "java"]
        labels = {"python": "Python", "node": "Node.js", "java": "Java"}
        lang, ok = QInputDialog.getItem(
            self, "Escolha a linguagem", "Linguagem:",
            [labels[l] for l in langs], 0, False
        )
        if not ok:
            return None
        # converte rótulo de volta para a chave
        return next(k for k, v in labels.items() if v == lang)

    def on_performance(self):
        if not (self.current_project and self.current_controller and self.current_endpoint):
            QMessageBox.warning(self, "Atenção", "Selecione primeiro um endpoint com testes carregados.")
            return
        self.performance_window = PerformanceWidget(self)
        self.performance_window.show()

    def on_import_java(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione Controller Java",
            "",
            "Java Files (*.java)"
        )
        if not path:
            return

        projects = list(self.controller.get_projects().keys())
        project, ok = QInputDialog.getItem(
            self,
            "Selecione o Projeto",
            "Projeto:",
            projects,
            0,
            False
        )
        if not ok or not project:
            return

        try:
            self.controller.service.import_java_controller(project, path)
        except Exception as e:
            logger.error(f"[IntegrationTestsScreen] Erro ao importar controlador Java: {e}")
            QMessageBox.warning(self, "Erro na Importação", str(e))
            return

        self.load_projects()
        QMessageBox.information(
            self,
            "Importação Concluída",
            "Controller importado e testes de sucesso gerados."
        )

    def on_tree_delete(self):
        """Remove o item selecionado (projeto, controlador ou endpoint) via atalho Delete."""
        item = self.tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        kind = data[0]
        if kind == "endpoint":
            self.on_remove_endpoint(item)
        elif kind == "controller":
            self.on_remove_controller(item)
        elif kind == "project":
            self.on_remove_project(item)

    def on_generate_tests_ai(self):
        if not (self.current_project and self.current_controller and self.current_endpoint):
            QMessageBox.warning(self, "Atenção", "Selecione um endpoint antes de usar IA.")
            return

        prompt = (
            f"Para o endpoint {self.current_method} {self.current_url}, "
            "gere uma lista de 3 casos de teste em JSON com: "
            "nome, query_params, headers, corpo de requisição e status esperado."
        )
        logger.info("[IntegrationTestsScreen] Enviando prompt de geração de testes para o modelo de IA")
        # ai = OpenAIChatBot()
        # ai.ask(prompt,
        #        on_success=self._on_tests_generated,
        #        on_error=lambda err: QMessageBox.critical(self, "Erro IA", str(err))
        #        )

    def _on_tests_generated(self, response_text):
        """
        Espera um JSON como:
        [
          {
            "name": "Listar usuários ativos",
            "query_params": {"active": "true"},
            "headers": {"Authorization": "Bearer <token>"},
            "body": "",
            "expected_status": 200
          },
          ...
        ]
        """
        try:
            tests = json.loads(response_text)
            for t in tests:
                name = t["name"]
                self.controller.add_test(self.current_project, self.current_controller, self.current_endpoint, name)
                self.controller.update_test(
                    self.current_project, self.current_controller, self.current_endpoint, name, t
                )
            self.load_tests(self.current_project, self.current_controller, self.current_endpoint)
            logger.info("[IntegrationTestsScreen] Testes gerados e carregados pela IA")
        except Exception as e:
            logger.error(f"[IntegrationTestsScreen] Falha ao processar testes IA: {e}")
            QMessageBox.critical(self, "Erro ao processar resposta IA", str(e))