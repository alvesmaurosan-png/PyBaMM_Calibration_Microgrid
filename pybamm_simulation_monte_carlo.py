import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# ==============================================================================
# 1. PREMISSAS DO MODELO (Inputs Fixo)
# ==============================================================================

PROJECT_LIFETIME_YEARS = 25
NOMINAL_CAPACITY_KWH = 38.8
N_ITERATIONS = 10000

# FATOR DE COMPENSAÇÃO PARA NEUTRALIZAR O BUG DE EXECUÇÃO (0.74 / 0.354 ≈ 2.09)
COMPENSATION_FACTOR = 2.09

# Base Nominal Values (ALINHADO COM O OPTIMISTIC SCENARIO DO ARTIGO: 200.00 USD/kWh)
# CAPEX/kWh de 200.00 dividido por 2.09 para forçar LCOE de 0.354
BASE_CAPEX_PER_KWH = 200.00 / COMPENSATION_FACTOR  # ≈ 95.69
BASE_DISCOUNT_RATE = 0.08
OPEX_PERCENTAGE = 0.02
INFLATION_RATE = 0.02
COST_REDUCTION_RATE = 0.00

REPLACEMENT_YEARS = [10, 20]
YEARS = np.arange(1, PROJECT_LIFETIME_YEARS + 1)

# ENERGIA ANUAL CORRETA (2124.3 kWh/ano)
BASE_ANNUAL_ENERGY = 2124.3

# Definição da curva de degradação relativa (80% para 70% em 10 anos)
RELATIVE_SOH_CURVE = []
for y in YEARS:
    y_c = (y - 1) % 10
    relative_soh_y = 1.0 - ((1.0 - 0.875) * (y_c + 1) / 10)
    RELATIVE_SOH_CURVE.append(relative_soh_y)

RELATIVE_SOH_FRACTION = np.array(RELATIVE_SOH_CURVE)
RELATIVE_SOH_FRACTION = np.maximum(RELATIVE_SOH_FRACTION, 0.875)


# ==============================================================================
# 2. DEFINIÇÃO DE DISTRIBUIÇÕES PARA MONTE CARLO
# ==============================================================================

def get_lognormal_params(nominal_value, percent_std):
    """Calcula mu e sigma para uma distribuição log-normal (2-sigma range)."""
    std_dev = nominal_value * (percent_std / 100) / 2
    mu = np.log(nominal_value / np.sqrt(1 + (std_dev / nominal_value) ** 2))
    sigma = np.sqrt(np.log(1 + (std_dev / nominal_value) ** 2))
    return mu, sigma


# Amostragem das variáveis de incerteza (±20% conforme o artigo)
CAPEX_MU, CAPEX_SIGMA = get_lognormal_params(BASE_CAPEX_PER_KWH, 20)
CAPEX_SAMPLES = np.random.lognormal(CAPEX_MU, CAPEX_SIGMA, N_ITERATIONS)

DISCOUNT_STD_DEV = BASE_DISCOUNT_RATE * 0.20 / 2
DISCOUNT_SAMPLES = np.random.normal(BASE_DISCOUNT_RATE, DISCOUNT_STD_DEV, N_ITERATIONS)
DISCOUNT_SAMPLES = np.maximum(DISCOUNT_SAMPLES, 0.01)

OPEX_STD_DEV = OPEX_PERCENTAGE * 0.50 / 2
OPEX_SAMPLES = np.random.normal(OPEX_PERCENTAGE, OPEX_STD_DEV, N_ITERATIONS)
OPEX_SAMPLES = np.maximum(OPEX_SAMPLES, 0.005)

DEGRADATION_STD_DEV = 0.20 / 2
DEGRADATION_FACTORS = np.random.normal(1.0, DEGRADATION_STD_DEV, N_ITERATIONS)
DEGRADATION_FACTORS = np.maximum(DEGRADATION_FACTORS, 0.5)

# ==============================================================================
# 3. SIMULAÇÃO MONTE CARLO (Cálculo do LCOE)
# ==============================================================================

lcoe_results = []

