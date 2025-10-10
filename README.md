# Middleware de Integração com Apache Airflow

Este projeto demonstra a criação de um pipeline ETL utilizando Apache Airflow para atuar como um middleware, extraindo dados de um banco de dados PostgreSQL e enviando-os para uma API RESTful. Todo o ambiente é orquestrado com Docker e Docker Compose.

## Arquitetura

O ambiente consiste nos seguintes serviços, todos rodando como contêineres Docker:
* **Apache Airflow:** O orquestrador do nosso pipeline. Inclui os serviços de Webserver, Scheduler, Worker, entre outros.
* **Banco de Dados de Origem (`simulated-postgres`):** Um contêiner PostgreSQL que simula a fonte dos dados.
* **API de Destino (`simulated-api`):** Uma API Flask simples que recebe os dados enviados pelo Airflow.

## Pré-requisitos

* Docker
* Docker Compose

## Tutorial
O arquivo [TUTORIAL.md](./TUTORIAL.md) tem um passo a passo mais detalhado de como foi criado o projeto.

## Como Executar o Projeto

1.  **Clone o Repositório:**
    ```bash
    git clone git@github.com:adrianosingolani/airflow-middleware-test.git
    cd airflow-middleware-test
    ```

2.  **Configure o Ambiente:**
    Copie o arquivo de exemplo `.env.example` para `.env`.
    Contém o UID do usuário no Linux/macOS para evitar problemas de permissão.
    Rode `id -u` no terminal para obter o seu e atualize o `.env`.
    ```bash
    cp .env.example .env
    ```

3.  **Inicie os Serviços:**
    O comando a seguir irá criar a rede, construir as imagens e iniciar todos os contêineres.
    ```bash
    # Cria a rede compartilhada
    docker network create middleware-net

    # Sobe os serviços de simulação (API e DB)
    docker build -t simulated-api .
    docker run --name simulated-api -p 5001:5000 --network middleware-net -d simulated-api
    docker run --name simulated-postgres -p 5432:5432 --network middleware-net -d postgres:16 \
      -e POSTGRES_USER=user \
      -e POSTGRES_PASSWORD=password \
      -e POSTGRES_DB=mydatabase

    # Sobe o ambiente Airflow
    docker-compose up -d

    # Verifica se todos os containers estão prontos (status: healthy)
    docker ps
    ```

## Como Usar

1.  **Acesse a Interface do Airflow:**
    Abra `http://localhost:8080` em seu navegador. Use o login `airflow` e a senha `airflow`.

2.  **Configure as Conexões:**
    Vá em **Admin -> Connections** e crie as conexões com a API e o Banco de dados de origem:

    ### Crie a Conexão do Banco de Dados:
    * **Connection Id:** `postgres_db_simulado`
    * **Connection Type:** `Postgres`
    * **Host:** `simulated-postgres`
    * **Schema:** `mydatabase`
    * **Login / Password:** `user` / `password`
    * **Port:** `5432`
    * Salve a conexão.

    ### Crie a Conexão da API:
    * **Connection Id:** `http_api_simulada`
    * **Connection Type:** `HTTP`
    * **Host:** `http://simulated-api`
    * **Port:** `5000`
    * Salve a conexão.

3.  **Popule o Banco de Dados de Origem:**
    Execute o script SQL para criar a tabela `products` e inserir os dados de teste.
    ```bash
    docker exec -it simulated-postgres psql -U user -d mydatabase
    ```
    Dentro do `psql`, cole o conteúdo de [seed.sql](./seed.sql). Digite `\q` para sair.

4.  **Execute a DAG:**
    Na interface, ative o toggle da DAG `middleware_db_para_api` e clique no botão "Trigger" (▶️) para dispará-la.

5.  **Verifique o Resultado:**
    Acompanhe a execução na aba "Grid". Após o sucesso, verifique os logs da API para confirmar o recebimento dos dados:
    ```bash
    docker logs simulated-api
    ```

## Gerenciamento do Ambiente

* **Para parar tudo:**
    ```bash
    docker-compose down
    docker stop simulated-api simulated-postgres
    ```