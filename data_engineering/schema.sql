CREATE DATABASE IF NOT EXISTS aero_ops;
USE aero_ops;

-- Tabela unificada de condições climáticas
-- Evita duplicação: inserimos o clima de um aeroporto a cada ciclo de monitoramento
CREATE TABLE IF NOT EXISTS FACT_CONDICOES_POUSO (
    id_clima INT AUTO_INCREMENT PRIMARY KEY,
    aeroporto_destino VARCHAR(10) NOT NULL, -- Ex: SBGR, SBSP
    vento_velocidade DECIMAL(5,2) NOT NULL,
    chuva_mm DECIMAL(5,2) NOT NULL,
    risco_calculado ENUM('Baixo', 'Médio', 'Crítico') NOT NULL,
    timestamp_leitura DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Telemetria de Voo otimizada
CREATE TABLE IF NOT EXISTS FACT_VOO_TELEMETRIA (
    id_log BIGINT AUTO_INCREMENT PRIMARY KEY,
    callsign VARCHAR(10) NOT NULL,
    aeroporto_alvo VARCHAR(10) NOT NULL,
    latitude DECIMAL(10, 6) NOT NULL,  -- Precisão correta para GPS
    longitude DECIMAL(10, 6) NOT NULL, -- Precisão correta para GPS
    altitude_pes INT,
    velocidade_kmh DECIMAL(6,2) NOT NULL,
    distancia_destino_km DECIMAL(6,2) NOT NULL,
    
    -- Colunas de Negócio
    status_pontualidade VARCHAR(20), -- 'No Horário', 'Atrasado'
    tendencia_velocidade VARCHAR(50), -- 'Estável', 'Recuperando'
    motivo_atraso VARCHAR(255),
    
    id_clima_fk INT,
    timestamp_coleta DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_clima_voo FOREIGN KEY (id_clima_fk) REFERENCES FACT_CONDICOES_POUSO(id_clima)
);

-- Índices para performance em consultas futuras
CREATE INDEX idx_timestamp ON FACT_VOO_TELEMETRIA(timestamp_coleta);



-- Adiciona a coluna de Alerta de Emergência
ALTER TABLE FACT_VOO_TELEMETRIA 
ADD COLUMN alerta_emergencia TINYINT(1) DEFAULT 0 AFTER motivo_atraso;
-- Adiciona a coluna de ETA Real
ALTER TABLE FACT_VOO_TELEMETRIA 
ADD COLUMN eta_real_min DECIMAL(6,2) AFTER alerta_emergencia;
-- Atualiza o comentário da coluna de status para incluir EMERGÊNCIA
ALTER TABLE FACT_VOO_TELEMETRIA 
MODIFY COLUMN status_pontualidade VARCHAR(20) COMMENT 'No Horário, Atrasado, EMERGÊNCIA';

SELECT * 
FROM FACT_VOO_TELEMETRIA 
ORDER BY id_log DESC 
LIMIT 3000;

SELECT * 
FROM FACT_CONDICOES_POUSO 
;

-- Desabilita temporariamente a verificação de chaves estrangeiras
SET FOREIGN_KEY_CHECKS = 0;

-- Limpa ambas as tabelas e reseta os contadores de ID (Auto Increment)
TRUNCATE TABLE FACT_VOO_TELEMETRIA;
TRUNCATE TABLE FACT_CONDICOES_POUSO;

-- Reabilita a verificação de chaves estrangeiras
SET FOREIGN_KEY_CHECKS = 1;






