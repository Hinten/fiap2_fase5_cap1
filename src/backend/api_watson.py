from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timezone

app = Flask(__name__)

# Conecta ao MongoDB local (porta padrão 27017)
client = MongoClient('mongodb://localhost:27017/')
# Cria/Acessa o banco de dados 'doctor_in' e a coleção (tabela) 'logs_watson'
db = client['doctor_in']
colecao_logs = db['logs_watson']

@app.route('/webhook', methods=['POST'])
def watson_webhook():
    # Recebe o JSON (payload) enviado pelo Watson Assistant
    dados_watson = request.json
    
    # Adiciona um timestamp do servidor local para rastreabilidade
    dados_watson['data_hora_recebimento'] = datetime.now(timezone.utc)
    
    # Grava o documento inteiro no MongoDB de forma direta
    resultado = colecao_logs.insert_one(dados_watson)
    
    print(f"📥 Log registrado com sucesso! ID no NoSQL: {resultado.inserted_id}")
    
    # O Watson exige uma resposta HTTP 200 para saber que deu tudo certo
    return jsonify({"status": "sucesso", "mensagem": "Log gravado no NoSQL"}), 200

if __name__ == '__main__':
    # Roda a API na porta 5000
    app.run(port=5000)