import requests
import time
import math
import os
import logging
from geopy.distance import geodesic
import mysql.connector
from datetime import datetime

# --- CONFIGURAÇÕES & CONSTANTES ---
# Em produção, mover SENHAS para variáveis de ambiente (os.environ)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'seu_usuario', 
    'password': 'sua_senha', 
    'database': 'aero_ops',
    'use_pure': True
}

# Configuração dos Aeroportos Monitorados
AEROPORTOS = {
    'SBGR': {'nome': 'Guarulhos', 'coords': (-23.4356, -46.4731), 'alt_ref': 2430},
    'SBSP': {'nome': 'Congonhas', 'coords': (-23.6261, -46.6564), 'alt_ref': 2631},
    'SBKP': {'nome': 'Viracopos', 'coords': (-23.0074, -47.1344), 'alt_ref': 2170}
}

RAIO_ANALISE_KM = 150     # Busca focada em SP
RAIO_CRITICO_KM = 80      # Raio para validar "chegada"

# Configuração de Cores para Terminal
class Cores:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Logging Básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CLASSE: GERENCIADOR DE BANCO DE DADOS ---
class AeroDatabase:
    """Gerencia conexões e persistência de dados de forma eficiente (Batch)"""
    def __init__(self):
        self.conn = None
        self.cursor = None

    def conectar(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            logging.info("Conectado ao Banco de Dados.")
        except Exception as e:
            logging.error(f"Falha ao conectar no BD: {e}")

    def desconectar(self):
        if self.cursor: self.cursor.close()
        if self.conn: self.conn.close()

    def salvar_ciclo(self, dados_clima_map, voos_identificados_map):
        """
        Salva TODO o ciclo de uma vez.
        1. Insere dados de clima (Um por aeroporto).
        2. Insere dados de voos vinculados ao ID do clima.
        """
        if not self.conn or not self.conn.is_connected():
            self.conectar()
        
        try:
            # 1. Salvar Clima e obter IDs
            clima_ids = {} # { 'SBGR': 123, 'SBSP': 124 }
            sql_clima = """INSERT INTO FACT_CONDICOES_POUSO 
                           (aeroporto_destino, vento_velocidade, chuva_mm, risco_calculado)
                           VALUES (%s, %s, %s, %s)"""
            
            for icao, clima in dados_clima_map.items():
                risco = "Critico" if clima['chuva'] > 0.5 or clima['vento'] > 30 else \
                        "Medio" if clima['chuva'] > 0.1 else "Baixo"
                
                self.cursor.execute(sql_clima, (icao, clima['vento'], clima['chuva'], risco))
                clima_ids[icao] = self.cursor.lastrowid

            # 2. Salvar Voos (Batch)
            if not voos_identificados_map:
                return

            sql_voo = """INSERT INTO FACT_VOO_TELEMETRIA 
                         (callsign, aeroporto_alvo, latitude, longitude, altitude_pes, 
                          velocidade_kmh, distancia_destino_km, status_pontualidade, 
                          tendencia_velocidade, motivo_atraso, alerta_emergencia, eta_real_min, id_clima_fk) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            valores_voos = []
            for aviao in voos_identificados_map.values():
                icao_alvo = aviao['aeroporto_alvo']
                id_clima = clima_ids.get(icao_alvo)
                
                valores_voos.append((
                    aviao['callsign'], icao_alvo, aviao['lat'], aviao['lon'], aviao['alt'],
                    aviao['vel'], aviao['dist'], aviao['status'], aviao['tendencia'], 
                    aviao['motivo'], aviao['emergencia'], aviao['eta'], id_clima
                ))
            
            if valores_voos:
                self.cursor.executemany(sql_voo, valores_voos)
                self.conn.commit()
                logging.info(f"Ciclo persistido: {len(valores_voos)} voos salvos.")

        except Exception as e:
            logging.error(f"Erro ao salvar ciclo no banco: {e}")
            self.conn.rollback()


# --- CLASSE: INTELIGÊNCIA GEODÉSICA ---
class AeroAnalytics:
    @staticmethod
    def calcular_bearing(lat1, lon1, lat2, lon2):
        """Calcula o ângulo de direção (Azimute) entre dois pontos"""
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        y = math.sin(lon2 - lon1) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        return (math.degrees(math.atan2(y, x)) + 360) % 360

    @staticmethod
    def calcular_score_afinidade(aviao_lat, aviao_lon, aviao_track, aero_coords):
        """
        Retorna um SCORE (0-100) da probabilidade deste avião estar indo para este aeroporto.
        Baseado em: Distância e Alinhamento (Bearing vs Track).
        """
        distancia = geodesic((aviao_lat, aviao_lon), aero_coords).kilometers
        if distancia > RAIO_ANALISE_KM: return 0
        
        # Angulo ideal para chegar no aeroporto
        bearing_ideal = AeroAnalytics.calcular_bearing(aviao_lat, aviao_lon, aero_coords[0], aero_coords[1])
        
        # Diferença entre para onde o avião está apontando (track) e onde está o aeroporto
        diff_angulo = abs(aviao_track - bearing_ideal)
        diff_angulo = min(diff_angulo, 360 - diff_angulo) # Ajuste para virada de 360 graus
        
        # Score System
        # Se apontar exatamente: 100 pts. Se apontar 90 graus errado: 0 pts.
        score_alinhamento = max(0, 100 - (diff_angulo * 2)) 
        
        # Penalidade de Distância (opcional, aqui focamos em quem está alinhado)
        return score_alinhamento

# --- CLASSE: CONTROLADOR DE VOOS (CORE) ---
class FlightSeer:
    def __init__(self):
        self.db = AeroDatabase()
        self.historico = {} # Cache local para comparar descida

    def buscar_clima(self, coords):
        """Busca Clima (Resiliente e Preciso)"""
        # Adicionado timezone=auto para garantir que o hourly[0] seja 00:00 local
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords[0]}&longitude={coords[1]}&current=precipitation,wind_speed_10m&hourly=precipitation_probability&forecast_days=1&timezone=auto"
        try:
            r = requests.get(url, timeout=5).json()
            
            # Obtém a hora atual para pegar a probabilidade correta do array hourly
            hora_atual = datetime.now().hour
            probabilidades = r.get("hourly", {}).get("precipitation_probability", [0] * 24)
            
            # Garante que o índice existe (segurança)
            prob_atual = probabilidades[hora_atual] if len(probabilidades) > hora_atual else probabilidades[0]

            return {
                "chuva": r.get("current", {}).get("precipitation", 0),
                "vento": r.get("current", {}).get("wind_speed_10m", 0),
                "prob": prob_atual
            }
        except Exception as e:
            logging.error(f"Erro ao buscar clima: {e}")
            return {"chuva": 0, "vento": 0, "prob": 0}

    def executar_ciclo(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{Cores.HEADER}{Cores.BOLD}==================================================================")
        print(f"✈️  SKYCARGO LOGISTICS INTELLIGENCE - AERO OPS PREDICTOR V3.1 (Refined)")
        print(f"=================================================================={Cores.ENDC}")
        
        # 1. Obter Clima (Cache)
        clima_map = {} 
        for icao, dados in AEROPORTOS.items():
            clima_map[icao] = self.buscar_clima(dados['coords'])

        # 2. Buscar Aviões (Global)
        centro_lat, centro_lon = -23.5, -46.6 # SP Centro
        url_radar = f"https://api.adsb.lol/v2/lat/{centro_lat}/lon/{centro_lon}/dist/180"
        
        voos_identificados_map = {} # callsign -> dados
        
        try:
            resp = requests.get(url_radar, timeout=10).json()
            lista_avioes = resp.get("ac", [])
            
            # 3. Lógica Melhorada de Destino
            for a in lista_avioes:
                callsign = a.get("flight", "").strip()
                if not callsign or len(callsign) < 3: continue
                
                lat, lon = a.get("lat"), a.get("lon")
                track = a.get("track", 0)
                alt = a.get("alt_baro", "ground")
                if alt == "ground": alt = 0
                else: alt = float(alt)
                gs = float(a.get("gs", 0)) * 1.852 # Knots to Km/h

                if gs < 50: continue 

                # --- FILTROS DE INTELIGÊNCIA ---
                # 1. Filtro de Subida (Take-off / Go-Around)
                baro_rate = a.get("baro_rate", 0)
                if baro_rate > 500:
                    continue

                melhor_score = 0
                melhor_dest = None
                dist_para_melhor = 0

                for icao, aero_data in AEROPORTOS.items():
                    dist = geodesic((lat, lon), aero_data['coords']).kilometers
                    
                    # 2. LOGICA NOVA: Filtro de Altitude e Historico
                    if dist < 80 and alt > 10000: continue 

                    if callsign in self.historico:
                        prev = self.historico[callsign]
                        # Se afastou mais de 2km do target anterior, ignora
                        if prev.get('target') == icao and dist > prev.get('dist', 9999) + 2:
                            continue

                    score = AeroAnalytics.calcular_score_afinidade(lat, lon, track, aero_data['coords'])
                    
                    # LOGICA AVANÇADA DE PERFIL VERTICAL (GLIDESLOPE - V2)
                    # Refinado para o caso GLO1043 (1860m = ~6100ft).
                    # Rampa de 3 graus é aprox 320 ft/km. 
                    # Reduzimos a tolerância de 900 para 450 ft/km para pegar quem está "alto demais".
                    
                    altura_relativa = alt - aero_data['alt_ref']
                    max_altura_viavel = (dist * 450) + 1500 # 450ft/km + 1500ft buffer
                    
                    if altura_relativa > max_altura_viavel:
                         score -= 50 
                    
                    # Penalidade Extra de Curto Alcance:
                    # Se você está muito perto (<10km) e muito alto (>3000ft acima), penaliza dobrado.
                    if dist < 10 and altura_relativa > 3000:
                        score -= 100

                    if dist < RAIO_ANALISE_KM:
                        if score > melhor_score:
                            melhor_score = score
                            melhor_dest = icao
                            dist_para_melhor = dist

                # Só confirma se tiver certeza (Score > 85)
                if melhor_score > 85 and melhor_dest:
                    clima_dest = clima_map[melhor_dest]
                    
                    # Regras de Negócio (Atraso e Emergência)
                    atraso_min = 0; motivo = "Operacao Normal"; status = "No Horario"
                    if clima_dest['vento'] > 30 or clima_dest['chuva'] > 0.5:
                        atraso_min += 15
                        status = "Atrasado"
                        motivo = "Condicoes Meteorologicas"

                    # Nova Lógica: Alerta de Emergência (Altitude < 5000 e Distância > 50km)
                    emergencia = 1 if (alt < 5000 and dist_para_melhor > 50) else 0
                    if emergencia:
                        status = "EMERGÊNCIA"
                        motivo = "Desvio / Altitude Crítica"

                    eta = ((dist_para_melhor / gs) * 60) + atraso_min if gs > 0 else 0

                    voos_identificados_map[callsign] = {
                        'callsign': callsign, 'aeroporto_alvo': melhor_dest,
                        'lat': lat, 'lon': lon, 'alt': alt, 'vel': gs,
                        'dist': dist_para_melhor, 'status': status,
                        'tendencia': "Estavel", 'motivo': motivo, 'eta': eta,
                        'emergencia': emergencia
                    }
                    # Atualizamos histórico com o target atual
                    self.historico[callsign] = {'gs': gs, 'time': time.time(), 'target': melhor_dest, 'dist': dist_para_melhor}

            # 4. EXIBIÇÃO VISUAL (Estilo Antigo Bonito)
            # Agrupar por aeroporto para exibição
            voos_por_aero = {icao: [] for icao in AEROPORTOS}
            for v in voos_identificados_map.values():
                if v['aeroporto_alvo'] in voos_por_aero:
                    voos_por_aero[v['aeroporto_alvo']].append(v)

            for icao, info in AEROPORTOS.items():
                clima = clima_map[icao]
                pista_status = f"{Cores.GREEN}SECA{Cores.ENDC}" if clima['chuva'] < 0.2 else f"{Cores.FAIL}MOLHADA{Cores.ENDC}"
                
                print(f"\n{Cores.BOLD}📍 AEROPORTO: {info['nome']} ({icao}){Cores.ENDC}")
                print(f"   [Pista: {pista_status} | Vento: {clima['vento']}km/h | Prob. Chuva: {clima['prob']}%]")
                print(f"   {'-'*60}")

                lista_voos = voos_por_aero[icao]
                if not lista_voos:
                    print(f"   {Cores.BLUE}Nenhum voo em aproximação detectado.{Cores.ENDC}")
                else:
                    # Ordenar por ETA
                    lista_voos.sort(key=lambda x: x['dist'])
                    for v in lista_voos:
                        color_status = Cores.WARNING if v['status'] == "EMERGÊNCIA" else (Cores.GREEN if v['status'] == "No Horario" else Cores.FAIL)
                        print(f"   ✈️  {Cores.BOLD}{v['callsign']:8}{Cores.ENDC} | Alt: {int(v['alt']):5}ft | Dist: {int(v['dist']):3}km | ETA: {int(v['eta']):3}min | Status: {color_status}{v['status']:10}{Cores.ENDC}")

            # Persistir
            self.db.salvar_ciclo(clima_map, voos_identificados_map)

        except Exception as e:
            print(f"Erro no ciclo de radar: {e}")

    def loop(self):
        try:
            while True:
                self.executar_ciclo()
                print("\nEsperando 5 minutos para o próximo ciclo...")
                time.sleep(300)
        except KeyboardInterrupt:
            print("Encerrando...")
            self.db.desconectar()

if __name__ == "__main__":
    app = FlightSeer()
    app.loop()
