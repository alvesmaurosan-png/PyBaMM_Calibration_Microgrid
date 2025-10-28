import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import networkx as nx

# Global style and font configuration
plt.style.use('ggplot')
# Nota sobre as fontes: Se "Noto Sans" não estiver instalada, o Matplotlib usará a fonte padrão 'sans-serif',
# o que gerou os avisos (findfont: Generic family 'sans-serif' not found because none of the following families were found: Noto Sans).
# Isso não impede a execução do código ou a geração dos gráficos.
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = 'Noto Sans'
plt.rcParams['figure.figsize'] = (10, 6)


# --- Functions for Graph Generation ---

def gerar_grafico_1_unifilar():
    """Generates a simplified single-line block diagram (Figure 1)."""

    # 1. Define system nodes
    nodes = {
        'PV Array': (0, 0.5),
        'ESS (SLB)': (0, -0.5),
        'PCS/Bidirectional Inverter': (1, 0),
        'Commercial Load': (2, 0.5),
        'Grid': (2, -0.5)
    }

    # 2. Define connections (energy flows)
    edges = [
        ('PV Array', 'PCS/Bidirectional Inverter', 'DC'),
        ('ESS (SLB)', 'PCS/Bidirectional Inverter', 'DC'),
        ('PCS/Bidirectional Inverter', 'Commercial Load', 'AC'),
        ('PCS/Bidirectional Inverter', 'Grid', 'AC'),
        ('Grid', 'Commercial Load', 'AC')
    ]

    G = nx.MultiDiGraph()
    for n, pos in nodes.items():
        G.add_node(n, pos=pos)

    for u, v, label in edges:
        G.add_edge(u, v, label=label)

    pos = nx.get_node_attributes(G, 'pos')

    plt.figure(figsize=(10, 5))

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=3000, node_color='lightblue', edgecolors='black', linewidths=1.5,
                           alpha=0.9)

    # Draw node labels
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')

    # Draw edges and labels
    nx.draw_networkx_edges(G, pos, edge_color='gray', width=2, arrows=True, arrowsize=20)

    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color='red', font_size=9)

    # TITLE TRANSLATED
    plt.title('Figure 1: Simplified Single-Line Diagram of the Hybrid Microsystem (PV+SLB)')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig('Figure_1_Unifilar.png')
    plt.close()
    print("Figure 1 (Single-Line) generated: Figure_1_Unifilar.png")


def gerar_grafico_2_soc_potencia():
    """
    Generates the State of Charge (SoC) and Power profile (Figure 2).
    Uses interpolation to ensure array dimensions match the time axis (25 points: 0h to 24h).
    """
    hours = np.arange(0, 25)  # 0h to 24h -> Total de 25 pontos

    # --- State of Charge (SoC) data (Blue line) ---
    # Horas chaves (x) e valores de SoC (y) para interpolação linear
    key_hours_soc = np.array([0, 10, 14, 18, 22, 24])
    key_soc = np.array([75, 75, 100, 100, 75, 75])

    # Interpolação linear para a linha de SoC
    soc = np.interp(hours, key_hours_soc, key_soc)

    # --- Power data (kW) (Red dashed line) ---
    # Para criar o degrau (step function), usamos pontos levemente deslocados no tempo (0.0001)
    power_hours = np.array([0, 10, 10.0001, 14, 14.0001, 18, 18.0001, 22, 22.0001, 24])
    # Power values: 0.0 -> 0.0 (Charge start) 1.5 -> 1.5 (Charge end) 0.0 -> 0.0 (Discharge start) -1.5 -> -1.5 (Discharge end) 0.0
    power_values = np.array([0.0, 0.0, 1.5, 1.5, 0.0, 0.0, -1.5, -1.5, 0.0, 0.0])

    # Interpolação linear (que se comporta como step com os pontos deslocados)
    power = np.interp(hours, power_hours, power_values)

    # Graph Generation (Dual Axis)
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Primary Axis: State of Charge (SoC)
    color_soc = 'tab:blue'
    ax1.set_xlabel('Hour of Day (h)', fontsize=12)
    # Y-AXIS LABEL TRANSLATED
    ax1.set_ylabel('State of Charge (SoC) [%]', color=color_soc, fontsize=12)
    ax1.plot(hours, soc, color=color_soc, linewidth=3, label='SoC [%]')
    ax1.tick_params(axis='y', labelcolor=color_soc)
    ax1.set_ylim(70, 105)
    ax1.set_xticks(np.arange(0, 26, 5))
    ax1.set_xlim(0, 25)

    # Secondary Axis: Power
    ax2 = ax1.twinx()
    color_power = 'tab:red'
    # Y-AXIS LABEL TRANSLATED
    ax2.set_ylabel('Power (kW) (Charge > 0, Discharge < 0)', color=color_power, fontsize=12)
    ax2.plot(hours, power, color=color_power, linestyle='--', linewidth=1.5, label='Power (kW)')
    ax2.tick_params(axis='y', labelcolor=color_power)
    ax2.set_ylim(-2.0, 2.0)

    # TITLE TRANSLATED
    plt.title('Figure 2: Typical Hourly Operation Profile (SoC and Power)', fontsize=16)
    ax1.grid(True, linestyle='--', alpha=0.6)
    fig.tight_layout()
    plt.savefig('Figure_2_Operation_Profile_SoC_Power.png')
    plt.close()
    print("Figure 2 (SoC/Power Profile) generated: Figure_2_Operation_Profile_SoC_Power.png")


