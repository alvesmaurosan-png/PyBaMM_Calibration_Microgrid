import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import spearmanr
import matplotlib

# ==============================================================================
# ENVIRONMENT CONFIGURATION AND EPS CORRECTION
# ==============================================================================
# CRITICAL CORRECTION: Forces Matplotlib to use Type 42 fonts for EPS (TrueType).
matplotlib.rcParams['ps.fonttype'] = 42
plt.style.use('ggplot')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 12

# ==============================================================================
# 1. MODEL PREMISES
# ==============================================================================

PROJECT_LIFETIME_YEARS = 25
NOMINAL_CAPACITY_KWH = 38.8
N_ITERATIONS = 10000

BASE_CAPEX_PER_KWH = 200.00  # USD/kWh
BASE_DISCOUNT_RATE = 0.08
OPEX_PERCENTAGE = 0.02
COST_REDUCTION_RATE = 0.00  # Non-stochastic in MC

REPLACEMENT_YEARS = [10, 20]
YEARS = np.arange(1, PROJECT_LIFETIME_YEARS + 1)

BASE_ANNUAL_ENERGY = 5.82 * 365  # kWh/year (5.82 kWh/day * 365 days)

# Nominal SOH curve (Simplified linear decay from 100% to 87.5% over 10 years, repeated)
RELATIVE_SOH_CURVE = []
for y in YEARS:
    y_c = (y - 1) % 10
    # Calculates the SOH fraction: 1.0 - (Total Loss * Cycle Year / Total Cycle Years)
    relative_soh_y = 1.0 - ((1.0 - 0.875) * (y_c + 1) / 10)
    RELATIVE_SOH_CURVE.append(relative_soh_y)

RELATIVE_SOH_FRACTION = np.array(RELATIVE_SOH_CURVE)
# Ensures SOH does not fall below the end-of-life limit (87.5% in this simplified curve)
RELATIVE_SOH_FRACTION = np.maximum(RELATIVE_SOH_FRACTION, 0.875)


# ==============================================================================
# 2. MONTE CARLO DISTRIBUTION DEFINITION
# ==============================================================================

def get_lognormal_params(nominal_value, percent_std):
    """Calculates mu and sigma for a log-normal distribution (2-sigma range)."""
    # std_dev_abs corresponds to half the 2-sigma range (e.g., 20% of nominal)
    std_dev_abs = nominal_value * (percent_std / 100) / 2
    mu = np.log(nominal_value / np.sqrt(1 + (std_dev_abs / nominal_value) ** 2))
    sigma = np.sqrt(np.log(1 + (std_dev_abs / nominal_value) ** 2))
    return mu, sigma


# Sampling (CAPEX) - Lognormal
CAPEX_PER_KWH_MU, CAPEX_PER_KWH_SIGMA = get_lognormal_params(BASE_CAPEX_PER_KWH, 20)
CAPEX_PER_KWH_SAMPLES = np.random.lognormal(CAPEX_PER_KWH_MU, CAPEX_PER_KWH_SIGMA, N_ITERATIONS)
CAPEX_INITIAL_SAMPLES = CAPEX_PER_KWH_SAMPLES * NOMINAL_CAPACITY_KWH

# Sampling (Discount Rate) - Normal
DISCOUNT_STD_DEV = BASE_DISCOUNT_RATE * 0.20 / 2
DISCOUNT_SAMPLES = np.random.normal(BASE_DISCOUNT_RATE, DISCOUNT_STD_DEV, N_ITERATIONS)
DISCOUNT_SAMPLES = np.maximum(DISCOUNT_SAMPLES, 0.01)  # Minimum 1%

# Sampling (OPEX) - Normal
OPEX_STD_DEV = OPEX_PERCENTAGE * 0.50 / 2
OPEX_SAMPLES = np.random.normal(OPEX_PERCENTAGE, OPEX_STD_DEV, N_ITERATIONS)
OPEX_SAMPLES = np.maximum(OPEX_SAMPLES, 0.005)  # Minimum 0.5%

# Sampling (Degradation Factor) - Normal
DEGRADATION_STD_DEV = 0.20 / 2
# Factor: 1.0 is nominal. >1.0 means worse degradation (faster), <1.0 means better (slower).
DEGRADATION_FACTORS = np.random.normal(1.0, DEGRADATION_STD_DEV, N_ITERATIONS)
DEGRADATION_FACTORS = np.maximum(DEGRADATION_FACTORS, 0.8)  # Limits variation to 80% of nominal rate

# ==============================================================================
# 3. MONTE CARLO SIMULATION (LCOE Calculation)
# ==============================================================================

# DataFrame to store input samples and LCOE results for GSA
df_mc_results = pd.DataFrame({
    'CAPEX_Total_Initial': CAPEX_INITIAL_SAMPLES,
    'Discount_Rate': DISCOUNT_SAMPLES,
    'OPEX_Percentage': OPEX_SAMPLES,
    'Degradation_Factor': DEGRADATION_FACTORS,
    'LCOE_USD_per_kWh': np.nan
})

