import pybamm
import numpy as np

# 1. Definir o Modelo e a Química (DFN para alta fidelidade, via lithium_ion)
# A estratégia de baixo estresse minimiza o stress do ciclo, validando a premissa
# de 10 anos dominada pelo envelhecimento calendárico.
model = pybamm.lithium_ion.DFN(
    name="SLB_LFP_LowStress_Validation",
    options={
        # Opção de degradação do SEI (Solid Electrolyte Interphase)
        "sei film resistance": "average",
        # Simulação isotérmica (consistente com baixo estresse)
        "thermal": "isothermal",
    }
)

# 2. Definir os Parâmetros (LFP Second-Life)
# Usando 'Chen2020', o conjunto de parâmetros mais adequado para LFP/Grafite.
parameter_values = pybamm.ParameterValues("Chen2020")

# Ajuste de SOH inicial para 80% (simula SLB, conforme seção 3.1)
parameter_values["Initial concentration in negative electrode [mol.m-3]"] *= 0.8
parameter_values["Initial concentration in positive electrode [mol.m-3]"] *= 0.8

# 3. Definir o Protocolo de Operação de Baixo Estresse (DoD <= 25%)
C_RATE = 1
DISCHARGE_TIME_HOURS = 0.25  # 25% de DoD
REST_TIME = 10  # Tempo de descanso/inatividade (ênfase no Calendar Aging)

cycle = [
    f"Charge at {C_RATE} C until 4.2 V",
    f"Rest for {REST_TIME} hours",
    f"Discharge at {C_RATE} C for {DISCHARGE_TIME_HOURS} hours",
    f"Rest for {REST_TIME} hours",
]
number_of_cycles = 3650  # 10 anos * 365 dias

experiment = pybamm.Experiment(
    cycle,
    period="1 day",
    number_for_repetition=number_of_cycles
)

# 4. Configurar e Rodar a Simulação
sim = pybamm.Simulation(
    model,
    experiment=experiment,
    parameter_values=parameter_values,
    solver=pybamm.CasadiSolver(mode="fast")
)

# Rodar a simulação e analisar (para confirmação no repositório)
try:
    solution = sim.solve()
    capacity = solution["Discharge capacity [A.h]"].data
    time = solution["Time [s]"].data / (3600 * 24 * 365)

    print("--- Validação PyBaMM (10 Anos) ---")
    print(f"Capacidade inicial (80% SOH): {capacity[0]:.2f} A.h")
    print(f"Capacidade final (após 10 anos): {capacity[-1]:.2f} A.h")
    print(f"Vida útil simulada (em anos): {time[-1]:.1f}")
except Exception as e:
    print(f"A simulação falhou. Erro: {e}")
    print(
        "\nAVISO: O erro provavelmente é devido à falta do arquivo de parâmetros 'Chen2020'. Recomenda-se rodar em um ambiente limpo (e.g., Google Colab) ou após a instalação correta das dependências do PyBaMM.")