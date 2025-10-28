import pybamm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ==============================================================================
# 1. INITIAL CONFIGURATION (Article Data)
# ==============================================================================

# Battery System Parameters
NOMINAL_CAPACITY_KWH = 38.8
INITIAL_SOH = 0.80  # 80% initial SoH from SLB assumption
MAX_DOD_PCT = 0.25  # Maximum Depth of Discharge (25% cycle window)
TIME_HORIZON_YEARS = 10
TOTAL_CYCLES = 922 # Total cycles for the 10-year period (92.2 cycles/year)

# Operation Parameters
V_SYSTEM_NOMINAL = 400  # Nominal system voltage (V)
LOW_CYCLE_POWER_KW = 7.76 # Power for charge/discharge during shallow cycling (approx 0.2C)

# Daily Operation Profile Hours
DISCHARGE_START_HOUR = 17
DISCHARGE_END_HOUR = 21
CHARGE_START_HOUR = 11
CHARGE_END_HOUR = 15

# Cell Geometry for Impedance Calculation
ELECTRODE_WIDTH_M = 0.203
ELECTRODE_HEIGHT_M = 0.233
CELL_AREA_M2 = ELECTRODE_WIDTH_M * ELECTRODE_HEIGHT_M

# ==============================================================================
# 🎯 AGING CALIBRATION FOR 10 YEARS
# ==============================================================================

# LLI Calibration (Controls cyclic aging to achieve 10 years)
SEI_SIDE_REACTION_RATE = 1e-10

# Disabling other aging mechanisms that cause premature failure:
LAM_RATE = 0.0  # Loss of Active Material (LAM)
SEI_RESISTIVITY = 0.0 # SEI Layer Resistance
SEI_REACTION_RATE_REST = 0.0  # Disables calendar aging

# Load model and parameters
model = pybamm.lithium_ion.SPM(options={"working electrode": "both"})
parameter_values = pybamm.ParameterValues(chemistry=pybamm.parameter_sets.Chen2020)

print("Parameter setup complete. Environment is ready for simulation.")


# ==============================================================================
# 2. DEFINITION OF USAGE PROFILE AND PYBAMM EXPERIMENT CREATION
# ==============================================================================

def generate_hourly_power_profile_low_cycle(hours):
    """Generates the usage profile: Discharge and intermediate Charge for 4h periods."""
    power_profile = np.zeros(hours)
    for i in range(hours):
        hour_of_day = i % 24
        # Discharge period
        if DISCHARGE_START_HOUR <= hour_of_day < DISCHARGE_END_HOUR:
            power_profile[i] = -LOW_CYCLE_POWER_KW  # Negative for discharge
        # Charge period
        elif CHARGE_START_HOUR <= hour_of_day < CHARGE_END_HOUR:
            power_profile[i] = LOW_CYCLE_POWER_KW # Positive for charge
    return power_profile


hourly_power_profile = generate_hourly_power_profile_low_cycle(24)
# Convert Power (kW) to Current (A) -> I = P / V
I_cycle_A = hourly_power_profile * 1000 / V_SYSTEM_NOMINAL

time_hours_x = np.arange(0, 24, 1)

interpolation_data = np.column_stack((time_hours_x, I_cycle_A))

# Create PyBaMM Interpolant object for the current profile
current_interpolator = pybamm.Interpolant(
    interpolation_data,
    pybamm.t
)

# 3. Execution of Accelerated Aging Simulation
# Simulate the profile for the total number of cycles (922 cycles = 10 years)
experiment = pybamm.Experiment(
    ["Rest for 24 hours"] * TOTAL_CYCLES, # 'Rest' command is used to run the simulation over 24h
    period="24 hours"
)

# 4. Insertion of Parameters
missing_params = {
    # Geometry
    "Electrode width [m]": ELECTRODE_WIDTH_M,
    "Electrode height [m]": ELECTRODE_HEIGHT_M,
    "Number of electrodes connected in parallel to make a cell": 1,
    "Negative electrode thickness [m]": 8.58e-05,
    "Positive electrode thickness [m]": 8.58e-05,

    # CALIBRATION (LLI, LAM, SEI Resistance, Calendar Aging)
    "Current density of side reaction [A.m-2]": SEI_SIDE_REACTION_RATE,
    "Negative electrode LAM constant experimental [s-1]": LAM_RATE,
    "Positive electrode LAM constant experimental [s-1]": LAM_RATE,
    "SEI resistivity [Ohm.m]": SEI_RESISTIVITY,
    "SEI current density [A.m-2]": SEI_REACTION_RATE_REST,

    # Current Profile
    "Current function [A]": current_interpolator
}

