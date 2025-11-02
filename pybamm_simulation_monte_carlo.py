import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# ==============================================================================
# 1. PREMISSAS DO MODELO (Inputs Fixo - Alinhado com o Artigo)
# ==============================================================================

PROJECT_LIFETIME_YEARS = 25
NOMINAL_CAPACITY_KWH = 38.8
N_ITERATIONS = 10000

# CORRIGIDO: Removido o COMPENSATION_FACTOR.
# Usa o valor CAPEX base (Cenário Otimista) do artigo.
BASE_CAPEX_PER_KWH = 200.00  # USD/kWh (Valor do Cenário Otimista)
BASE_DISCOUNT_RATE = 0.08  # Taxa de Desconto Real (8%)
OPEX_PERCENTAGE = 0.02  # 2% do CAPEX inicial
COST_REDUCTION_RATE = 0.00  # 0% (Conforme simplificação)

REPLACEMENT_YEARS = [10, 20]
YEARS = np.arange(1, PROJECT_LIFETIME_YEARS + 1)

# ENERGIA ANUAL CORRETA (5.82 kWh/dia * 365 dias)
# Este é o valor base de energia (já com SoH inicial de 80%)
BASE_ANNUAL_ENERGY = 5.82 * 365  # ≈ 2124.3 kWh/ano

# Definição da curva de degradação relativa (80% para 70% em 10 anos)
# Relativo ao SoH inicial (1.0 = 80%, 0.875 = 70%)
RELATIVE_SOH_CURVE = []
for y in YEARS:
    y_c = (y - 1) % 10  # Ciclo de 10 anos
    # Decaimento linear de 1.0 (Ano 0) para 0.875 (Ano 10)
    relative_soh_y = 1.0 - ((1.0 - 0.875) * (y_c + 1) / 10)
    RELATIVE_SOH_CURVE.append(relative_soh_y)

RELATIVE_SOH_FRACTION = np.array(RELATIVE_SOH_CURVE)
# Garante que a energia não exceda o limite inferior (0.875)
RELATIVE_SOH_FRACTION = np.maximum(RELATIVE_SOH_FRACTION, 0.875)


# ==============================================================================
# 2. DEFINIÇÃO DE DISTRIBUIÇÕES PARA MONTE CARLO
# ==============================================================================

def get_lognormal_params(nominal_value, percent_std):
    """Calcula mu e sigma para uma distribuição log-normal (2-sigma range)."""
    # Assume que a variação percentual (e.g., 20%) cobre 2 desvios-padrão (2-sigma)
    std_dev_abs = nominal_value * (percent_std / 100) / 2
    mu = np.log(nominal_value / np.sqrt(1 + (std_dev_abs / nominal_value) ** 2))
    sigma = np.sqrt(np.log(1 + (std_dev_abs / nominal_value) ** 2))
    return mu, sigma


# Amostragem das variáveis de incerteza (±20% para CAPEX e Discount Rate)
CAPEX_MU, CAPEX_SIGMA = get_lognormal_params(BASE_CAPEX_PER_KWH, 20)
CAPEX_SAMPLES = np.random.lognormal(CAPEX_MU, CAPEX_SIGMA, N_ITERATIONS)

DISCOUNT_STD_DEV = BASE_DISCOUNT_RATE * 0.20 / 2
DISCOUNT_SAMPLES = np.random.normal(BASE_DISCOUNT_RATE, DISCOUNT_STD_DEV, N_ITERATIONS)
DISCOUNT_SAMPLES = np.maximum(DISCOUNT_SAMPLES, 0.01)  # Limite inferior de 1%

# OPEX (±50% conforme o artigo)
OPEX_STD_DEV = OPEX_PERCENTAGE * 0.50 / 2
OPEX_SAMPLES = np.random.normal(OPEX_PERCENTAGE, OPEX_STD_DEV, N_ITERATIONS)
OPEX_SAMPLES = np.maximum(OPEX_SAMPLES, 0.005)  # Limite inferior de 0.5%

# Fator de Degradação (±20% na taxa, ou seja, no SoH relativo)
DEGRADATION_STD_DEV = 0.20 / 2
DEGRADATION_FACTORS = np.random.normal(1.0, DEGRADATION_STD_DEV, N_ITERATIONS)
DEGRADATION_FACTORS = np.maximum(DEGRADATION_FACTORS, 0.8)  # Limita a variação

# ==============================================================================
# 3. SIMULAÇÃO MONTE CARLO (Cálculo do LCOE)
# ==============================================================================

lcoe_results = []

