import pandas as pd, time, schedule
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest

engine = create_engine('postgresql://postgres:123@localhost/banco_clinico')

def registrar_log(nivel, evento, detalhes):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO logs_auditoria (nivel_log, evento, detalhes) VALUES (:n, :e, :d)"), 
                     {"n": nivel, "e": evento, "d": detalhes})
        conn.commit()

def analisar_dados():
    # Busca apenas medições pendentes de avaliação da IA
    query = "SELECT m.id as med_id, m.paciente_id, m.pressao_sistolica, m.pressao_diastolica, m.frequencia_cardiaca, m.adesao_tratamento, p.status FROM medicoes m JOIN pacientes p ON m.paciente_id = p.id WHERE m.anomalia_detectada IS NULL"
    df_novos = pd.read_sql(query, engine)
    
    if df_novos.empty: return
    
    # Busca histórico estabilizado para a IA entender o que é "normal"
    df_hist = pd.read_sql("SELECT pressao_sistolica, pressao_diastolica, frequencia_cardiaca, adesao_tratamento FROM medicoes WHERE anomalia_detectada = FALSE LIMIT 50", engine)
    
    # Combina contexto histórico com dados novos para rodar a detecção
    df_fit = pd.concat([df_hist, df_novos[['pressao_sistolica', 'pressao_diastolica', 'frequencia_cardiaca', 'adesao_tratamento']]])
    
    modelo = IsolationForest(contamination=0.15, random_state=42)
    modelo.fit(df_fit[['pressao_sistolica', 'pressao_diastolica', 'frequencia_cardiaca', 'adesao_tratamento']])
    preds = modelo.predict(df_novos[['pressao_sistolica', 'pressao_diastolica', 'frequencia_cardiaca', 'adesao_tratamento']])
    
    with engine.connect() as conn:
        for idx, row in df_novos.iterrows():
            is_anomalia = bool(preds[idx] == -1)
            
            # Marca a leitura atual
            conn.execute(text("UPDATE medicoes SET anomalia_detectada = :b WHERE id = :m"), {"b": is_anomalia, "m": row['med_id']})
            
            # Se for uma anomalia grave na triagem, muda o status para admitido
            if is_anomalia and row['status'] == 'triado':
                conn.execute(text("UPDATE pacientes SET status = 'admitido' WHERE id = :p"), {"p": row['paciente_id']})
                detalhe = f"ALERTA CRÍTICO: Paciente ID {row['paciente_id']} com status admitido na auditoria após triagem alterada (Leitura ID: {row['med_id']})"
                registrar_log("ALERTA", "Admissão Hospitalar", detalhe)
                print(f"⚠️ {detalhe}")
        conn.commit()

schedule.every(3).seconds.do(analisar_dados)

print("Iniciando MOTOR ANALÍTICO (IA)...")
while True:
    schedule.run_pending()
    time.sleep(1)