def gerar_grafico_demanda_despacho():
    """Generates the demand and ESS dispatch profile for Peak Shaving (Figure 3)."""

    hours = np.arange(0, 24)
    # 1. Commercial Demand Profile (kW)
    commercial_demand = np.array([
        10, 8, 8, 8, 10, 15, 30, 50, 65, 75, 80, 85,
        90, 95, 88, 70, 60, 75, 85, 70, 50, 30, 20, 15
    ])

    # 2. Photovoltaic Generation Profile (kW)
    pv_generation = np.array([
        0, 0, 0, 0, 0, 0, 5, 25, 50, 75, 90, 95,
        90, 80, 60, 30, 10, 0, 0, 0, 0, 0, 0, 0
    ])

    # 3. ESS Dispatch Profile (kW)
    ess_dispatch = np.array([
        0, 0, 0, 0, 0, 0, 0, 0, 0, -5, -10, -15,  # PV surplus charging
        -10, 0, 0, 0, 0, 15, 20, 15, 0, 0, 0, 0  # Discharge (Peak Shaving) - 20kW Power
    ])

    # Calculations
    net_grid_power = commercial_demand - pv_generation - ess_dispatch
    grid_purchase = np.maximum(0, net_grid_power)

    # Graph Generation
    plt.figure(figsize=(14, 7))

    # LEGENDS TRANSLATED
    plt.plot(hours, commercial_demand, label='Commercial Demand (kW)', color='black', linewidth=2.5, linestyle='-')
    plt.plot(hours, pv_generation, label='Photovoltaic Generation (PV)', color='orange', linewidth=2.5, linestyle='--')
    plt.plot(hours, grid_purchase, label='Net Grid Power Purchase (kW)', color='red', linewidth=1.5,
             linestyle='-', alpha=0.7)
    plt.plot(hours, ess_dispatch, label='ESS Dispatch Power (Discharge > 0, Charge < 0)', color='blue',
             linewidth=2, linestyle=':')

    plt.fill_between(hours, 0, ess_dispatch, where=(ess_dispatch > 0), color='green', alpha=0.3,
                     label='ESS Discharge (Peak Shaving)')
    plt.fill_between(hours, 0, ess_dispatch, where=(ess_dispatch < 0), color='purple', alpha=0.3,
                     label='ESS Charge (PV Surplus)')

    # Highlight Lines
    # LABEL TRANSLATED
    plt.axvspan(17, 21, color='red', alpha=0.1, label='Peak Hours (PH)')
    plt.axhline(0, color='gray', linestyle='-', linewidth=0.8)

    # Graph Settings
    # TITLE AND AXES TRANSLATED
    plt.title('Figure 3: Demand, PV Generation, and ESS Peak Shaving Profiles on a Typical Day', fontsize=16)
    plt.xlabel('Hour of Day', fontsize=12)
    plt.ylabel('Power (kW)', fontsize=12)
    plt.xticks(hours)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(loc='upper right', fontsize=10)
    plt.xlim(0, 23)

    max_y = commercial_demand.max()
    min_y = ess_dispatch.min() * 1.1
    plt.ylim(min_y * 1.1, max_y * 1.1)

    plt.tight_layout()
    plt.savefig('Figure_3_Operation_Profile.png')
    plt.close()
    print("Figure 3 (Demand/Dispatch Profile) generated: Figure_3_Operation_Profile.png")


def gerar_grafico_3_comparacao_pybamm():
    """
    Generates the PyBaMM comparison curve (Figure 4).
    Compares the uncalibrated result (2.53 years) with the calibrated one (10 years).
    """

    # Simulated Data (Years vs SoH)
    years = np.arange(11)

    # Scenario 1: Uncalibrated (Reaches 70% in 2.53 years)
    soh_uncalibrated = np.where(years <= 2.53, 80 - (years * (10 / 2.53)), 70)
    soh_uncalibrated[0] = 80
    soh_uncalibrated[soh_uncalibrated < 70] = 70

    # Scenario 2: Calibrated (Reaches 70% in 10.00 years)
    soh_calibrated = 80 - years * 1.0

    plt.figure()

    # Uncalibrated Curve
    # LEGEND TRANSLATED
    plt.plot(years, soh_uncalibrated, marker='x', linestyle='--', color='red', linewidth=2,
             label='Uncalibrated (Initial Result: 2.53 years)')

    # Calibrated Curve (Final Result)
    # LEGEND TRANSLATED
    plt.plot(years, soh_calibrated, marker='o', linestyle='-', color='darkgreen', linewidth=2,
             label='Calibrated (Final Result: 10.00 years)')

    # LEGEND TRANSLATED
    plt.axhline(y=70, color='gray', linestyle=':', label='EOL (70% SoH)')

    # TITLE AND AXES TRANSLATED
    plt.title('Figure 4: Calibration Validation: SoH Degradation (PyBaMM)')
    plt.xlabel('Year of Operation')
    plt.ylabel('State of Health (SoH) [%]')
    plt.ylim(65, 85)
    plt.xlim(0, 10)
    plt.legend(loc='lower left')
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.tight_layout()
    plt.savefig('Figure_4_PyBaMM_Comparison.png')
    plt.close()
    print("Figure 4 (PyBaMM Comparison) generated: Figure_4_PyBaMM_Comparison.png")


