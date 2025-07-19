# TestAI - Automação de Testes Integrados em APIs REST

Aplicação desktop em PyQt5 para automação de testes integrados em APIs REST, com recursos de IA para sugestão de parâmetros e 
geração de casos de teste, importação automática de controllers Java, execução de testes paralelos, exportação para diversos formatos e 
análise de performance.

---

## Funcionalidades

- Interface gráfica avançada com PyQt5, incluindo árvore de projetos, endpoints, controladores e testes
- Importação automática de controllers Java: gera endpoints e exemplos de testes a partir do código-fonte
-Criação e edição visual de endpoints, parâmetros, headers, bodies e testes HTTP
- Execução de testes paralela com logs detalhados, status individual, e histórico de execuções
- Validação de respostas por status, corpo, headers, JSON Schema e expressões regulares
- Exportação de testes para Python (requests/pytest), Node.js (axios), Java (RestAssured) e Postman/Hoppscotch/Insomnia
- Teste de performance integrado: carga, latência, throughput, histograma e métricas automáticas via matplotlib
- Sugestões inteligentes de parâmetros via aprendizado local dos padrões de requisições (IA embutida, sem cloud)
- Notificações nativas (tray + toast) para alertas e status do sistema
- Geração de JSON Schema automática a partir de exemplos
- Logs e tratamento de erros com logging estruturado

---

## Pré-requisitos

- Python 3.8 ou superior  
- pip  
- pyinstaller (para gerar executáveis)

---

## Instalação em modo desenvolvimento

1. Clone o repositório:  
   ```bash
   git clone https://seu-repo.git
   cd TestAI

2. Crie um ambiente virtual (opcional, mas recomendado):  
   ```bash
   python -m venv .venv
   source .venv/bin/activate     # Linux/macOS
   .venv\Scripts\activate        # Windows (PowerShell)
   
3. Instale as dependências:  
   ```bash
   pip install -r requirements.txt
   
4. Execute a aplicação:  
   ```bash
   python main.py

## Gerando o executável:

1 - Já incluímos dois scripts para simplificar o build com PyInstaller:
- `build.sh`: Script para Linux/macOS que executa o PyInstaller com as opções necessárias.
- `build.bat`: Script para Windows que executa o PyInstaller com as opções necessárias.
- `TestAI.spec`: Arquivo de especificação do PyInstaller para gerar um executável em um único arquivo.
- `TestAI_onedir.spec`: Arquivo de especificação do PyInstaller para gerar um executável em uma única pasta.

## Estrutura de pastas:
```
    ./
   ├── main.py
   ├── requirements.txt
   ├── build.sh
   ├── build.bat
   ├── TestAI.spec
   ├── TestAI_onedir.spec
   ├── presentation/
   │   └── components/
   │       ├── integration_screen.py
   │       ├── performance_component.py
   │       ├── test_widget.py
   │       ├── json_text_edit.py
   │       └── parameter_table.py
   ├── services/
   │   ├── integration_tests_service.py
   │   ├── notification_manager.py
   │   ├── local_session_service.py
   │   ├── pattern_learner.py
   │   └── test_worker.py
   ├── controller/
   │   ├── integration_tests_controller.py
   │   ├── java_controller_parser.py
   │   └── request_assistant_controller.py
   ├── utils/
   │   ├── exporters.py
   │   └── requests.py
   └── styles/
       └── app_styles.qss
```

## Logs e tratamento de erros:

```python
import logging
logger = logging.getLogger("[NotificationManager]")

try:
    # lógica de notificação
    self.notification_manager.show_toast(...)
    logger.info("[NotificationManager] Notificação enviada com sucesso")
except Exception as e:
    logger.error(f"[NotificationManager] Falha ao enviar notificação: {e}")
```

## Contato
Para dúvidas ou contribuições, chame no Teams/Email: Diego Oliveira Melo (diego.oliveira-melo@itau-unibanco.com.br)