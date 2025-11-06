import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
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
# 1. MODEL INPUT DATA
# ==============================================================================

# Time vector for a typical day
HOURS = np.arange(24)

# 1.1. Commercial Consumer Demand Profile (Based on typical load curve)
# kW values for 24 hours (example data, replace with your actual data if different)
DEMAND_PROFILE_KW = np.array([
    1.5, 1.4, 1.3, 1.2, 1.2, 1.5, 2.5, 4.0, 5.0, 5.5, 6.0, 6.5,
    6.2, 5.8, 5.0, 4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.8, 1.6, 1.5
])

# 1.2. Battery Operation Parameters (Based on the low-stress strategy)
# Nominal capacity and SOH limits
NOMINAL_CAPACITY_KWH = 38.8
SOH_EoL = 0.70  # End-of-Life SOH (used for visualization of limits)
SOH_SoL = 0.80  # Start-of-Life SOH
MAX_DOD = 0.25  # Maximum Depth-of-Discharge (DoD) constraint
MIN_SOC = SOH_SoL * 100 - MAX_DOD * 100  # Approx. 75% for 80% SOH

# Example data for typical operation (based on one day simulation)
# State of Charge (SoC) - Example data for visualization (80% to 75% swing)
SOC_PROFILE = np.array([
    80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 78.0, 76.0, 75.0, 75.0, 75.0, 75.0,
    76.0, 77.0, 78.0, 79.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0
])

# Power (kW) - Example data for charge/discharge (negative is discharge to load)
POWER_PROFILE_KW = np.array([
    0.0, 0.0, 0.0, 0.0, 0.0, -1.0, -1.5, -2.0, 0.0, 0.0, 0.0, 0.0,
    1.0, 1.5, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
])

# 1.3. Degradation Curve Parameters (Simplified linear model for 10 years)
PROJECT_LIFETIME_YEARS = 25
NOMINAL_CYCLE_YEARS = 10
YEARS_VECTOR = np.arange(1, PROJECT_LIFETIME_YEARS + 1)

# Linear decay from 100% (or 80% relative SOH) to 87.5% relative SOH in 10 years
# We use SOH_SoL (0.8) as the start, and SOH_EoL (0.7) as the end of project life.
# The relative SOH loss over the nominal 10-year cycle is 12.5% (100% to 87.5% relative).
RELATIVE_SOH_DECAY_NOMINAL = []
for y in YEARS_VECTOR:
    # Cycle year 1 to 10. Repeat for 2nd and 3rd cycle (replacements at 10 and 20 years)
    y_c = (y - 1) % NOMINAL_CYCLE_YEARS

    # Degradation: 1.0 - (Total loss * cycle year / cycle length)
    relative_soh_y = 1.0 - ((1.0 - 0.875) * (y_c + 1) / NOMINAL_CYCLE_YEARS)

    RELATIVE_SOH_DECAY_NOMINAL.append(relative_soh_y)

RELATIVE_SOH_FRACTION = np.array(RELATIVE_SOH_DECAY_NOMINAL)
RELATIVE_SOH_FRACTION = np.maximum(RELATIVE_SOH_FRACTION, 0.875)  # Limit SOH fraction
# Note: In the MC code, this is adjusted by the Degradation_Factor. Here, we plot only the nominal.

# ==============================================================================
# 2. CHART 1 GENERATION: Demand Profile (Figure 1)
# ==============================================================================

# **ALTERAÇÃO 1: Nome do arquivo de saída alterado para Chart_vf_1...**
figure_name_demand = 'Chart_vf_1_Demand_Profile'

plt.figure(figsize=(10, 6))
plt.plot(HOURS, DEMAND_PROFILE_KW, marker='o', linestyle='-', color='#006000', linewidth=2, markersize=5)
plt.fill_between(HOURS, DEMAND_PROFILE_KW, color='#006000', alpha=0.1)

# **ALTERAÇÃO 2: Título do gráfico alterado para "Chart 1 – ..."**
plt.title('Chart 1 – Typical Hourly Demand Profile of the Commercial Consumer', fontsize=14)
plt.xlabel('Hour of Day', fontsize=12)
plt.ylabel('Power Demand (kW)', fontsize=12)
plt.xticks(HOURS[::2])
plt.grid(True, linestyle=':', alpha=0.6)
plt.tight_layout()

# GERAR ARQUIVOS .EPS e .PNG
plt.savefig(f'{figure_name_demand}.eps', format='eps')
plt.savefig(f'{figure_name_demand}.png', format='png', dpi=1000)
plt.close()

# ==============================================================================
# 3. CHART 2 GENERATION: Operation Profile (SoC and Power) (Figure 3)
# ==============================================================================

# **ALTERAÇÃO 3: Nome do arquivo de saída alterado para Chart_vf_3...**
figure_name_operation = 'Chart_vf_3_Operation_Profile'