def gerar_grafico_4_degradacao_final():
    """Generates the SoH degradation curve over 10 years (Figure 5)."""
    years = np.arange(11)  # 0 to 10 years
    soh_initial = 80.0
    soh = soh_initial - years * 1.0  # Drops 1.0% p.a.

    plt.figure()
    # LEGENDS TRANSLATED
    plt.plot(years, soh, marker='o', linestyle='-', color='purple', linewidth=2, label='Projected SoH')
    plt.axhline(y=70, color='red', linestyle='--', label='EOL (70% SoH)')
    plt.scatter(10, 70, color='red', marker='X', s=150, label='Technical Limit (Year 10)')

    # TITLE AND AXES TRANSLATED
    plt.title('Figure 5: Calibrated SoH Degradation Curve (10 Years)')
    plt.xlabel('Year of Operation')
    plt.ylabel('State of Health (SoH) [%]')
    plt.ylim(65, 85)
    plt.legend()
    plt.grid(True, linestyle=':', alpha=0.7)
    plt.tight_layout()
    plt.savefig('Figure_5_Final_SoH_Degradation.png')
    plt.close()
    print("Figure 5 (Final SoH Degradation) generated: Figure_5_Final_SoH_Degradation.png")


def gerar_grafico_5_composicao_custos():
    """Generates the composition of the Total Present Value of Costs (C_PV) (Figure 6)."""

    # INTERNAL LABELS TRANSLATED
    costs_for_chart = {
        'Initial CAPEX (Year 0)': 14160.00,
        'ESS Replacement PV (Year 10)': 4489.45,
        'OPEX (Present Value)': 1439.83
    }

    labels = costs_for_chart.keys()
    sizes = costs_for_chart.values()

    plt.figure()
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90,
            wedgeprops={'edgecolor': 'black', 'linewidth': 1.5})

    # TITLE TRANSLATED
    plt.title('Figure 6: Composition of the Total Cost Present Value (C_PV)')
    plt.axis('equal')
    plt.tight_layout()
    plt.savefig('Figure_6_Cost_Composition.png')
    plt.close()
    print("Figure 6 (Cost Composition) generated: Figure_6_Cost_Composition.png")


def gerar_grafico_6_comparacao_lcoe():
    """Generates the LCOE comparison (Figure 7)."""

    # Data: Using the calculated LCOE of 0.45 USD/kWh
    lcoe_data = {
        'PV+ESS (SLB)': 0.45,
        'Standalone PV (Est.)': 0.35,
        'Utility Tariff (Est.)': 0.20
    }

    labels = list(lcoe_data.keys())
    values = list(lcoe_data.values())

    plt.figure()
    barras = plt.bar(labels, values, color=['#005A9C', '#4CAF50', '#FF9800'])

    # Add the exact value above each bar
    for bar in barras:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, yval + 0.01, f'{yval:.2f} USD/kWh', ha='center', va='bottom',
                 fontsize=10)

    # TITLE AND Y-AXIS TRANSLATED
    plt.title('Figure 7: Comparison of the Levelized Cost of Electricity (LCOE)')
    plt.ylabel('LCOE (USD/kWh)')
    plt.ylim(0, 0.8)
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig('Figure_7_LCOE_Comparison.png')
    plt.close()
    print("Figure 7 (LCOE Comparison) generated: Figure_7_LCOE_Comparison.png")


if __name__ == '__main__':
    gerar_grafico_1_unifilar()
    gerar_grafico_2_soc_potencia()  # NEW and CORRECTED: Figure 2 (SoC/Power)
    gerar_grafico_demanda_despacho()  # Renamed and is now Figure 3 (Demand/Dispatch)
    gerar_grafico_3_comparacao_pybamm()  # Now Figure 4
    gerar_grafico_4_degradacao_final()  # Now Figure 5
    gerar_grafico_5_composicao_custos()  # Now Figure 6
    gerar_grafico_6_comparacao_lcoe()  # Now Figure 7

    print("\nAll 7 figures have been generated and saved as PNG files.")
    print("The error in Figure 2 has been corrected using interpolation methods.")