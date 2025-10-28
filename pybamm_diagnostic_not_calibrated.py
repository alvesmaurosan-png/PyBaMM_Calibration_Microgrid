import pybamm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL (Dados do Artigo)
# ==============================================================================

# Definição dos parâmetros globais do sistema (do artigo PV+ESS)
CAPACITY_NOMINAL_KWH = 38.8
SOH_INITIAL = 0.80
CAPACITY_REMAINING_KWH = CAPACITY_NOMINAL_KWH * SOH_INITIAL

DOD_MAX_PCT = 0.25
DAILY_CYCLE_ENERGY_KWH = CAPACITY_REMAINING_KWH * DOD_MAX_PCT

TIME_YEARS = 10
TOTAL_CYCLES = 922

# Parâmetros Elétricos/Uso (assumindo LFP e sistema de 400V)
V_SYSTEM_NOMINAL = 400
LOW_CYCLE_POWER_KW = 7.76

# Definição dos Horários de Uso (para perfis de 24h)
DISCHARGE_START_HOUR = 17
DISCHARGE_END_HOUR = 21
CHARGE_START_HOUR = 11
CHARGE_END_HOUR = 15

# Valores de Geometria da Célula (Para cálculo da Área e resolução dos KeyErrors)
ELECTRODE_WIDTH_M = 0.203
ELECTRODE_HEIGHT_M = 0.233
CELL_AREA_M2 = ELECTRODE_WIDTH_M * ELECTRODE_HEIGHT_M

# Carregar modelo e parâmetros
model = pybamm.lithium_ion.SPM(options={"working electrode": "both"})
parameter_values = pybamm.ParameterValues(chemistry=pybamm.parameter_sets.Chen2020)

print("Configuração de parâmetros concluída. O ambiente está pronto para simulação.")


# ==============================================================================
# 2. DEFINIÇÃO DO PERFIL DE USO E CRIAÇÃO DO EXPERIMENTO PYBAMM
# ==============================================================================

# --- 1. DEFINIÇÃO DA FUNÇÃO ---
def generate_hourly_power_profile_low_cycle(hours):
    """Gera o perfil de uso: Descarga e Carga intermediária por 4h."""
    power_profile = np.zeros(hours)
    for i in range(hours):
        hour_of_day = i % 24
        # DESCARGA (corrente negativa)
        if DISCHARGE_START_HOUR <= hour_of_day < DISCHARGE_END_HOUR:
            power_profile[i] = -LOW_CYCLE_POWER_KW
        # CARGA (corrente positiva)
        elif CHARGE_START_HOUR <= hour_of_day < CHARGE_END_HOUR:
            power_profile[i] = LOW_CYCLE_POWER_KW
    return power_profile


# --- 2. CRIAÇÃO DA TABELA DE CORRENTE E INTERPOLAÇÃO ---
hourly_power_profile = generate_hourly_power_profile_low_cycle(24)
I_cycle_A = hourly_power_profile * 1000 / V_SYSTEM_NOMINAL

time_hours_x = np.arange(0, 24, 1)

interpolation_data = np.column_stack((time_hours_x, I_cycle_A))

current_interpolator = pybamm.Interpolant(
    interpolation_data,
    pybamm.t
)

# 3. Execução da Simulação de Envelhecimento Acelerado
experiment = pybamm.Experiment(
    ["Rest for 24 hours"] * TOTAL_CYCLES,
    period="24 hours"
)

# 4. Inserção dos Parâmetros Ausentes e da Corrente
missing_params = {
    # Geometria
    "Electrode width [m]": ELECTRODE_WIDTH_M,
    "Electrode height [m]": ELECTRODE_HEIGHT_M,
    "Number of electrodes connected in parallel to make a cell": 1,
    "Negative electrode thickness [m]": 8.58e-05,
    "Positive electrode thickness [m]": 8.58e-05,

    # Corrente
    "Current function [A]": current_interpolator
}

parameter_values.update(
    missing_params,
    check_already_exists=False
)

print(f"\nIniciando simulação SPM de {TOTAL_CYCLES} ciclos ({TIME_YEARS} anos)...")

# 5. Resolver o Modelo
sim = pybamm.Simulation(
    model,
    experiment=experiment,
    parameter_values=parameter_values,
    solver=pybamm.CasadiSolver()
)
solution = sim.solve()

