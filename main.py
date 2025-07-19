#!/usr/bin/env python3
import sys
import logging
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
import qtawesome as qta

from presentation.components.integration_screen import IntegrationTestsScreen
from services.notification_manager import NotificationManager
from utils.utilities import get_style_sheet

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("[ApplicationManager]")


class ApplicationManager(QObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setStyleSheet(get_style_sheet())

        self.screen_window = None

        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(qta.icon('fa5s.bell', color='white'))
        self.tray_icon.setToolTip("TestAI - Integração com LocalStack")

        menu = QMenu()
        open_action = QAction("TestAI", self.app)
        open_action.triggered.connect(self.open_screen)
        menu.addAction(open_action)

        exit_action = QAction("Sair", self.app)
        exit_action.triggered.connect(self.app.quit)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

        self.notification_manager = NotificationManager(self.app)

        self.open_screen()
        logger.info("[ApplicationManager] IntegrationTestsScreen iniciado com sucesso!")

    def open_screen(self):
        """
        Exibe a janela quando o usuário escolhe no menu.
        """
        try:
            if self.screen_window and self.screen_window.isVisible():
                logger.info("IntegrationTestsScreen já está visível. Escondendo...")
                self.notification_manager.notify(
                    "TestAI",
                    "TestAI já aberta!",
                    duration=5000
                )
            else:
                if not self.screen_window:
                    logger.info("Criando instância de IntegrationTestsScreen.")
                    self.screen_window = IntegrationTestsScreen()
                logger.info("Exibindo IntegrationTestsScreen.")
                self.screen_window.show()
                self.screen_window.raise_()
                self.screen_window.activateWindow()
        except Exception as e:
            logger.error(f"Erro ao exibir IntegrationTestsScreen: {e}")
            if self.screen_window:
                 self.screen_window.close()
                 self.screen_window = None

    def run(self):
        sys.exit(self.app.exec_())


if __name__ == '__main__':
    manager = ApplicationManager()
    manager.run()
