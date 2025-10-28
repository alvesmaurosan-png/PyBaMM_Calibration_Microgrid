import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

# ==============================================================================
# 1. DADOS E FUNÇÃO DE DEGRADAÇÃO (Resultado do Passo 1)
# ==============================================================================

# Taxa de degradação K_DoD em (Perda de SoH por ciclo) * 100
# Estes dados substituem a chamada direta ao PyBaMM
DEGRADATION_RATES = pd.DataFrame({
    'DoD_pct': [0.0, 10.0, 50.0, 100.0],
    'Rate_per_100_EFC': [0.0, 0.015, 0.075, 0.150]  # Taxa em % do SoH inicial por 100 EFC
})

# Função de Interpolação para obter a taxa K_DoD
rate_interp_func = interp1d(
    DEGRADATION_RATES['DoD_pct'],
    DEGRADATION_RATES['Rate_per_100_EFC'],
    kind='linear',
    fill_value="extrapolate"
)


def get_rate_per_efc(dod_pct):
    """
    Consulta a tabela de degradação (resultado do Passo 1) e retorna a taxa
    de perda de SOH (em % do SOH inicial) por Ciclo Equivalente Completo (EFC).
    """
    # Limita o DoD entre 0 e 100% para a interpolação
    dod_clipped = np.clip(dod_pct, 0, 100)

    # Obtém a taxa por 100 EFC
    rate_per_100_efc = rate_interp_func(dod_clipped)

    # Retorna a taxa por 1 EFC (garantindo que não seja negativa)
    return max(0, rate_per_100_efc / 100)


# ==============================================================================
# 2. SIMULAÇÃO HORÁRIA (8760 HORAS)
# ==============================================================================

# --- Parâmetros de Entrada ---
CAPACITY_NOMINAL_AH = 100.0  # Capacidade Nominal (Ah) do Sistema
INITIAL_SOH_PCT = 80.0  # SoH inicial (Bateria de segunda vida)
DAYS_OF_SIMULATION = 365
HOURS_OF_SIMULATION = DAYS_OF_SIMULATION * 24
EFC_UPDATE_INTERVAL = 24  # Frequência de atualização da degradação (ex: a cada 24 horas)


# --- Perfil de Uso (Exemplo de Carga/Descarga Horária) ---
# Vamos simular um perfil de uso que varia, forçando diferentes DoD's e ciclos.
# Suponhamos que o C-rate máximo seja 1C, e o sistema opera a 0.25C (25A para 100Ah)
def generate_hourly_current(hours):
    # Simula um ciclo de 60% DoD por dia: Descarrega 12h, Carrega 12h
    current = np.zeros(hours)

    # Taxa de corrente para 25% da capacidade (0.25C)
    current_rate = 0.25 * CAPACITY_NOMINAL_AH

    for i in range(hours):
        hour_of_day = i % 24
        if 8 <= hour_of_day < 20:  # Descarga das 8h às 20h
            current[i] = -current_rate  # Negativo para Descarga
        elif 20 <= hour_of_day < 24 or 0 <= hour_of_day < 8:  # Carga no restante
            current[i] = current_rate

    return current


# Simulação de 1 ano
hourly_current_profile = generate_hourly_current(HOURS_OF_SIMULATION)

# --- Inicialização das Variáveis ---
time_hours = np.arange(HOURS_OF_SIMULATION)
results = pd.DataFrame({'Hora': time_hours, 'Corrente_A': hourly_current_profile})

# Inicializa o SoH e a Capacidade
results['SOH_Pct'] = np.nan
results['Capacity_Ah'] = np.nan
results['SoC_Pct'] = np.nan

# Capacidade inicial real em Ah (base para todos os cálculos de SoH/SoC)
CAPACITY_INITIAL_SOH_AH = (INITIAL_SOH_PCT / 100) * CAPACITY_NOMINAL_AH

# Variáveis que mudam ao longo do tempo
current_soh_pct = INITIAL_SOH_PCT
current_capacity_ah = CAPACITY_INITIAL_SOH_AH
current_soc_pct = 100.0  # Começa no SoC máximo
total_efc_accumulated = 0.0

# ==============================================================================
# 3. LOOP DE SIMULAÇÃO HORA A HORA
# ==============================================================================

print(f"\nIniciando Simulação Horária: {HOURS_OF_SIMULATION} horas.")
print(f"Capacidade inicial: {current_capacity_ah:.2f} Ah ({INITIAL_SOH_PCT:.1f}% SoH)")

# Variáveis temporárias para monitoramento de degradação
last_soc = current_soc_pct
dod_buffer_sum = 0.0  # Acumulador de Profundidade de Descarga para EFC

