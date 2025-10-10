# Tutorial: Criando um Middleware de Integração de um Banco de Dados com uma API utilizando Apache Airflow e Docker

## Objetivo

Este tutorial descreve o processo de ponta a ponta para configurar um ambiente Apache Airflow em Docker e criar um DAG (fluxo de trabalho) que atua como um middleware, extraindo dados de um banco de dados PostgreSQL e enviando-os para uma API REST.

## Pré-requisitos

* Docker e Docker Compose instalados.

---

## Passo 1: Configuração do Ambiente do Projeto

Vamos começar criando a estrutura de pastas e todos os arquivos de configuração e código necessários.

### 1.1. Crie a Estrutura de Pastas

Abra seu terminal, navegue até o local onde deseja criar o projeto e execute os seguintes comandos:

```bash
mkdir airflow-middleware-test
cd airflow-middleware-test
mkdir dags logs plugins config
```

### 1.2. Crie o Arquivo de Variáveis de Ambiente

Para evitar problemas de permissão de arquivos entre sua máquina e os contêineres Docker, crie um arquivo `.env` que define o ID do seu usuário.

```bash
# Execute este comando na raiz da pasta 'airflow-middleware-test'
echo -e "AIRFLOW_UID=$(id -u)" > .env
```

### 1.3. Crie o Arquivo `docker-compose.yaml`

Este é o arquivo principal que define todo o ecossistema do Airflow. A configuração abaixo já inclui otimizações de estabilidade (nomes de contêiner e health checks ajustados) e performance (DAGs de exemplo desativadas), e usa os comandos corretos para a versão mais recente do Airflow.

Crie um arquivo chamado `docker-compose.yaml` na raiz do projeto e cole o seguinte conteúdo:

```yaml
x-airflow-common:
  &airflow-common
  image: ${AIRFLOW_IMAGE_NAME:-apache/airflow:3.1.0}
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    AIRFLOW__CORE__AUTH_MANAGER: airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://airflow:airflow@postgres/airflow
    AIRFLOW__CELERY__BROKER_URL: redis://:@redis:6379/0
    AIRFLOW__CORE__FERNET_KEY: ''
    AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION: 'true'
    AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
    AIRFLOW__CORE__EXECUTION_API_SERVER_URL: 'http://airflow-apiserver:8080/execution/'
    AIRFLOW__SCHEDULER__ENABLE_HEALTH_CHECK: 'true'
    _PIP_ADDITIONAL_REQUIREMENTS: ${_PIP_ADDITIONAL_REQUIREMENTS:-}
    AIRFLOW_CONFIG: '/opt/airflow/config/airflow.cfg'
  volumes:
    - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
    - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
    - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
    - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
  user: "${AIRFLOW_UID:-50000}:0"
  depends_on:
    &airflow-common-depends-on
    redis:
      condition: service_healthy
    postgres:
      condition: service_healthy

services:
  postgres:
    image: postgres:16
    container_name: airflow-middleware-postgres-internal
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - postgres-db-volume:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 10s
      retries: 5
      start_period: 5s
    restart: always

  redis:
    image: redis:7.2-bookworm
    container_name: airflow-middleware-redis
    expose:
      - 6379
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 30s
      retries: 50
      start_period: 30s
    restart: always

  airflow-apiserver:
    <<: *airflow-common
    container_name: airflow-middleware-apiserver
    command: api-server
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8080/api/v2/version"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    restart: always
    depends_on:
      <<: *airflow-common-depends-on
      airflow-init:
        condition: service_completed_successfully
    networks:
      - default
      - middleware-net

  airflow-scheduler:
    <<: *airflow-common
    container_name: airflow-middleware-scheduler
    command: scheduler
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8974/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    restart: always
    depends_on:
      <<: *airflow-common-depends-on
      airflow-init:
        condition: service_completed_successfully
    networks:
      - default
      - middleware-net

  airflow-dag-processor:
    <<: *airflow-common
    container_name: airflow-middleware-dag-processor
    command: dag-processor
    healthcheck:
      # Tempos maiores para evitar falhas em máquinas com menos recursos
      test: ["CMD-SHELL", 'airflow jobs check --job-type DagProcessorJob --hostname "$${HOSTNAME}"']
      interval: 60s
      timeout: 30s
      retries: 5
      start_period: 30s
    restart: always
    depends_on:
      <<: *airflow-common-depends-on
      airflow-init:
        condition: service_completed_successfully
    networks:
      - default
      - middleware-net

  airflow-worker:
    <<: *airflow-common
    container_name: airflow-middleware-worker
    command: celery worker
    healthcheck:
      # Tempos maiores para evitar falhas em máquinas com menos recursos
      test:
        - "CMD-SHELL"
        - 'celery --app airflow.providers.celery.executors.celery_executor.app inspect ping -d "celery@$${HOSTNAME}" || celery --app airflow.executors.celery_executor.app inspect ping -d "celery@$${HOSTNAME}"'
      interval: 60s
      timeout: 30s
      retries: 5
      start_period: 30s
    environment:
      <<: *airflow-common-env
      DUMB_INIT_SETSID: "0"
      AIRFLOW__CELERY__WORKER_HOSTNAME: "airflow-worker@%h"
    restart: always
    depends_on:
      <<: *airflow-common-depends-on
      airflow-apiserver:
        condition: service_healthy
      airflow-init:
        condition: service_completed_successfully
    networks:
      - default
      - middleware-net

  airflow-triggerer:
    <<: *airflow-common
    container_name: airflow-middleware-triggerer
    command: triggerer
    healthcheck:
      # Tempos maiores para evitar falhas em máquinas com menos recursos
      test: ["CMD-SHELL", 'airflow jobs check --job-type TriggererJob --hostname "$${HOSTNAME}"']
      interval: 60s
      timeout: 30s
      retries: 5
      start_period: 30s
    restart: always
    depends_on:
      <<: *airflow-common-depends-on
      airflow-init:
        condition: service_completed_successfully
    networks:
      - default
      - middleware-net

  airflow-init:
    <<: *airflow-common
    container_name: airflow-middleware-init
    entrypoint: /bin/bash
    command:
      - -c
      - |
        mkdir -p /opt/airflow/{logs,dags,plugins,config}
        chown -R "${AIRFLOW_UID}:0" /opt/airflow/{logs,dags,plugins,config}
        exec /entrypoint airflow db migrate
    environment:
      <<: *airflow-common-env
      _AIRFLOW_DB_UPGRADE: 'true'
      _AIRFLOW_WWW_USER_CREATE: 'true'
      _AIRFLOW_WWW_USER_USERNAME: ${_AIRFLOW_WWW_USER_USERNAME:-airflow}
      _AIRFLOW_WWW_USER_PASSWORD: ${_AIRFLOW_WWW_USER_PASSWORD:-airflow}
    user: "0:0"

volumes:
  postgres-db-volume:

networks:
  middleware-net:
    external: true
```

### 1.4. Crie os Arquivos da API Simulada

Na raiz do projeto, crie o arquivo `api_simulada.py`:
```python
# api_simulada.py
from flask import Flask, request, jsonify
import logging

# Configuração de logging para garantir a visibilidade da saída no Docker
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

@app.route('/receive_data', methods=['POST'])
def receive_data():
    data = request.json
    logging.info(f"Dados recebidos: {data}")
    return jsonify({"status": "success", "received_data": data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```
Agora, crie o `Dockerfile` para a API:
```dockerfile
# Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY api_simulada.py .
RUN pip install Flask
CMD ["python", "api_simulada.py"]
```

### 1.5. Crie o Arquivo do DAG

