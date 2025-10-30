import pandas as pd
import numpy as np
import os

# ==============================================================================
# 1. FIXED INPUT PARAMETERS (ECONOMIC & TECHNICAL)
# ==============================================================================

# Economic Parameters (from your base calculation)
PROJECT_LIFETIME_YEARS = 10
DISCOUNT_RATE = 0.08  # Real Discount Rate
INFLATION_RATE = 0.02  # Annual Inflation Rate
NOMINAL_DISCOUNT_RATE = (1 + DISCOUNT_RATE) * (1 + INFLATION_RATE) - 1
YEARS = np.arange(1, PROJECT_LIFETIME_YEARS + 1)  # Calculation years (1 to 10)

# System Parameters
NOMINAL_CAPACITY_KWH = 38.8
INITIAL_SOH_PCT_FRACTION = 0.80  # Initial SoH (80%)

# Operational and O&M Costs
FIXED_OM_DOLLAR_PER_KWH_YEAR = 15  # Fixed O&M Cost ($/kWh/year)
VARIABLE_OM_DOLLAR_PER_MWH = 5  # Variable O&M Cost ($/MWh/MWh_out)
ROUND_TRIP_EFFICIENCY = 0.90
DAILY_CYCLES = 1

# ==============================================================================
# 2. LOAD DEGRADATION DATA AND PRE-CALCULATIONS
# ==============================================================================

FILE_PATH = "pybamm_degradation_output.csv"

if not os.path.exists(FILE_PATH):
    print(f"ERROR: Degradation file not found at {FILE_PATH}.")
    print("Please ensure the 'pybamm_degradation_output.csv' is in the same folder.")
    exit()

df_degradation = pd.read_csv(FILE_PATH)
time_points = df_degradation['Time_Years'].values
soh_points_pct = df_degradation['SOH_Pct_PyBaMM'].values

# Calculate Annual SOH Fraction
annual_soh_pct_of_initial = np.interp(YEARS, time_points, soh_points_pct) / 100.0
annual_soh_fraction = annual_soh_pct_of_initial * INITIAL_SOH_PCT_FRACTION

# Calculate Annual Energy Delivered (E_t)
ANNUAL_ENERGY_KWH = (
        NOMINAL_CAPACITY_KWH * annual_soh_fraction * DAILY_CYCLES * 365 * ROUND_TRIP_EFFICIENCY
)

# Calculate NPV of Energy (Denominator: NPV(E))
ENERGY_DELIVERED_NPV = np.sum(ANNUAL_ENERGY_KWH / (1 + NOMINAL_DISCOUNT_RATE) ** YEARS)

# Calculate NPV of OPEX (Part of Numerator: NPV(O&M))
OM_FIXED_ANNUAL = NOMINAL_CAPACITY_KWH * FIXED_OM_DOLLAR_PER_KWH_YEAR
OM_VARIABLE_ANNUAL = ANNUAL_ENERGY_KWH / 1000 * VARIABLE_OM_DOLLAR_PER_MWH
OPEX_TOTAL_ANNUAL = OM_FIXED_ANNUAL + OM_VARIABLE_ANNUAL
NPV_OPEX = np.sum(OPEX_TOTAL_ANNUAL / (1 + NOMINAL_DISCOUNT_RATE) ** YEARS)

# ==============================================================================
# 3. SENSITIVITY ANALYSIS SCENARIOS
# ==============================================================================

# Define the CAPEX scenarios (Capital Expenditure per kWh, $/kWh)
CAPEX_SCENARIOS = {
    "Pessimistic (+10% CAPEX)": 550,
    "Base Case (Original)": 500,
    "Optimistic (-10% CAPEX)": 450,
}

results = {}

print("\n" + "=" * 70)
print("              LCOE SENSITIVITY ANALYSIS (Varying CAPEX)")
print("=" * 70)
print(f"Discount Rate (Nominal): {NOMINAL_DISCOUNT_RATE:.4f}")
print(f"NPV of Total Energy Delivered: {ENERGY_DELIVERED_NPV:,.0f} kWh")
print(f"NPV of OPEX: ${NPV_OPEX:,.0f}")
print("-" * 70)

# Run LCOE calculation for each scenario
for scenario, capex_per_kwh in CAPEX_SCENARIOS.items():
    # Calculate Total CAPEX (I_0)
    CAPEX_TOTAL = NOMINAL_CAPACITY_KWH * capex_per_kwh

    # Calculate Total Costs NPV (Numerator: I_0 + NPV(O&M))
    TOTAL_COSTS_NPV = CAPEX_TOTAL + NPV_OPEX

    # Calculate LCOE
    LCOE = TOTAL_COSTS_NPV / ENERGY_DELIVERED_NPV

    results[scenario] = {"CAPEX_per_kWh": capex_per_kwh, "LCOE": LCOE}

    # Print results
    print(f"| {scenario:<25} | CAPEX/kWh: ${capex_per_kwh:<5} | LCOE: ${LCOE:.4f} / kWh |")

print("=" * 70)

# ==============================================================================
# 4. SUMMARY AND CONCLUSION
# ==============================================================================

lcoe_base = results["Base Case (Original)"]["LCOE"]
lcoe_pessimistic = results["Pessimistic (+10% CAPEX)"]["LCOE"]
lcoe_optimistic = results["Optimistic (-10% CAPEX)"]["LCOE"]

print("\n### Sensitivity Impact:")
print(f"* Base LCOE: ${lcoe_base:.4f} / kWh")
print(
    f"* 10% Increase in CAPEX (to $550/kWh) results in an LCOE increase of: ${(lcoe_pessimistic - lcoe_base):.4f} / kWh.")
print(
    f"* 10% Decrease in CAPEX (to $450/kWh) results in an LCOE decrease of: ${(lcoe_base - lcoe_optimistic):.4f} / kWh.")

print("\nWould you like to review these results or proceed to the final project documentation (Executive Summary)?")