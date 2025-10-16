import pendulum
import json
import requests
from airflow.sdk import dag, task
from salesforce_auth_hook import SalesforceAuthHook
from airflow.models.connection import Connection

@dag(
    dag_id="salesforce_bulk_upload",
    start_date=pendulum.datetime(2025, 10, 13, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["salesforce", "producao"],
)
def salesforce_bulk_upload_dag():
    """
    DAG que orquestra o fluxo completo da Salesforce Bulk API v2:
    1. Obtém o token de acesso.
    2. Extrai dados do banco.
    3. Transforma em CSV.
    4. Cria um job de ingestão na API.
    5. Faz o upload do CSV para o job.
    6. Fecha o job para iniciar o processamento.
    """

    @task
    def obter_token():
        """Tarefa 1: Obtém o token de acesso usando o Hook personalizado SalesforceAuthHook."""
        return SalesforceAuthHook().get_token()

    @task
    def extrair_dados_do_banco():
        """Tarefa 2: Extrai dados do banco de dados de origem."""
        from airflow.providers.postgres.hooks.postgres import PostgresHook
        hook = PostgresHook(postgres_conn_id="postgres_db_simulado")
        registros = hook.get_records("SELECT name, quantity FROM products")
        return registros

    @task
    def transformar_em_csv(registros_do_banco: list):
        """Tarefa 3: Converte os registros em uma string CSV."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Current_Stock__c'])
        writer.writerows(registros_do_banco)
        csv_string = output.getvalue()
        return csv_string

    @task
    def criar_job_na_api(access_token: str):
        """Tarefa 4: Cria o job na API usando a biblioteca requests."""
        conn = Connection.get_connection_from_secrets('salesforce_api_oauth')
        api_version = conn.extra_dejson.get("api_version", "62.0")

        url = f"{conn.schema}://{conn.host}/services/data/v{api_version}/jobs/ingest"
        payload = {"object": "Asset", "operation": "update"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Lança um erro para status 4xx ou 5xx

        job_id = response.json().get("id")

        print(f"Job criado com sucesso! ID: {job_id}")
        return job_id

    @task
    def fazer_upload_do_csv(csv_data: str, job_id: str, access_token: str):
        """Tarefa 5: Faz o upload do CSV."""
        conn = Connection.get_connection_from_secrets('salesforce_api_oauth')
        api_version = conn.extra_dejson.get("api_version", "62.0")

        url = f"{conn.schema}://{conn.host}/services/data/v{api_version}/jobs/ingest/{job_id}/batches"
        headers = {
            "Content-Type": "text/csv",
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.put(url, headers=headers, data=csv_data.encode('utf-8'))
        response.raise_for_status()

        print(f"CSV enviado com sucesso para o Job ID: {job_id}")
        print(f"Resposta: {response}")
        return job_id

    @task
    def fechar_job_na_api(job_id: str, access_token: str):
        """Tarefa 6: Fecha o job."""
        conn = Connection.get_connection_from_secrets('salesforce_api_oauth')
        api_version = conn.extra_dejson.get("api_version", "62.0")

        url = f"{conn.schema}://{conn.host}/services/data/v{api_version}/jobs/ingest/{job_id}"
        payload = {"state": "UploadComplete"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.patch(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        print(f"Job ID: {job_id} fechado com sucesso. Resposta da API: {response.text}")

    token = obter_token()
    dados_db = extrair_dados_do_banco()
    dados_csv = transformar_em_csv(dados_db)

    id_do_job = criar_job_na_api(access_token=token)

    # Passando todos os dados necessários para a próxima tarefa
    id_do_job_apos_upload = fazer_upload_do_csv(
        csv_data=dados_csv,
        job_id=id_do_job,
        access_token=token
    )

    fechar_job_na_api(
        job_id=id_do_job_apos_upload,
        access_token=token
    )

salesforce_bulk_upload_dag()