Finalmente, crie o arquivo `db_para_api_dag.py` **dentro da pasta `dags`**:
```python
# dags/db_para_api_dag.py
import pendulum
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.operators.http import HttpOperator

@dag(
    dag_id="middleware_db_para_api",
    start_date=pendulum.datetime(2025, 10, 9, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["middleware", "producao"],
)
def database_to_api_dag():
    """
    DAG que extrai dados de produtos de um banco PostgreSQL
    e os envia para uma API de destino.
    """
    @task
    def extrair_dados_do_banco():
        """Busca dados da tabela de produtos e os formata."""
        hook = PostgresHook(postgres_conn_id="postgres_db_simulado")
        registros = hook.get_records("SELECT name, quantity FROM products")
        dados_formatados = [{"nome_produto": nome, "estoque": quantidade} for nome, quantidade in registros]
        return dados_formatados

    enviar_dados_para_api = HttpOperator(
        task_id="enviar_dados_para_api",
        http_conn_id="http_api_simulada",
        endpoint="/receive_data",
        method="POST",
        data="{{ task_instance.xcom_pull(task_ids='extrair_dados_do_banco') | tojson }}",
        headers={"Content-Type": "application/json"},
        log_response=True,
    )

    # Define a ordem de execução
    extrair_dados_do_banco() >> enviar_dados_para_api

database_to_api_dag()
```

---
## Passo 2: Inicialização dos Serviços

Com todos os arquivos criados, vamos iniciar os contêineres.

1.  **Crie a Rede Docker:**
    ```bash
    # Se a rede já existir, um erro aparecerá e poderá ser ignorado.
    docker network create middleware-net
    ```

2.  **Construa e Inicie a API Simulada:**
    ```bash
    docker build -t simulated-api .
    docker run --name simulated-api -p 5001:5000 --network middleware-net -d simulated-api
    ```

3.  **Inicie o Banco de Dados Simulado:**
    ```bash
    docker run --name simulated-postgres -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=mydatabase -p 5432:5432 --network middleware-net -d postgres:16
    ```

4.  **Inicie o Airflow:**
    ```bash
    docker-compose up -d
    ```
    **Importante:** Aguarde de 2 a 3 minutos para que todos os serviços do Airflow iniciem e o status no `docker ps` fique `(healthy)`.

---
## Passo 3: Configuração das Conexões no Airflow

1.  Acesse a interface do Airflow: `http://localhost:8080` (login `airflow`, senha `airflow`).
2.  Vá em **Admin -> Connections**.
3.  **Crie a Conexão do Banco de Dados:**
    * **Connection Id:** `postgres_db_simulado`
    * **Connection Type:** `Postgres`
    * **Host:** `simulated-postgres`
    * **Schema:** `mydatabase`
    * **Login / Password:** `user` / `password`
    * **Port:** `5432`
    * Salve a conexão.

4.  **Crie a Conexão da API:**
    * **Connection Id:** `http_api_simulada`
    * **Connection Type:** `HTTP`
    * **Host:** `http://simulated-api`
    * **Port:** `5000`
    * Salve a conexão.

---
## Passo 4: Execução e Verificação

1.  **Popule o Banco de Dados de Origem:**
    ```bash
    docker exec -it simulated-postgres psql -U user -d mydatabase
    ```
    Dentro do psql, cole o seguinte SQL e pressione Enter:
    ```sql
    CREATE TABLE products (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        quantity INT
    );
    INSERT INTO products (name, quantity) VALUES
    ('Produto A', 10), ('Produto B', 25), ('Produto C', 7);
    \q
    ```

2.  **Execute a DAG:**
    * Na interface do Airflow, encontre a DAG `middleware_db_para_api`.
    * Ative-a no botão de toggle à esquerda.
    * Clique no botão "Play" (▶️) à direita para dispará-la.

3.  **Verifique o Sucesso:**
    * Na aba "Grid", as tarefas da execução devem ficar verdes.
    * Verifique o log da API para a confirmação final:
        ```bash
        docker logs simulated-api
        ```
        A saída deve conter a linha: `INFO:root:Dados recebidos: [...]`.

## Gerenciamento do Ambiente

* **Para parar tudo:**
    ```bash
    docker-compose down
    docker stop simulated-api simulated-postgres
    ```
* **Para iniciar tudo novamente:**
    ```bash
    docker start simulated-api simulated-postgres
    docker-compose up -d
    ```