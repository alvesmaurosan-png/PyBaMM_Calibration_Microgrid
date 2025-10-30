import pandas as pd
import numpy as np
import os

# ==============================================================================
# 1. INPUT PARAMETERS (ECONOMIC & TECHNICAL)
# ==============================================================================

# Economic Parameters
PROJECT_LIFETIME_YEARS = 10
DISCOUNT_RATE = 0.08  # Real Discount Rate (8%)
INFLATION_RATE = 0.02 # Assumed Annual Inflation Rate (2%)
NOMINAL_DISCOUNT_RATE = (1 + DISCOUNT_RATE) * (1 + INFLATION_RATE) - 1
YEARS = np.arange(1, PROJECT_LIFETIME_YEARS + 1) # Calculation years (1 to 10)

# System Parameters (Based on 38.8 kWh nominal capacity)
NOMINAL_CAPACITY_KWH = 38.8
INITIAL_SOH_PCT_FRACTION = 0.80 # CRITICAL: Initial SoH is 80% (0.80)

# Cost Parameters (Use your project data)
CAPEX_PER_KWH_DOLLAR = 500  # Capital Expenditure per kWh ($/kWh)
FIXED_OM_DOLLAR_PER_KWH_YEAR = 15  # Fixed O&M Cost ($/kWh/year)
VARIABLE_OM_DOLLAR_PER_MWH = 5    # Variable O&M Cost ($/MWh/MWh_out)

# Operational Parameters
ROUND_TRIP_EFFICIENCY = 0.90 # Battery round trip efficiency (90%)
DAILY_CYCLES = 1 # One full cycle per day (Charge-Discharge)

# ==============================================================================
# 2. LOAD DEGRADATION DATA AND SOH CALCULATION
# ==============================================================================

FILE_PATH = "pybamm_degradation_output.csv"

if not os.path.exists(FILE_PATH):
    print(f"ERROR: Degradation file not found at {FILE_PATH}.")
    print("Please ensure the 'pybamm_degradation_output.csv' is in the same folder.")
    exit()

df_degradation = pd.read_csv(FILE_PATH)

# The SOH_Pct_PyBaMM is the percentage relative to the *INITIAL* capacity (80% of nominal).
time_points = df_degradation['Time_Years'].values
soh_points_pct = df_degradation['SOH_Pct_PyBaMM'].values

# Interpolate the SOH Percentage for years 1 to 10
annual_soh_pct_of_initial = np.interp(
    YEARS,
    time_points,
    soh_points_pct
) / 100.0 # Convert percentage (e.g., 99.8%) to a fraction (0.998)

# Calculate the Actual SOH Fraction (relative to the system's NOMINAL capacity)
# Example Year 1: 0.998 * 0.80 = 0.7984 (i.e., 79.84% of nominal capacity)
annual_soh_fraction = annual_soh_pct_of_initial * INITIAL_SOH_PCT_FRACTION


# ==============================================================================
# 3. LCOE CALCULATION CORE
# ==============================================================================

# A. Capital Expenditure (CAPEX)
CAPEX_TOTAL = NOMINAL_CAPACITY_KWH * CAPEX_PER_KWH_DOLLAR

# B. Annual Energy Delivered (Generation)
# ANNUAL_ENERGY_KWH = Nominal Capacity * SoH_Annual * Cycles/day * Days/year * Efficiency
ANNUAL_ENERGY_KWH = (
    NOMINAL_CAPACITY_KWH * annual_soh_fraction * DAILY_CYCLES * 365 * ROUND_TRIP_EFFICIENCY
)

# C. Annual Costs (OPEX)
OM_FIXED_ANNUAL = NOMINAL_CAPACITY_KWH * FIXED_OM_DOLLAR_PER_KWH_YEAR
OM_VARIABLE_ANNUAL = ANNUAL_ENERGY_KWH / 1000 * VARIABLE_OM_DOLLAR_PER_MWH

# Total Annual Operating Cost
OPEX_TOTAL_ANNUAL = OM_FIXED_ANNUAL + OM_VARIABLE_ANNUAL

# D. Net Present Value (NPV) Calculation (LCOE Formula)

# 1. Total Costs NPV (Numerator)
cost_npv_opex = np.sum(OPEX_TOTAL_ANNUAL / (1 + NOMINAL_DISCOUNT_RATE)**YEARS)
TOTAL_COSTS_NPV = CAPEX_TOTAL + cost_npv_opex

# 2. Total Energy NPV (Denominator)
ENERGY_DELIVERED_NPV = np.sum(ANNUAL_ENERGY_KWH / (1 + NOMINAL_DISCOUNT_RATE)**YEARS)

# LCOE Calculation
LCOE_STORAGE = TOTAL_COSTS_NPV / ENERGY_DELIVERED_NPV

# ==============================================================================
# 4. RESULTS AND OUTPUT (WITH HIGH PRECISION FOR SOH VISIBILITY)
# ==============================================================================

print("\n" + "="*50)
print("             LEVELIZED COST OF ENERGY (LCOE)")
print("="*50)
print(f"Project Lifetime: {PROJECT_LIFETIME_YEARS} Years")
print(f"Nominal Discount Rate (i_nom): {NOMINAL_DISCOUNT_RATE:.4f}")
print("-" * 50)
print(f"Total CAPEX (Year 0): ${CAPEX_TOTAL:,.0f}")
print(f"NPV of OPEX: ${cost_npv_opex:,.0f}")
print(f"NPV of Total Costs (Numerator): ${TOTAL_COSTS_NPV:,.0f}")
print(f"NPV of Total Energy Delivered (Denominator): {ENERGY_DELIVERED_NPV:,.0f} kWh")
print("-" * 50)
print(f"LCOE of Storage: ${LCOE_STORAGE:.4f} / kWh")
print("="*50)

# Optional: Output the annual energy and SOH data for inspection
annual_data = pd.DataFrame({
    'Year': YEARS,
    # Increased precision to visually capture the subtle degradation
    'SOH_Fraction (of Nominal)': annual_soh_fraction.round(6),
    'SOH_Pct_of_Initial': (annual_soh_pct_of_initial * 100).round(4),
    'Annual_Energy_Delivered_kWh': ANNUAL_ENERGY_KWH.round(1),
    'Annual_OPEX_$': OPEX_TOTAL_ANNUAL.round(3),
})

# Display all rows and columns to prevent Pandas from truncating the output
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.float_format', lambda x: '%.6f' % x) # Ensure float display precision

print("\nAnnual Data Snapshot (Final and Detailed):")
print(annual_data)

# Revert Pandas display options (optional, good practice)
pd.reset_option('display.max_rows')
pd.reset_option('display.max_columns')
pd.reset_option('display.width')
pd.reset_option('display.float_format')

print("\nWould you like to proceed with the CAPEX Sensitivity Analysis now?")
