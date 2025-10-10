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