print("Simulação PyBaMM concluída com sucesso.")

# ==============================================================================
# 3. EXTRAÇÃO DOS RESULTADOS FÍSICOS (SOH e IMPEDÂNCIA)
# ==============================================================================

# 1. Extrair Capacidade e Resistência
capacity_ah = solution["Discharge capacity [A.h]"].entries

# Extração dos termos de resistência parciais (para contornar o último KeyError)
R_neg_ohm_m2 = solution["X-averaged negative electrode resistance [Ohm.m2]"].entries
R_pos_ohm_m2 = solution["X-averaged positive electrode resistance [Ohm.m2]"].entries

# Cálculo da resistência interna total (R_int = (R_neg + R_pos) / Area)
R_int_ohm = (R_neg_ohm_m2 + R_pos_ohm_m2) / CELL_AREA_M2

# 2. Amostragem dos pontos finais de ciclo
CYCLE_DURATION_H = 24
TOLERANCE = 0.01

time_entries = solution["Time [h]"].entries

# Filtra os índices onde o tempo é um múltiplo de 24 horas (fim do ciclo)
cycle_indices = np.where(
    np.abs(time_entries - np.round(time_entries / CYCLE_DURATION_H) * CYCLE_DURATION_H) < TOLERANCE
)[0]

cycle_indices = cycle_indices[cycle_indices > 0]
cycle_indices = np.unique(cycle_indices)

# Fallback: Se a amostragem por tolerância falhar, usa a amostragem por passo
if len(cycle_indices) == 0 or len(cycle_indices) < TOTAL_CYCLES / 2:
    try:
        # Encontra o índice correspondente ao tempo final do primeiro ciclo
        first_cycle_index = np.argmin(np.abs(time_entries - CYCLE_DURATION_H))
        if first_cycle_index > 0:
            num_steps_per_cycle = first_cycle_index
            cycle_indices = np.arange(num_steps_per_cycle, len(time_entries), num_steps_per_cycle)
    except Exception:
        cycle_indices = np.array([len(time_entries) - 1])  # Último ponto

time_years = time_entries[cycle_indices] / (365 * 24)

# Amostra os valores nos índices finais dos ciclos
R_int_sampled = R_int_ohm[cycle_indices]
capacity_sampled = capacity_ah[cycle_indices]

# A capacidade inicial é o primeiro valor válido da capacidade
initial_capacity_ah = capacity_sampled[0]

# 3. Criar DataFrame de Degradação
degradation_data = pd.DataFrame({
    'Time_Years': time_years,
    'SOH_Pct_PyBaMM': (capacity_sampled / initial_capacity_ah) * 100,
    'R_int_Ohm': R_int_sampled,
})

degradation_data = degradation_data.drop_duplicates(subset=['Time_Years'], keep='last').reset_index(drop=True)

# 4. Determinar a Vida Útil Técnica (T_life)
SOH_END_OF_LIFE = 70.0
T_life = degradation_data.loc[degradation_data['SOH_Pct_PyBaMM'] <= SOH_END_OF_LIFE, 'Time_Years'].min()

print(f"\n--- Resultado PyBaMM (SPM) ---")
print(f"Vida útil técnica (SoH < {SOH_END_OF_LIFE}%) é de: {T_life:.2f} anos." if not np.isnan(
    T_life) else f"AVISO: O SoH não atingiu {SOH_END_OF_LIFE}% em {time_years.max():.2f} anos.")

# 5. Plotagem da Curva de Degradação
plt.figure(figsize=(10, 5))
plt.plot(degradation_data['Time_Years'], degradation_data['SOH_Pct_PyBaMM'], label='SOH (%) (PyBaMM - SPM)',
         linewidth=2)
plt.axhline(SOH_END_OF_LIFE, color='red', linestyle='--', label=f'Fim de Vida ({SOH_END_OF_LIFE}%)')
plt.title('Curva de Degradação (SOH) - PyBaMM SPM')
plt.xlabel('Tempo (Anos)')
plt.ylabel('SOH (%)')
plt.legend()
plt.grid(True, linestyle=':', alpha=0.6)
plt.show()

degradation_data.to_csv("pybamm_degradation_output.csv", index=False)
print("\nCurva de degradação salva em 'pybamm_degradation_output.csv' para recalcular o LCOE.")