# LCOE Calculation Loop
for i in range(N_ITERATIONS):
    capex_initial = CAPEX_INITIAL_SAMPLES[i]
    discount_rate = DISCOUNT_SAMPLES[i]
    opex_percentage_sample = OPEX_SAMPLES[i]
    degradation_factor = DEGRADATION_FACTORS[i]

    DISCOUNT_FACTORS = 1.0 / (1 + discount_rate) ** YEARS

    # Apply degradation factor to the nominal SOH curve
    relative_soh_adjusted = RELATIVE_SOH_FRACTION * degradation_factor
    relative_soh_adjusted = np.minimum(relative_soh_adjusted, 1.0)
    relative_soh_adjusted = np.maximum(relative_soh_adjusted, 0.875)

    ANNUAL_ENERGY_KWH = BASE_ANNUAL_ENERGY * relative_soh_adjusted
    ENERGY_DELIVERED_NPV = np.sum(ANNUAL_ENERGY_KWH * DISCOUNT_FACTORS)

    OM_ANNUAL = capex_initial * opex_percentage_sample
    NPV_OPEX = np.sum(OM_ANNUAL * DISCOUNT_FACTORS)

    NPV_REPLACEMENTS = 0
    for y_rep in REPLACEMENT_YEARS:
        COST_AT_REPLACEMENT = capex_initial * (1 - COST_REDUCTION_RATE) ** y_rep
        NPV_REPLACEMENTS += COST_AT_REPLACEMENT / (1 + discount_rate) ** y_rep

    TOTAL_COSTS_NPV = capex_initial + NPV_REPLACEMENTS + NPV_OPEX

    if ENERGY_DELIVERED_NPV > 0:
        LCOE_STORAGE = TOTAL_COSTS_NPV / ENERGY_DELIVERED_NPV
        df_mc_results.loc[i, 'LCOE_USD_per_kWh'] = LCOE_STORAGE

df_mc_results.dropna(subset=['LCOE_USD_per_kWh'], inplace=True)
lcoe_results = df_mc_results['LCOE_USD_per_kWh'].values

# ==============================================================================
# 4. STATISTICAL ANALYSIS (P90 and CAPEX Threshold)
# ==============================================================================

LCOE_P90 = np.percentile(lcoe_results, 90)
LCOE_MEAN = np.mean(lcoe_results)
LCOE_P50 = np.percentile(lcoe_results, 50)

# Calculation of CAPEX Threshold (Based on P90 LCOE)
DISCOUNT_FACTORS_BASE = 1.0 / (1 + BASE_DISCOUNT_RATE) ** YEARS
ANNUAL_ENERGY_KWH_BASE = BASE_ANNUAL_ENERGY * RELATIVE_SOH_FRACTION
ENERGY_DELIVERED_NPV_BASE = np.sum(ANNUAL_ENERGY_KWH_BASE * DISCOUNT_FACTORS_BASE)

FACTOR_OPEX_NPV = np.sum(OPEX_PERCENTAGE * DISCOUNT_FACTORS_BASE)
FACTOR_REPL_NPV = 0
for y_rep in REPLACEMENT_YEARS:
    FACTOR_REPL_NPV += (1 - COST_REDUCTION_RATE) ** y_rep / (1 + BASE_DISCOUNT_RATE) ** y_rep

LCC_CAPEX_FACTOR = 1 + FACTOR_OPEX_NPV + FACTOR_REPL_NPV
LCC_P90 = LCOE_P90 * ENERGY_DELIVERED_NPV_BASE
CAPEX_INITIAL_P90 = LCC_P90 / LCC_CAPEX_FACTOR
CAPEX_PER_KWH_P90 = CAPEX_INITIAL_P90 / NOMINAL_CAPACITY_KWH

# ==============================================================================
# 5. CHART 1 GENERATION: LCOE PDF (Figure 8) - GENERATE EPS & PNG 1000 DPI
# ==============================================================================

figure_name_pdf = 'Chart_vf_5_Monte_Carlo_LCOE_PDF' # Nome de arquivo ajustado

plt.figure(figsize=(10, 6))

plt.hist(lcoe_results, bins=50, density=True, alpha=0.7, color='skyblue', edgecolor='black')

# ALTERAÇÃO 1: Título do gráfico alterado (Chart 5)
plt.title(
    'Chart 5 – Probability Density Function (PDF) of LCOE \n (P90 Max CAPEX: 232,31 USD/kWh)',
    fontsize=14
)
plt.xlabel('LCOE ($/kWh)', fontsize=16)
plt.ylabel('Probability Density', fontsize=16)
plt.tick_params(axis='both', which='major', labelsize=12)

# Reference lines
plt.axvline(LCOE_P90, color='red', linestyle='--', linewidth=2, label=f'P90 Threshold (${LCOE_P90:.4f})')
plt.axvline(0.45, color='green', linestyle=':', linewidth=2, label='Competitiveness Limit (~$0.45/kWh)')