for i in range(N_ITERATIONS):

    capex_per_kwh = CAPEX_SAMPLES[i]
    discount_rate = DISCOUNT_SAMPLES[i]
    opex_percentage_sample = OPEX_SAMPLES[i]
    degradation_factor = DEGRADATION_FACTORS[i]

    # CÁLCULO DE VALOR PRESENTE (Utiliza a Taxa Real)
    # CORRIGIDO: Removeu a taxa nominal (INFLATION_RATE)
    DISCOUNT_FACTORS = 1.0 / (1 + discount_rate) ** YEARS

    # 3.1 ENERGIA ENTREGUE (DENOMINADOR)

    # Ajusta o SoH relativo com o fator de incerteza da degradação
    relative_soh_adjusted = RELATIVE_SOH_FRACTION * degradation_factor
    relative_soh_adjusted = np.minimum(relative_soh_adjusted, 1.0)  # Não pode exceder 100% (inicial)
    relative_soh_adjusted = np.maximum(relative_soh_adjusted, 0.875)  # Não pode exceder o SoH EoL

    ANNUAL_ENERGY_KWH = BASE_ANNUAL_ENERGY * relative_soh_adjusted
    ENERGY_DELIVERED_NPV = np.sum(ANNUAL_ENERGY_KWH * DISCOUNT_FACTORS)

    # 3.2 CUSTOS TOTAIS (NUMERADOR - LCC)

    CAPEX_INITIAL = NOMINAL_CAPACITY_KWH * capex_per_kwh

    # NPV_OPEX
    OM_ANNUAL = CAPEX_INITIAL * opex_percentage_sample
    NPV_OPEX = np.sum(OM_ANNUAL * DISCOUNT_FACTORS)

    # NPV_REPLACEMENTS (Utiliza a simplificação de custo de reposição ≈ CAPEX inicial)
    NPV_REPLACEMENTS = 0
    for y_rep in REPLACEMENT_YEARS:
        # Assumindo que o custo de reposição acompanha o CAPEX inicial amostrado (sem redução de custo)
        COST_AT_REPLACEMENT = CAPEX_INITIAL * (1 - COST_REDUCTION_RATE) ** y_rep
        NPV_REPLACEMENTS += COST_AT_REPLACEMENT / (1 + discount_rate) ** y_rep

    TOTAL_COSTS_NPV = CAPEX_INITIAL + NPV_REPLACEMENTS + NPV_OPEX

    # 3.3 LCOE
    if ENERGY_DELIVERED_NPV > 0:
        LCOE_STORAGE = TOTAL_COSTS_NPV / ENERGY_DELIVERED_NPV
        lcoe_results.append(LCOE_STORAGE)

lcoe_results = np.array(lcoe_results)

# ==============================================================================
# 4. ANÁLISE DE RESULTADOS E P90 CAPEX THRESHOLD (Utiliza a Lógica Inversa)
# ==============================================================================

LCOE_MEAN = np.mean(lcoe_results)
LCOE_P10 = np.percentile(lcoe_results, 10)
LCOE_P50 = np.percentile(lcoe_results, 50)
LCOE_P90 = np.percentile(lcoe_results, 90)  # Target: 0.4091 USD/kWh

# CÁLCULO INVERSO DO CAPEX P90 (Conceitualmente alinhado com o artigo)
# Usa os valores médios (base) para o denominador (energia e fatores de custo)
# para garantir que o resultado seja estável e não dependa do P90 da energia.

DISCOUNT_FACTORS_BASE = 1.0 / (1 + BASE_DISCOUNT_RATE) ** YEARS
ANNUAL_ENERGY_KWH_BASE = BASE_ANNUAL_ENERGY * RELATIVE_SOH_FRACTION
ENERGY_DELIVERED_NPV_BASE = np.sum(ANNUAL_ENERGY_KWH_BASE * DISCOUNT_FACTORS_BASE)

FACTOR_OPEX_NPV = np.sum(OPEX_PERCENTAGE * DISCOUNT_FACTORS_BASE)

FACTOR_REPL_NPV = 0
for y_rep in REPLACEMENT_YEARS:
    FACTOR_REPL_NPV += (1 - COST_REDUCTION_RATE) ** y_rep / (1 + BASE_DISCOUNT_RATE) ** y_rep

# Fator que multiplica o CAPEX/kWh para dar o LCC/kWh
LCC_CAPEX_FACTOR = 1 + FACTOR_OPEX_NPV + FACTOR_REPL_NPV

# LCC P90 = LCOE P90 * EVP Base
LCC_P90 = LCOE_P90 * ENERGY_DELIVERED_NPV_BASE

# CAPEX Inicial P90 = LCC P90 / Fatores de Custo (que multiplicam o CAPEX Inicial)
CAPEX_INITIAL_P90 = LCC_P90 / LCC_CAPEX_FACTOR
CAPEX_PER_KWH_P90 = CAPEX_INITIAL_P90 / NOMINAL_CAPACITY_KWH  # Target: 111.10 USD/kWh

# ==============================================================================
# 5. SAÍDA FINAL
# ==============================================================================

print("\n" + "=" * 70)
print("  MONTE CARLO RISK MODELING (LCC - 25 Years) - ALINHAMENTO FINAL")
print("=" * 70)

results_data = {
    "Métrica": [
        "LCOE Mean (Média)",
        "LCOE P50 (Mediana)",
        "LCOE P90 (Risco Econômico)"
    ],
    "Valor": [
        f"${LCOE_MEAN:.4f} / kWh",
        f"${LCOE_P50:.4f} / kWh",
        f"${LCOE_P90:.4f} / kWh"
    ]
}
df_lcoe = pd.DataFrame(results_data)
print(df_lcoe.to_string(index=False))

print("-" * 70)
print(f"P90 LCOE Target (Artigo) ........: $0.4091 / kWh")
print(f"P90 Max CAPEX Total (Initial) ...: ${CAPEX_INITIAL_P90:,.2f}")
print(f"P90 Max CAPEX/kWh (Artigo) ......: ${CAPEX_PER_KWH_P90:.2f} / kWh")
print("-" * 70)

# Geração do Gráfico (Figure 5)
plt.figure(figsize=(10, 6))
plt.hist(lcoe_results, bins=50, density=True, alpha=0.7, color='skyblue', edgecolor='black')

plt.axvline(LCOE_P90, color='red', linestyle='--', linewidth=2, label=f'P90 Threshold (${LCOE_P90:.4f})')
# O limite de competitividade é o valor determinístico do Cenário Base (~0.45)
plt.axvline(0.45, color='green', linestyle=':', linewidth=2, label='Limite de Competitividade (~$0.45)')

plt.title('Probability Density Function (PDF) of LCOE (Monte Carlo)')
plt.xlabel('LCOE ($/kWh)')
plt.ylabel('Probability Density')
plt.legend()
plt.grid(True, linestyle=':', alpha=0.6)
plt.show()