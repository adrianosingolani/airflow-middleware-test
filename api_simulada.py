from flask import Flask, request, jsonify
import logging
import uuid # Para gerar IDs únicos para nossos jobs
import json

# --- Configuração Inicial ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# --- Banco de Dados em Memória ---
# Este dicionário irá armazenar o estado dos jobs que criarmos.
# A chave será o jobId e o valor será um dicionário com os detalhes do job.
JOBS_DB = {}

# --- Endpoints da API Salesforce Bulk 2.0 (Simulados) ---

# Endpoint 1: Criar um Job
@app.route('/services/data/v1/jobs/ingest', methods=['POST'])
def create_ingest_job():
    """
    Simula a criação de um job. Recebe a definição do job,
    gera um ID único e o armazena em nossa "base de dados".
    """
    job_info = request.json
    job_id = str(uuid.uuid4()) # Gera um ID único
    
    # Monta a resposta simulada, imitando a API real
    response_data = {
        "id": job_id,
        "operation": job_info.get("operation"),
        "object": job_info.get("object"),
        "createdById": "USER-SIMULADO-001",
        "state": "Open", # O job começa aberto, aguardando o upload
        "concurrencyMode": "Parallel"
    }
    
    JOBS_DB[job_id] = response_data
    
    logging.info(f"Job criado com sucesso. ID: {job_id}, Definição: {job_info}")
    return jsonify(response_data), 201 # 201 Created

# Endpoint 2: Fazer Upload do CSV para o Job
@app.route('/services/data/v1/jobs/ingest/<jobId>/batches', methods=['PUT'])
def upload_job_data(jobId):
    """
    Simula o upload de um arquivo CSV para um job existente.
    """
    if jobId not in JOBS_DB:
        return jsonify({"error": "Job não encontrado"}), 404

    # Em uma simulação, não é preciso salvar o CSV, apenas confirmar o recebimento.
    csv_content = request.data.decode('utf-8')
    logging.info(f"Recebido upload de CSV para o Job ID: {jobId}. Tamanho: {len(csv_content)} bytes.")
    
    # Exibe o conteúdo do CSV no log.
    logging.info(f"Conteúdo do CSV recebido:\n{csv_content}")

    # A API real retorna 201 Created sem corpo na resposta.
    return "", 201

# Endpoint 3: Fechar o Job
@app.route('/services/data/v1/jobs/ingest/<jobId>', methods=['PATCH'])
def close_job(jobId):
    """
    Simula o fechamento do job, mudando seu estado para "UploadComplete".
    """
    if jobId not in JOBS_DB:
        return jsonify({"error": "Job não encontrado"}), 404
        
    update_info = request.json
    if update_info.get("state") == "UploadComplete":
        JOBS_DB[jobId]["state"] = "UploadComplete"
        logging.info(f"Job ID: {jobId} foi fechado. Estado atual: UploadComplete.")
        return jsonify(JOBS_DB[jobId]), 200
    else:
        return jsonify({"error": "Ação inválida"}), 400

# Endpoint de verificação (útil para depuração)
@app.route('/jobs', methods=['GET'])
def get_all_jobs():
    return jsonify(JOBS_DB)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)