plt.legend(fontsize=13, loc='upper right')
plt.grid(True, linestyle=':', alpha=0.6)
plt.tight_layout()

# GENERATE .EPS FILE
plt.savefig(f'{figure_name_pdf}.eps', format='eps')
# GENERATE .PNG FILE HIGH RESOLUTION (1000 DPI)
plt.savefig(f'{figure_name_pdf}.png', format='png', dpi=1000)

plt.close()

# ==============================================================================
# 6. CHART 2 GENERATION: GSA - Tornado Chart (Figure 7) - GENERATE EPS & PNG 1000 DPI
# ==============================================================================

input_vars_gsa = [
    'CAPEX_Total_Initial',
    'Discount_Rate',
    'OPEX_Percentage',
    'Degradation_Factor',
]
output_var = 'LCOE_USD_per_kWh'
figure_name_gsa = 'Chart_vf_6_GSA_Spearman_Correlation' # Nome de arquivo ajustado

# 6.1 Spearman Correlation Calculation
correlation_results = {}
for var in input_vars_gsa:
    rho, p_value = spearmanr(df_mc_results[var], df_mc_results[output_var])
    correlation_results[var] = rho

df_gsa = pd.DataFrame(list(correlation_results.items()), columns=['Variable', 'Spearman_Coefficient'])

# Mapping for chart display names
variable_mapping = {
    'CAPEX_Total_Initial': 'CAPEX Initial Total (USD)',
    'Discount_Rate': 'Discount Rate (r)',
    'OPEX_Percentage': 'O&M Cost (% CAPEX)',
    'Degradation_Factor': 'Degradation Factor (SOH)',
}
df_gsa['Variable_Name'] = df_gsa['Variable'].map(variable_mapping)

# Sort by absolute value for Tornado Chart
df_gsa['Abs_Rho'] = df_gsa['Spearman_Coefficient'].abs()
df_gsa = df_gsa.sort_values(by='Abs_Rho', ascending=True)

# 6.2 Tornado Chart Generation

plt.figure(figsize=(10, 6))

bars = plt.barh(df_gsa['Variable_Name'], df_gsa['Spearman_Coefficient'],
                color=np.where(df_gsa['Spearman_Coefficient'] > 0, '#600000', '#006000'),
                alpha=0.8)

plt.xlabel(r'Spearman Correlation Coefficient ($\rho$)', fontsize=14)
# ALTERAÇÃO 2: Título do gráfico alterado (Chart 6)
plt.title(
    'Chart 6 – Global Sensitivity Analysis (GSA) – LCOE Risck Drivers',
    fontsize=16
)
plt.axvline(0, color='black', linestyle='-', linewidth=0.8)
plt.grid(axis='x', linestyle=':', alpha=0.6)

# Add rho values on the bars
for bar in bars:
    width = bar.get_width()
    x_pos = width
    ha = 'left' if width > 0 else 'right'
    text_offset = 0.01 * (1 if width > 0 else -1)

    plt.text(x_pos + text_offset, bar.get_y() + bar.get_height() / 2,
             f"{width:.3f}",
             va='center', ha=ha,
             color='black', fontsize=12)

plt.xlim(min(df_gsa['Spearman_Coefficient']) * 1.1, max(df_gsa['Spearman_Coefficient']) * 1.1)
plt.yticks(fontsize=12)
plt.xticks(fontsize=12)

plt.tight_layout()

# GENERATE .EPS FILE
plt.savefig(f'{figure_name_gsa}.eps', format='eps')
# GENERATE .PNG FILE HIGH RESOLUTION (1000 DPI)
plt.savefig(f'{figure_name_gsa}.png', format='png', dpi=1000)

plt.close()

# ==============================================================================
# 7. RESULTS CONSOLIDATION (For text insertion)
# ==============================================================================

print("\n" + "=" * 75)
print("             MONTE CARLO AND GSA CODE EXECUTION COMPLETE")
print("        (.eps and .png (1000 dpi) files generated for both charts)")
print("=" * 75)
print(">> KEY RESULTS FOR THE ARTICLE:")
print(f"LCOE P50 (Median)................: ${LCOE_P50:.4f}")
print(f"LCOE Mean........................: ${LCOE_MEAN:.4f}")
print(f"LCOE P90 (Risk Threshold)........: ${LCOE_P90:.4f}")
print(f"P90 Maximum Viable CAPEX.........: ${CAPEX_PER_KWH_P90:.2f} / kWh")
print("-" * 75)

print("\n>> GLOBAL SENSITIVITY ANALYSIS (GSA - Spearman Coefficients):")
print(
    df_gsa[['Variable_Name', 'Spearman_Coefficient']].sort_values(by='Spearman_Coefficient', ascending=False).to_string(
        index=False))
print("-" * 75)

print(f"LCOE PDF CHART (.eps and .png) GENERATED AS: {figure_name_pdf}.*")
print(f"GSA TORNADO CHART (.eps and .png) GENERATED AS: {figure_name_gsa}.*")