for i in time_hours:
    I_h = results.loc[i, 'Corrente_A']  # Corrente da hora (A)

    # 1. CÁLCULO DA MUDANÇA DE SOC (Estado de Carga)
    # Delta SoC = (Corrente * 1 hora) / Capacidade Atual
    delta_soc_pct = (I_h * 1) / current_capacity_ah * 100

    # Atualiza o SoC (limitando a 0 e 100)
    new_soc_pct = current_soc_pct + delta_soc_pct
    new_soc_pct = np.clip(new_soc_pct, 0.0, 100.0)

    # 2. CÁLCULO DOS CICLOS EQUIVALENTES COMPLETOS (EFC)
    # A degradação é calculada pelo "tamanho" do ciclo (DoD), não pela direção.
    # O EFC é o DoD dividido por 200 (para ciclos de 100%)

    dod_in_hour = abs(new_soc_pct - current_soc_pct)  # Perda/Ganho de SoC (DoD) na hora
    dod_buffer_sum += dod_in_hour

    # O EFC é a soma cumulativa dos DoD's
    if dod_buffer_sum >= 200.0:  # Um ciclo completo (100% Carga + 100% Descarga = 200%)
        # EFCs concluídos (pode ser mais de um se o buffer for grande)
        efc_this_hour = dod_buffer_sum / 200.0
        total_efc_accumulated += efc_this_hour

        # O DoD médio que gerou este EFC é o DoD acumulado (200% ou mais).
        # Para ser realista, usamos a taxa K_DoD obtida no Passo 1.
        # No entanto, a forma mais simples de integrar é usar a taxa de 100% DoD
        # ou, mais corretamente, aplicar a taxa por EFC.

        # Taxa de degradação por 1 EFC (usando DoD de 100% como referência para o EFC)
        rate_per_efc = get_rate_per_efc(100.0)

        # Perda de capacidade (em % do SOH inicial)
        soh_fade_pct_of_initial = rate_per_efc * efc_this_hour * 100

        # Perda de capacidade em Ah (baseada na capacidade inicial de 80% SoH)
        capacity_fade_ah = (soh_fade_pct_of_initial / 100) * CAPACITY_INITIAL_SOH_AH

        # Atualiza a capacidade e SOH
        current_capacity_ah -= capacity_fade_ah

        # Reseta o buffer para o que sobrou (o resto da divisão)
        dod_buffer_sum %= 200.0

        # 3. ATUALIZAÇÃO PARA O PRÓXIMO PASSO
    current_soc_pct = new_soc_pct
    current_soh_pct = (current_capacity_ah / CAPACITY_NOMINAL_AH) * 100

    # Armazenamento dos resultados
    results.loc[i, 'Capacity_Ah'] = current_capacity_ah
    results.loc[i, 'SOH_Pct'] = current_soh_pct
    results.loc[i, 'SoC_Pct'] = current_soc_pct

    if i % 876 == 0 and i > 0:  # Imprime a cada 10% do ano
        print(f"Hora {i} (Dia {i / 24:.0f}): EFC Acc. = {total_efc_accumulated:.1f}, SoH = {current_soh_pct:.2f}%")

# ==============================================================================
# 4. RESULTADOS E VISUALIZAÇÃO
# ==============================================================================

print(f"\n--- Simulação Completa (1 Ano) ---")
print(f"SoH Inicial: {INITIAL_SOH_PCT:.2f}%")
print(f"SoH Final: {results['SOH_Pct'].iloc[-1]:.2f}%")
print(f"EFCs Totais: {total_efc_accumulated:.1f}")

# Gráfico de Degradação (SOH) e SoC
fig, ax1 = plt.subplots(figsize=(12, 6))

color = 'tab:red'
ax1.set_xlabel('Hora de Simulação')
ax1.set_ylabel('SOH (%)', color=color)
ax1.plot(results['Hora'], results['SOH_Pct'], color=color, label='SOH (%)')
ax1.tick_params(axis='y', labelcolor=color)

ax2 = ax1.twinx()  # Cria um segundo eixo y
color = 'tab:blue'
ax2.set_ylabel('SoC (%)', color=color)
# Plota o SoC, amostrando apenas um ponto a cada 10 horas para não sobrecarregar
ax2.plot(results['Hora'], results['SoC_Pct'], color=color, alpha=0.5, label='SoC (%)')
ax2.tick_params(axis='y', labelcolor=color)

fig.tight_layout()
plt.title('Simulação Horária: Degradação do SOH vs. SoC')
plt.grid(True, linestyle=':', alpha=0.5)
plt.show()

# Salvar resultados
results.to_csv("simulacao_horaria_8760h.csv", index=False)
print("\nDados detalhados da simulação horária salvos em 'simulacao_horaria_8760h.csv'")