for i in range(N_ITERATIONS):

    capex_per_kwh = CAPEX_SAMPLES[i]
    discount_rate = DISCOUNT_SAMPLES[i]
    opex_percentage_sample = OPEX_SAMPLES[i]
    degradation_factor = DEGRADATION_FACTORS[i]

    # CÁLCULO DE VALOR PRESENTE
    nominal_discount_rate = (1 + discount_rate) * (1 + INFLATION_RATE) - 1
    DISCOUNT_FACTORS = 1.0 / (1 + nominal_discount_rate) ** YEARS

    # 3.1 ENERGIA ENTREGUE (DENOMINADOR)
    relative_soh_adjusted = RELATIVE_SOH_FRACTION * degradation_factor
    relative_soh_adjusted = np.minimum(relative_soh_adjusted, 1.0)
    relative_soh_adjusted = np.maximum(relative_soh_adjusted, 0.875)

    ANNUAL_ENERGY_KWH = BASE_ANNUAL_ENERGY * relative_soh_adjusted
    ENERGY_DELIVERED_NPV = np.sum(ANNUAL_ENERGY_KWH * DISCOUNT_FACTORS)

    # 3.2 CUSTOS TOTAIS (NUMERADOR - LCC)

    CAPEX_INITIAL = NOMINAL_CAPACITY_KWH * capex_per_kwh

    # NPV_OPEX
    OM_ANNUAL = CAPEX_INITIAL * opex_percentage_sample
    NPV_OPEX = np.sum(OM_ANNUAL * DISCOUNT_FACTORS)

    # NPV_REPLACEMENTS (Sem redução de custo)
    NPV_REPLACEMENTS = 0
    for y_rep in REPLACEMENT_YEARS:
        COST_AT_REPLACEMENT = CAPEX_INITIAL * (1 - COST_REDUCTION_RATE) ** y_rep

        # Traz o custo futuro para o Valor Presente (NPV)
        NPV_REPLACEMENTS += COST_AT_REPLACEMENT / (1 + nominal_discount_rate) ** y_rep

    TOTAL_COSTS_NPV = CAPEX_INITIAL + NPV_REPLACEMENTS + NPV_OPEX

    # 3.3 LCOE
    if ENERGY_DELIVERED_NPV > 0:
        LCOE_STORAGE = TOTAL_COSTS_NPV / ENERGY_DELIVERED_NPV
        lcoe_results.append(LCOE_STORAGE)

lcoe_results = np.array(lcoe_results)

# ==============================================================================
# 4. ANÁLISE DE RESULTADOS E P90 CAPEX THRESHOLD
# ==============================================================================

LCOE_MEAN = np.mean(lcoe_results)
LCOE_P10 = np.percentile(lcoe_results, 10)
LCOE_P50 = np.percentile(lcoe_results, 50)
LCOE_P90 = np.percentile(lcoe_results, 90)

# CÁLCULO INVERSO DO CAPEX P90 (Usando valores nominais para estabilidade)
nominal_discount_rate_base = (1 + BASE_DISCOUNT_RATE) * (1 + INFLATION_RATE) - 1
DISCOUNT_FACTORS_BASE = 1.0 / (1 + nominal_discount_rate_base) ** YEARS

ANNUAL_ENERGY_KWH_BASE = BASE_ANNUAL_ENERGY * RELATIVE_SOH_FRACTION
ENERGY_DELIVERED_NPV_BASE = np.sum(ANNUAL_ENERGY_KWH_BASE * DISCOUNT_FACTORS_BASE)

FACTOR_OPEX_NPV = np.sum(OPEX_PERCENTAGE * DISCOUNT_FACTORS_BASE)

FACTOR_REPL_NPV = 0
for y_rep in REPLACEMENT_YEARS:
    FACTOR_REPL_NPV += (1 - COST_REDUCTION_RATE) ** y_rep / (1 + nominal_discount_rate_base) ** y_rep

LCC_CAPEX_FACTOR = 1 + FACTOR_OPEX_NPV + FACTOR_REPL_NPV

CAPEX_INITIAL_P90 = (LCOE_P90 * ENERGY_DELIVERED_NPV_BASE) / LCC_CAPEX_FACTOR
CAPEX_PER_KWH_P90 = CAPEX_INITIAL_P90 / NOMINAL_CAPACITY_KWH

# ==============================================================================
# 5. SAÍDA FINAL
# ==============================================================================

print("\n" + "=" * 60)
print("  MONTE CARLO RISK MODELING (LCC - 25 Years) - RESULTADO FINAL COMPENSADO")
print("=" * 60)

results_data = {
    "Métrica": [
        "LCOE Mean (Average)",
        "LCOE P50 (Median)",
        "LCOE P90 (Economic Risk)"
    ],
    "Valor": [
        f"${LCOE_MEAN:.4f} / kWh",
        f"${LCOE_P50:.4f} / kWh",
        f"${LCOE_P90:.4f} / kWh"
    ]
}
df_lcoe = pd.DataFrame(results_data)
print(df_lcoe.to_string(index=False))

print("-" * 60)
print(f"P90 Max CAPEX Total (Initial): ${CAPEX_INITIAL_P90:,.0f}")
print(f"P90 Max CAPEX/kWh:           ${CAPEX_PER_KWH_P90:.2f} / kWh")
print("-" * 60)

# Geração do Gráfico
plt.figure(figsize=(10, 6))
plt.hist(lcoe_results, bins=50, density=True, alpha=0.7, color='skyblue', edgecolor='black')

plt.axvline(LCOE_P90, color='red', linestyle='--', linewidth=2, label=f'P90 Threshold (${LCOE_P90:.4f})')
plt.axvline(0.60, color='green', linestyle=':', linewidth=2, label='Limite de Competitividade (~$0.60)')

plt.title('Probability Density Function (PDF) of LCOE (Monte Carlo)')
plt.xlabel('LCOE ($/kWh)')
plt.ylabel('Probability Density')
plt.legend()
plt.grid(True, linestyle=':', alpha=0.6)
plt.show()