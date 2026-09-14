DROP TABLE IF EXISTS logs_auditoria CASCADE;
DROP TABLE IF EXISTS medicoes CASCADE;
DROP TABLE IF EXISTS pacientes CASCADE;

CREATE TABLE logs_auditoria (
    id SERIAL PRIMARY KEY,
    nivel_log VARCHAR(20),
    evento VARCHAR(100),
    detalhes TEXT,
    data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pacientes (
    id SERIAL PRIMARY KEY,
    status VARCHAR(20) DEFAULT 'triado', -- Pode ser: triado, admitido, alta
    checkups_normais INT DEFAULT 0
);

CREATE TABLE medicoes (
    id SERIAL PRIMARY KEY,
    paciente_id INT REFERENCES pacientes(id),
    pressao_sistolica INT,
    pressao_diastolica INT,
    frequencia_cardiaca INT,
    adesao_tratamento DECIMAL(3,2),
    anomalia_detectada BOOLEAN, -- A IA preencherá isso de forma independente
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inserindo dados base para a IA ter parâmetro inicial de normalidade
INSERT INTO pacientes (status) VALUES ('triado'), ('triado'), ('triado');
INSERT INTO medicoes (paciente_id, pressao_sistolica, pressao_diastolica, frequencia_cardiaca, adesao_tratamento, anomalia_detectada) VALUES 
(1, 120, 80, 72, 0.95, FALSE), (2, 118, 79, 68, 0.88, FALSE), (3, 122, 82, 75, 0.90, FALSE);