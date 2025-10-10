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