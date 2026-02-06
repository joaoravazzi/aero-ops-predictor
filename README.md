# ✈️ Aero Ops Predictor (Logistics Intelligence)

Este projeto foi desenvolvido como trabalho de conclusão no bootcamp da **Generation Brasil**, com o apoio e patrocínio do **Grupo Cyrela** e **CashMe**. O foco é resolver um desafio real de logística crítica para a **SkyCargo Logistics**, empresa especializada no transporte de órgãos para transplante e peças urgentes de maquinário.

## 📋 O Problema de Negócio
A SkyCargo enfrentava dificuldades ao depender de painéis de aeroportos atualizados manualmente, que muitas vezes não refletiam atrasos reais causados por condições climáticas severas. Isso gerava a perda de tempo crítico para ambulâncias e caminhões que aguardavam as cargas na pista.

**A Solução:** Desenvolvemos uma "Torre de Controle Própria" que calcula o **ETA Real (Estimated Time of Arrival)** cruzando a posição física da aeronave via telemetria com as condições meteorológicas exatas do aeroporto de destino.

---

## 🛠️ Tecnologias Utilizadas
* **Python:** Motor de coleta e processamento geodésico.
* **SQL (MySQL):** Modelagem de dados e persistência para auditoria de voos.
* **Power BI:** Dashboards analíticos para monitoramento e matriz de risco.
* **Bibliotecas Principais:** `geopy` (Cálculo de distância geodésica), `requests` (Integração com APIs ADS-B e OpenMeteo) e `mysql-connector`.

---

## 🧠 Inteligência do Sistema e Regras de Negócio
O motor de predição utiliza as seguintes lógicas para garantir a precisão logística:
* **Cálculo Geodésico:** Considera a curvatura da Terra através da biblioteca `geopy` para calcular a distância exata até a pista.
* **Fator Clima:** Adiciona +10 min ao ETA se o vento no destino for > 30 km/h e +15 min se houver precipitação > 0.5mm.
* **Alerta de Emergência:** Identificação automática de queda drástica de altitude (> 5000 pés) longe do aeroporto, gerando flag de desvio crítico.

---

## 📊 Visualização de Dados
O dashboard final responde a perguntas críticas de negócio:
* **Mapa de Rastreio:** Plota a rota real do avião baseada na telemetria coletada no SQL.
* **Análise de Performance:** Gráficos que mostram o comportamento de velocidade e altitude da aeronave ao longo do tempo.
* **Matriz de Risco:** Monitoramento da pontualidade e condições de pista (Seca vs. Molhada).

---

## 📂 Como Utilizar este Repositório
Por questões de segurança e proteção de dados, as credenciais de acesso ao banco de dados foram removidas dos scripts. Para replicar o projeto:

1.  **Banco de Dados:** Execute o arquivo `schema.sql` em seu servidor MySQL local para criar a estrutura das tabelas `FACT_VOO_TELEMETRIA` e `FACT_CONDICOES_POUSO`.
2.  **Configuração:** No arquivo `functions.py`, insira suas credenciais (Host, User e Password) no dicionário `DB_CONFIG`.
3.  **Execução:** Execute o script `functions.py` para iniciar o monitoramento em loop (atualização recomendada a cada 5 minutos).

---

## 🚀 Próximos Passos
* **Machine Learning:** Implementação de modelos de regressão (XGBoost/Random Forest) para prever padrões de órbita e refinar o ETA de forma preditiva.
* **Dados Premium:** Transição para APIs de baixa latência para garantir disponibilidade total em escala industrial.

---

## 👥 Agradecimentos
* **Equipe:** João Victor Ravazzi Ferretti, Andrey Alves Miranda, Carrie Jenniffer Alves Mota, Juliana Malheiros, Leandro Falasca.
* **Instrutores:** Luiz Chiavini e Samuel Reginatto
* **Apoiadores:** Generation Brasil, Grupo Cyrela e CashMe.
