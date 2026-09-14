import random, time, schedule
from sqlalchemy import create_engine, text

engine = create_engine('postgresql://postgres:123@localhost/banco_clinico')

def registrar_log(nivel, evento, detalhes):
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO logs_auditoria (nivel_log, evento, detalhes) VALUES (:n, :e, :d)"), 
                     {"n": nivel, "e": evento, "d": detalhes})
        conn.commit()

def simular_triagem():
    with engine.connect() as conn:
        res = conn.execute(text("INSERT INTO pacientes (status) VALUES ('triado') RETURNING id"))
        paciente_id = res.scalar()
        
        # 80% normal, 20% com risco de internação
        if random.random() > 0.20:
            sis, dia, fc, ad = random.randint(110, 129), random.randint(70, 84), random.randint(60, 85), round(random.uniform(0.8, 1.0), 2)
        else:
            sis, dia, fc, ad = random.randint(160, 190), random.randint(100, 120), random.randint(110, 130), round(random.uniform(0.1, 0.4), 2)
            
        conn.execute(text("""
            INSERT INTO medicoes (paciente_id, pressao_sistolica, pressao_diastolica, frequencia_cardiaca, adesao_tratamento)
            VALUES (:p, :s, :d, :f, :a)
        """), {"p": paciente_id, "s": sis, "d": dia, "f": fc, "a": ad})
        conn.commit()
        
    detalhe = f"nova coleta de dados realizada. Paciente ID {paciente_id} com status triado (PA: {sis}x{dia}, FC: {fc})"
    registrar_log("INFO", "Triagem", detalhe)
    print(f"🩺 [TRIAGEM] {detalhe}")

def realizar_checkups():
    with engine.connect() as conn:
        admitidos = conn.execute(text("SELECT id, checkups_normais FROM pacientes WHERE status = 'admitido'")).fetchall()
        
        for pac in admitidos:
            paciente_id, checkups = pac[0], pac[1]
            last_med = conn.execute(text("SELECT pressao_sistolica, pressao_diastolica, frequencia_cardiaca, anomalia_detectada FROM medicoes WHERE paciente_id = :p ORDER BY id DESC LIMIT 1"), {"p": paciente_id}).fetchone()
            
            # Se a IA avaliou o último checkup como normal (FALSE para anomalia)
            if last_med and last_med[3] == False: 
                checkups += 1
                conn.execute(text("UPDATE pacientes SET checkups_normais = :c WHERE id = :p"), {"c": checkups, "p": paciente_id})
            
            if checkups >= 3:
                conn.execute(text("UPDATE pacientes SET status = 'alta' WHERE id = :p"), {"p": paciente_id})
                detalhe = f"nova coleta de dados realizada (Saída). Paciente ID {paciente_id} com status ALTA após estabilidade clínica."
                registrar_log("ALTA", "Expurgo", detalhe)
                print(f"✅ [ALTA] {detalhe}")
            else:
                # Regra de saúde: simula a medicação agindo e trazendo os sinais de volta ao normal (120/80, 75BPM)
                sis = max(120, last_med[0] - random.randint(5, 15))
                dia = max(80, last_med[1] - random.randint(3, 10))
                fc = max(75, last_med[2] - random.randint(5, 12))
                
                conn.execute(text("""
                    INSERT INTO medicoes (paciente_id, pressao_sistolica, pressao_diastolica, frequencia_cardiaca, adesao_tratamento)
                    VALUES (:p, :s, :d, :f, 1.0)
                """), {"p": paciente_id, "s": sis, "d": dia, "f": fc})
                
                detalhe = f"nova coleta de dados realizada. Checkup do Paciente ID {paciente_id} com status admitido (PA: {sis}x{dia}, FC: {fc})."
                registrar_log("INFO", "Checkup", detalhe)
                print(f"🛏️ [CHECKUP] {detalhe}")
        conn.commit()

schedule.every(5).seconds.do(simular_triagem) # Simula o intervalo de 5 min da triagem
schedule.every(30).seconds.do(realizar_checkups) # Simula o intervalo de 30 min do checkup de leito

print("Iniciando SIMULADOR DE ENTRADAS...")
while True:
    schedule.run_pending()
    time.sleep(1)