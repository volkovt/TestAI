import statistics
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QSpinBox, QPushButton, QProgressBar, QMainWindow, QToolButton, QStyle, QMessageBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from utils.requests import join_url


class PerformanceWidget(QMainWindow):
    """
    Janela para configurar e executar teste de carga/performance,
    exibindo histograma e métricas de latência.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Teste de Performance")
        self.setMinimumSize(650, 600)

        # Central widget + layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Formulário de configuração
        form = QFormLayout()
        self.threads_spin = QSpinBox();   self.threads_spin.setRange(1, 500);   self.threads_spin.setValue(10)
        self.ramp_spin    = QSpinBox();   self.ramp_spin.setRange(0, 3600);     self.ramp_spin.setValue(10)
        self.duration_spin= QSpinBox();   self.duration_spin.setRange(1, 86400);self.duration_spin.setValue(60)

        self.threads_spin.setToolTip(
            "Número de threads paralelas que executarão requisições simultâneas."
        )
        self.ramp_spin.setToolTip(
            "Tempo (em segundos) para atingir gradualmente o total de threads configurado."
        )
        self.duration_spin.setToolTip(
            "Duração total (em segundos) do teste de carga."
        )

        form.addRow("Número de threads:", self.threads_spin)
        form.addRow("Ramp-up (s):",       self.ramp_spin)
        form.addRow("Duração (s):",       self.duration_spin)
        main_layout.addLayout(form)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.start_btn = QPushButton("▶ Iniciar"); self.start_btn.clicked.connect(self.start_test)
        self.close_btn = QPushButton("✖ Fechar");  self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)

        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminada enquanto roda
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        # Canvas do histograma
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ax = self.canvas.figure.subplots()
        main_layout.addWidget(self.canvas)

        metrics_layout = QHBoxLayout()

        # Label de métricas
        self.metrics_label = QLabel()
        self.metrics_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.metrics_label.setWordWrap(True)
        self.metrics_label.setToolTip(
            "<b>Total de requisições</b>: quantas chamadas foram concluídas.<br>"
            "<b>Média de latência</b>: tempo médio de resposta (segundos).<br>"
            "<b>Latência mínima</b>: menor tempo de resposta.<br>"
            "<b>Latência máxima</b>: maior tempo de resposta.<br>"
            "<b>Mediana (p50)</b>: 50% das requisições estão abaixo desse valor.<br>"
            "<b>Percentil 90 (p90)</b>: 90% das requisições estão abaixo desse valor.<br>"
            "<b>Throughput</b>: média de requisições por segundo."
        )
        metrics_layout.addWidget(self.metrics_label)

        info_btn = QToolButton()
        info_btn.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        info_btn.setIconSize(QSize(16, 16))

        info_text = (
            "<b>Total de requisições</b>: quantas chamadas foram concluídas.<br>"
            "<b>Média de latência</b>: tempo médio de resposta (segundos).<br>"
            "<b>Latência mínima</b>: menor tempo de resposta.<br>"
            "<b>Latência máxima</b>: maior tempo de resposta.<br>"
            "<b>Mediana (p50)</b>: 50% das requisições ficam abaixo desse valor.<br>"
            "<b>Percentil 90 (p90)</b>: 90% das requisições ficam abaixo desse valor.<br>"
            "<b>Throughput</b>: média de requisições por segundo."
        )
        info_btn.setToolTip(info_text)
        info_btn.clicked.connect(lambda: QMessageBox.information(self, "Ajuda: Métricas de Performance", info_text))
        metrics_layout.addWidget(info_btn, alignment=Qt.AlignTop)
        main_layout.addLayout(metrics_layout)

        self.worker = None

    def start_test(self):
        parent = self.parent()
        if not (parent.current_project and parent.current_controller and parent.current_endpoint):
            return

        self.start_btn.setEnabled(False)
        self.progress.setVisible(True)

        # Monta URL e método
        data = parent.controller.service.load()
        proj = data[parent.current_project]
        ctrl = proj["controllers"][parent.current_controller]
        ep   = ctrl["endpoints"][parent.current_endpoint]
        base, ctrl_path, ep_path = proj.get("base_url",""), ctrl.get("path",""), ep.get("path","")
        url = join_url(base, ctrl_path, ep_path)
        method = ep.get("method","GET").upper()
        headers, params, body = {}, {}, ""

        threads  = self.threads_spin.value()
        ramp_up  = self.ramp_spin.value()
        duration = self.duration_spin.value()

        self.worker = PerformanceWorker(
            method, url, headers, params, body,
            threads, ramp_up, duration
        )
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, latencies: list[float]):
        # Reabilita controles
        self.progress.setVisible(False)
        self.start_btn.setEnabled(True)

        # Histograma
        self.ax.clear()
        self.ax.hist(latencies, bins=20)
        self.ax.set_title("Distribuição de Latências")
        self.ax.set_xlabel("Latência (s)")
        self.ax.set_ylabel("Número de requisições")
        self.canvas.draw()

        # Cálculo de métricas
        count = len(latencies)
        duration = self.duration_spin.value()
        avg = sum(latencies) / count if count else 0
        min_lat = min(latencies) if count else 0
        max_lat = max(latencies) if count else 0
        sorted_lat = sorted(latencies)
        median = sorted_lat[count // 2] if count else 0
        p90 = sorted_lat[int(count * 0.90)] if count else 0
        p95 = sorted_lat[int(count * 0.95)] if count else 0
        stddev = statistics.pstdev(latencies) if count > 1 else 0
        throughput = count / duration if duration else 0

        metrics = (
            f"<b>Total de requisições:</b> {count}<br>"
            f"<b>Média de latência:</b> {avg:.3f}s<br>"
            f"<b>Latência mínima:</b> {min_lat:.3f}s<br>"
            f"<b>Latência máxima:</b> {max_lat:.3f}s<br>"
            f"<b>Mediana (p50):</b> {median:.3f}s<br>"
            f"<b>Percentil 90 (p90):</b> {p90:.3f}s<br>"
            f"<b>Percentil 95 (p95):</b> {p95:.3f}s<br>"
            f"<b>Desvio-padrão:</b> {stddev:.3f}s<br>"
            f"<b>Throughput:</b> {throughput:.1f} req/s"
        )
        self.metrics_label.setText(metrics)


class PerformanceWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, method, url, headers, params, data, threads, ramp_up, duration):
        super().__init__()
        self.method, self.url, self.headers, self.params, self.data = method, url, headers, params, data
        self.threads, self.ramp_up, self.duration = threads, ramp_up, duration

    def run(self):
        session = requests.Session()
        latencies: list[float] = []
        end_time = time.time() + self.duration

        def worker_loop():
            if self.ramp_up and self.threads:
                time.sleep(self.ramp_up / self.threads)
            while time.time() < end_time:
                start = time.time()
                try:
                    session.request(
                        self.method, self.url,
                        headers=self.headers,
                        params=self.params,
                        data=self.data,
                        timeout=10
                    )
                    latencies.append(time.time() - start)
                except:
                    pass

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(worker_loop) for _ in range(self.threads)]
            for f in futures:
                try:
                    f.result()
                except:
                    pass
        self.finished.emit(latencies)

    def _do_request(self, session):
        start = time.time()
        session.request(self.method, self.url,
                        headers=self.headers,
                        params=self.params,
                        data=self.data)
        return time.time() - start