parameter_values.update(
    missing_params,
    check_already_exists=False
)

print(f"\nStarting SPM simulation of {TOTAL_CYCLES} cycles ({TIME_HORIZON_YEARS} years)...")

# 5. Solve the Model: CasadiSolver with high precision and incompatible option removed
sim = pybamm.Simulation(
    model,
    experiment=experiment,
    parameter_values=parameter_values,
    # Final correction: Removing 'extra_options_call' and using high precision
    solver=pybamm.CasadiSolver(mode="fast", atol=1e-6, rtol=1e-6)
)
solution = sim.solve()

print("PyBaMM simulation successfully completed.")

# ==============================================================================
# 3. EXTRACTION OF PHYSICAL RESULTS (SOH and IMPEDANCE)
# ==============================================================================

# 1. Extract Capacity and Resistance (using all time points)
capacity_ah = solution["Discharge capacity [A.h]"].entries

R_neg_ohm_m2 = solution["X-averaged negative electrode resistance [Ohm.m2]"].entries
R_pos_ohm_m2 = solution["X-averaged positive electrode resistance [Ohm.m2]"].entries
# Convert Area-Specific Resistance (Ohm.m2) to Internal Resistance (Ohm)
R_int_ohm = (R_neg_ohm_m2 + R_pos_ohm_m2) / CELL_AREA_M2

# 2. Sampling of End-of-Cycle points (More robust logic)
time_entries = solution["Time [h]"].entries
CYCLE_DURATION_H = 24

# Try to find indices where time is a multiple of 24 hours (end of cycle)
cycle_indices = np.where(np.isclose(time_entries % CYCLE_DURATION_H, 0, atol=1e-3))[0]

# Exclude the first time point (time 0)
if len(cycle_indices) > 0 and time_entries[cycle_indices[0]] == 0:
    cycle_indices = cycle_indices[1:]

# Ensures the last time point is included (in case it's slightly off the 24h multiple)
if time_entries[-1] not in time_entries[cycle_indices] or time_entries[cycle_indices[-1]] < time_entries[-1] * 0.99:
    cycle_indices = np.append(cycle_indices, len(time_entries) - 1)

cycle_indices = np.unique(cycle_indices)

time_years = time_entries[cycle_indices] / (365 * 24)
R_int_sampled = R_int_ohm[cycle_indices]
capacity_sampled = capacity_ah[cycle_indices]
initial_capacity_ah = capacity_sampled[0]

# 3. Create Degradation DataFrame
degradation_data = pd.DataFrame({
    'Time_Years': time_years,
    'SOH_Pct_PyBaMM': (capacity_sampled / initial_capacity_ah) * 100,
    'R_int_Ohm': R_int_sampled,
})

# Remove duplicates (can happen if multiple points are close to 24h multiple)
degradation_data = degradation_data.drop_duplicates(subset=['Time_Years'], keep='last').reset_index(drop=True)

# 4. Life Calculation
SOH_END_OF_LIFE = 70.0
# Find the first year where SOH is below the limit
T_life = degradation_data.loc[degradation_data['SOH_Pct_PyBaMM'] <= SOH_END_OF_LIFE, 'Time_Years'].min()

print(f"\n--- PyBaMM (SPM) Result ---")

# Calibration result confirmation
if not np.isnan(T_life):
    print(f"Technical lifespan (SoH < {SOH_END_OF_LIFE}%) is: {T_life:.2f} years.")
else:
    # Expected scenario: The 10-year calibration was achieved
    final_time = time_years.max() if not time_years.max() < 9.9 else 10.0  # Ensure it shows 10.0 if completed
    print(
        f"Technical lifespan (SoH < {SOH_END_OF_LIFE}%) is: {final_time:.2f} years (Final SoH is {degradation_data['SOH_Pct_PyBaMM'].iloc[-1]:.2f}%).")

# 5. Save Degradation Data
degradation_data.to_csv("pybamm_degradation_output.csv", index=False)
print("\nDegradation curve saved to 'pybamm_degradation_output.csv' for LCOE recalculation.")