fig, ax1 = plt.subplots(figsize=(10, 6))

# Plot 1: Power (Charge/Discharge)
color = '#006000'
ax1.set_xlabel('Hour of Day', fontsize=12)
ax1.set_ylabel('Power (kW) - Discharge Negative', color=color, fontsize=12)
ax1.bar(HOURS, POWER_PROFILE_KW, color=color, alpha=0.7)
ax1.tick_params(axis='y', labelcolor=color)
ax1.axhline(0, color='black', linestyle='--', linewidth=0.8)  # Zero power line

# Plot 2: State of Charge (SoC)
ax2 = ax1.twinx()
color = '#600000'
ax2.set_ylabel('State of Charge (SoC) [%]', color=color, fontsize=12)
ax2.plot(HOURS, SOC_PROFILE, color=color, linestyle='-', marker='o', linewidth=2, markersize=4, label='SoC Profile')
ax2.tick_params(axis='y', labelcolor=color)

# Add operational limits
ax2.axhline(SOH_SoL * 100, color='gray', linestyle=':', linewidth=1.5, label='Initial SoH (80%)')
ax2.axhline(MIN_SOC, color='red', linestyle='--', linewidth=1.5, label=f'DoD Limit ({MAX_DOD * 100:.0f}%)')

ax2.set_ylim(MIN_SOC - 2, SOH_SoL * 100 + 2)
ax1.set_xticks(HOURS[::2])
# **ALTERAÇÃO 4: Título do gráfico alterado para "Chart 3 – ..."**
ax1.set_title('Chart 3 – Typical Hourly Operation Profile (SoC and Power)', fontsize=14)
fig.tight_layout()

# GERAR ARQUIVOS .EPS e .PNG
plt.savefig(f'{figure_name_operation}.eps', format='eps')
plt.savefig(f'{figure_name_operation}.png', format='png', dpi=1000)
plt.close()

# ==============================================================================
# 4. CHART 3 GENERATION: SOH Degradation Curve (Figure 5 - Nominal)
# ==============================================================================
# This chart reflects the simplified linear degradation model used as the baseline for the MC risk analysis.

# **ALTERAÇÃO 5: Nome do arquivo de saída alterado para Chart_vf_4... (Usando o 4 conforme pedido)**
figure_name_soh = 'Chart_vf_4_Projected_SOH_Curve'

plt.figure(figsize=(10, 6))

# SOH in percentage (Relative SOH * SOH_SoL)
SOH_IN_PERCENTAGE = RELATIVE_SOH_FRACTION * SOH_SoL * 100
# SOH_EoL limit in percentage (70%)
SOH_EoL_PERCENT = SOH_EoL * 100

plt.plot(YEARS_VECTOR, SOH_IN_PERCENTAGE, marker='s', linestyle='-', color='darkblue', linewidth=2, markersize=5,
         label='Projected SOH (Nominal)')

# Replacement markers
for y_rep in [10, 20]:
    plt.axvline(y_rep, color='orange', linestyle='--', linewidth=1, alpha=0.7,
                label='Battery Replacement' if y_rep == 10 else None)

# EoL Limit
plt.axhline(SOH_EoL_PERCENT, color='red', linestyle='--', linewidth=2,
            label=f'Project End-of-Life Limit ({SOH_EoL_PERCENT:.0f}%)')

# **ALTERAÇÃO 6: Título do gráfico alterado para "Chart 4 – ..."**
plt.title('Chart 4 – Projected Curve of State of Health (SOH) Over Project Lifetime', fontsize=14)
plt.xlabel('Project Year', fontsize=12)
plt.ylabel('SOH [%]', fontsize=12)
plt.xticks(np.arange(0, PROJECT_LIFETIME_YEARS + 1, 5))
plt.ylim(SOH_EoL_PERCENT - 2, SOH_SoL * 100 + 2)
plt.legend(loc='lower left')
plt.grid(True, linestyle=':', alpha=0.6)
plt.tight_layout()

# GERAR ARQUIVOS .EPS e .PNG
plt.savefig(f'{figure_name_soh}.eps', format='eps')
plt.savefig(f'{figure_name_soh}.png', format='png', dpi=1000)
plt.close()

# ==============================================================================
# 5. CONSOLIDATION MESSAGE
# ==============================================================================

print("\n" + "=" * 80)
print("     METHODOLOGY CHARTS GENERATION COMPLETE (DEMAND, OPERATION, SOH)")
print("       (.eps and .png (1000 dpi) files generated for all 3 charts)")
print("=" * 80)
# Os nomes de arquivo na mensagem de consolidação foram atualizados.
print(f"CHART 1 (Demand) files generated as: {figure_name_demand}.*")
print(f"CHART 3 (Operation) files generated as: {figure_name_operation}.*")
print(f"CHART 4 (SOH) files generated as: {figure_name_soh}.*")