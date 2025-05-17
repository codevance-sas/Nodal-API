# app/services/hydraulics/extensions/compressor.py
import numpy as np
import math
from typing import Dict, Any, List, Optional, Tuple, Literal


def calculate_compressor_requirements(
    inlet_pressure: float,     # inlet pressure, psia
    outlet_pressure: float,    # outlet pressure, psia
    gas_rate: float,           # gas flow rate, MMscf/d
    gas_gravity: float,        # gas specific gravity (air=1)
    inlet_temperature: float,  # inlet temperature, °F
    z_avg: Optional[float] = None,  # average compressibility factor
    k: Optional[float] = None,      # specific heat ratio cp/cv
    compressor_type: Literal["centrifugal", "reciprocating"] = "centrifugal",
    stages: int = 1,           # number of compression stages
    efficiency: float = 0.75   # adiabatic efficiency
) -> Dict[str, Any]:
    """
    Calculate compressor power requirements and performance.
    
    Args:
        inlet_pressure: Compressor inlet pressure in psia
        outlet_pressure: Compressor outlet pressure in psia
        gas_rate: Gas flow rate in MMscf/d
        gas_gravity: Gas specific gravity relative to air
        inlet_temperature: Gas temperature at compressor inlet in °F
        z_avg: Average gas compressibility factor (optional)
        k: Specific heat ratio (cp/cv) (optional)
        compressor_type: Type of compressor ("centrifugal" or "reciprocating")
        stages: Number of compression stages
        efficiency: Adiabatic efficiency as fraction
        
    Returns:
        Dictionary containing calculated results
    """
    # Convert units
    inlet_temp_r = inlet_temperature + 460  # °F to °R
    
    # Calculate k if not provided (specific heat ratio)
    if k is None:
        # Estimate k based on gas gravity
        # For natural gas, k typically ranges from 1.25 to 1.32
        k = 1.32 - 0.05 * gas_gravity
    
    # Calculate z_avg if not provided
    if z_avg is None:
        # Simple compressibility correlation
        # Estimate critical properties
        p_pc = 709 - 58 * gas_gravity  # pseudo-critical pressure
        t_pc = 170 + 314 * gas_gravity  # pseudo-critical temperature
        
        # Calculate pseudo-reduced properties
        p_pr_in = inlet_pressure / p_pc
        p_pr_out = outlet_pressure / p_pc
        t_pr = inlet_temp_r / t_pc
        
        # Simple compressibility correlation
        z_in = 1.0 - 0.06 * p_pr_in / t_pr
        z_out = 1.0 - 0.06 * p_pr_out / t_pr
        z_avg = (z_in + z_out) / 2.0
    
    # Calculate compression ratio
    compression_ratio = outlet_pressure / inlet_pressure
    
    # For multi-stage compression, calculate optimal intermediate pressures
    if stages > 1:
        # Calculate optimum pressure ratio per stage
        ratio_per_stage = compression_ratio ** (1 / stages)
        
        # Calculate intermediate pressures
        stage_inlet_pressures = [inlet_pressure]
        stage_outlet_pressures = []
        
        for i in range(stages):
            stage_outlet = stage_inlet_pressures[i] * ratio_per_stage
            stage_outlet_pressures.append(stage_outlet)
            if i < stages - 1:
                stage_inlet_pressures.append(stage_outlet)
    else:
        # Single stage
        stage_inlet_pressures = [inlet_pressure]
        stage_outlet_pressures = [outlet_pressure]
        ratio_per_stage = compression_ratio
    
    # Calculate discharge temperature for each stage
    stage_discharge_temps = []
    stage_power_req = []
    
    for i in range(stages):
        stage_ratio = stage_outlet_pressures[i] / stage_inlet_pressures[i]
        stage_inlet_temp = inlet_temp_r if i == 0 else (stage_discharge_temps[i-1] - 50)  # assume 50°R cooling between stages
        
        # Calculate discharge temperature (°R)
        t2_t1_ratio = stage_ratio ** ((k-1) / k)
        discharge_temp_r = stage_inlet_temp * t2_t1_ratio / efficiency
        stage_discharge_temps.append(discharge_temp_r)
        
        # Calculate power requirement for this stage (hp)
        z_stage = z_avg  # simplification - could calculate per stage
        mw = 28.97 * gas_gravity  # molecular weight
        
        # Convert MMscf/d to CFM at actual conditions
        flow_rate_scfd = gas_rate * 1e6  # Convert to scf/d
        flow_rate_acfm = flow_rate_scfd * (inlet_pressure / stage_inlet_pressures[i]) * \
                         (stage_inlet_temp / 520) * z_stage / 1440  # 1440 minutes per day
        
        # Adiabatic power formula (hp)
        # P = (n * Z * T₁ * Q * [r^((k-1)/k) - 1]) / (229 * k-1/k * η)
        power_factor = 0.0857  # conversion factor for hp output
        power_hp = flow_rate_acfm * stage_inlet_pressures[i] * z_stage * \
                   (t2_t1_ratio - 1) * power_factor / efficiency
                    
        stage_power_req.append(power_hp)
    
    # Calculate total power requirement
    total_power_hp = sum(stage_power_req)
    total_power_kw = total_power_hp * 0.7457  # convert hp to kW
    
    # Calculate overall discharge temperature (°F)
    final_discharge_temp_f = stage_discharge_temps[-1] - 460
    
    # Calculate fuel consumption (assuming natural gas driver)
    # Typical heat rate for gas engines: 8,000-10,000 BTU/hp-hr
    # Natural gas HHV: ~1,020 BTU/scf
    heat_rate = 9000  # BTU/hp-hr
    fuel_consumption_scfh = (heat_rate * total_power_hp) / 1020  # scf/hr
    fuel_consumption_mmscfd = fuel_consumption_scfh * 24 / 1e6  # MMscf/d
    
    # Calculate compression efficiency
    ideal_power_kw = total_power_kw * efficiency
    compression_efficiency = ideal_power_kw / total_power_kw * 100
    
    # Results
    return {
        "inlet_pressure": inlet_pressure,
        "outlet_pressure": outlet_pressure,
        "compression_ratio": compression_ratio,
        "inlet_temperature_f": inlet_temperature,
        "discharge_temperature_f": final_discharge_temp_f,
        "power_required_hp": total_power_hp,
        "power_required_kw": total_power_kw,
        "power_per_stage_hp": stage_power_req,
        "stage_pressures": {
            "inlet": stage_inlet_pressures,
            "outlet": stage_outlet_pressures
        },
        "stage_discharge_temps_f": [t - 460 for t in stage_discharge_temps],
        "fuel_consumption_mmscfd": fuel_consumption_mmscfd,
        "compression_efficiency": compression_efficiency,
        "specific_power": total_power_hp / gas_rate  # hp per MMscf/d
    }


def calculate_optimal_stages(
    inlet_pressure: float,
    outlet_pressure: float,
    max_ratio_per_stage: float = 3.0
) -> int:
    """
    Calculate the optimal number of compression stages based on the overall compression ratio.
    
    Args:
        inlet_pressure: Inlet pressure in psia
        outlet_pressure: Outlet pressure in psia
        max_ratio_per_stage: Maximum compression ratio per stage (typically 3-4)
        
    Returns:
        Recommended number of compression stages
    """
    compression_ratio = outlet_pressure / inlet_pressure
    stages = math.ceil(math.log(compression_ratio) / math.log(max_ratio_per_stage))
    return max(1, stages)


def calculate_compressor_performance_curve(
    compressor_type: str,
    design_flow_rate: float,   # design flow rate in acfm
    design_head: float,        # design head in ft-lbf/lbm
    speed_rpm: float,          # speed in RPM
    impeller_diameter: float,  # impeller diameter in inches
    flow_range: List[float] = None  # flow rates to evaluate as fraction of design
) -> Dict[str, List[float]]:
    """
    Generate a compressor performance curve showing head, efficiency, and power vs. flow rate.
    
    Args:
        compressor_type: Type of compressor ("centrifugal" or "reciprocating")
        design_flow_rate: Design flow rate in actual cubic feet per minute (acfm)
        design_head: Design head in ft-lbf/lbm
        speed_rpm: Operating speed in RPM
        impeller_diameter: Impeller diameter in inches
        flow_range: List of flow rates to evaluate as fraction of design
        
    Returns:
        Dictionary with flow rates and corresponding performance metrics
    """
    if flow_range is None:
        # Default: evaluate from 50% to 120% of design flow rate
        flow_range = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
    
    # Calculate flow rates in acfm
    flow_rates = [fr * design_flow_rate for fr in flow_range]
    
    # Initialize result arrays
    heads = []
    efficiencies = []
    powers = []
    surge_margin = []
    
    if compressor_type.lower() == "centrifugal":
        # Simplified centrifugal compressor curve model
        # Head curve: typically a quadratic function of flow rate
        for q in flow_rates:
            # Normalized flow
            q_norm = q / design_flow_rate
            
            # Approximate head curve (parabolic)
            # h/h_design = a - b*(q/q_design)^2
            a = 1.2  # head at zero flow
            b = 0.2  # shape parameter
            head = design_head * (a - b * q_norm**2)
            heads.append(head)
            
            # Approximate efficiency curve (typical centrifugal)
            # Efficiency is a parabolic function peaking at design point
            if q_norm <= 1.0:
                # Left side of peak
                eff = 0.87 * (1 - 0.4 * (1 - q_norm)**2)
            else:
                # Right side of peak
                eff = 0.87 * (1 - 0.3 * (q_norm - 1)**2)
            efficiencies.append(eff * 100)  # as percentage
            
            # Calculate power (hp) = (head * flow * density) / (33000 * efficiency)
            # Using conversion factor for simplification
            power = head * q / (5307 * eff)
            powers.append(power)
            
            # Calculate surge margin
            # (distance from operating point to surge line as % of design flow)
            surge_flow = design_flow_rate * 0.6  # assume surge at 60% of design
            surge_m = (q - surge_flow) / design_flow_rate * 100 if q > surge_flow else 0
            surge_margin.append(surge_m)
    
    else:  # reciprocating
        # Reciprocating compressors have a different performance profile
        # Relatively constant head across flow range with declining efficiency at extremes
        for q in flow_rates:
            # Normalized flow
            q_norm = q / design_flow_rate
            
            # Head for reciprocating is relatively constant
            # Slight increase at lower flows due to valve dynamics
            head_factor = 1.0 + 0.05 * (1 - q_norm)
            head = design_head * head_factor
            heads.append(head)
            
            # Efficiency curve for reciprocating
            # Peaks near design point, drops at extremes
            eff = 0.85 * (1 - 0.25 * abs(q_norm - 1)**1.5)
            efficiencies.append(eff * 100)
            
            # Power calculation
            power = head * q / (5307 * eff)
            powers.append(power)
            
            # Reciprocating compressors don't have surge in the same way
            # Use capacity factor instead
            cap_factor = q / design_flow_rate * 100
            surge_margin.append(cap_factor)
    
    # Return performance curves
    return {
        "flow_rate_acfm": flow_rates,
        "head_ft": heads,
        "efficiency_percent": efficiencies,
        "power_hp": powers,
        "surge_margin_percent": surge_margin if compressor_type.lower() == "centrifugal" else None,
        "capacity_percent": surge_margin if compressor_type.lower() == "reciprocating" else None
    }


def joule_thomson_cooling(
    inlet_pressure: float,     # inlet pressure, psia
    outlet_pressure: float,    # outlet pressure, psia
    inlet_temperature: float,  # inlet temperature, °F
    gas_gravity: float,        # gas specific gravity (air=1)
    co2_fraction: float = 0.0, # CO2 fraction in gas
    h2s_fraction: float = 0.0, # H2S fraction in gas
    n2_fraction: float = 0.0   # N2 fraction in gas
) -> Dict[str, Any]:
    """
    Calculate temperature drop due to Joule-Thomson cooling effect in gas pipelines.
    
    Args:
        inlet_pressure: Gas pressure before expansion in psia
        outlet_pressure: Gas pressure after expansion in psia
        inlet_temperature: Gas temperature before expansion in °F
        gas_gravity: Gas specific gravity relative to air
        co2_fraction: Mole fraction of CO2 in the gas
        h2s_fraction: Mole fraction of H2S in the gas
        n2_fraction: Mole fraction of N2 in the gas
        
    Returns:
        Dictionary with calculated temperature and related data
    """
    # Calculate Joule-Thomson coefficient (°F/psi)
    # This is a simplified correlation based on gas gravity and temperature
    # More accurate values would require equation of state calculations
    
    # Base JT coefficient for natural gas (°F/psi)
    # Higher for heavier components
    base_jt = 0.045 + 0.01 * gas_gravity
    
    # Adjust for contaminants (CO2, H2S increase cooling effect)
    jt_coef = base_jt * (1 + 0.5 * co2_fraction + 0.7 * h2s_fraction - 0.1 * n2_fraction)
    
    # Adjust for temperature (JT effect decreases at higher temperatures)
    temp_factor = 1.0 - 0.003 * (inlet_temperature - 60)
    jt_coef = jt_coef * temp_factor
    
    # Calculate temperature drop
    pressure_drop = inlet_pressure - outlet_pressure
    temp_drop = jt_coef * pressure_drop
    
    # Calculate outlet temperature
    outlet_temperature = inlet_temperature - temp_drop
    
    # Check for hydrate formation risk
    # Simple hydrate formation temperature estimate for natural gas (°F)
    hydrate_temp = 50 + 0.2 * outlet_pressure - 20 * gas_gravity
    
    # Determine if there's a hydrate risk
    hydrate_risk = outlet_temperature <= hydrate_temp
    margin = outlet_temperature - hydrate_temp
    
    # Return results
    return {
        "inlet_temperature": inlet_temperature,
        "outlet_temperature": outlet_temperature,
        "temperature_drop": temp_drop,
        "jt_coefficient": jt_coef,
        "hydrate_formation_temp": hydrate_temp,
        "hydrate_risk": hydrate_risk,
        "hydrate_margin": margin,
        "pressure_drop": pressure_drop
    }


def critical_flow_calculation(
    upstream_pressure: float,  # upstream pressure, psia
    downstream_pressure: float,  # downstream pressure, psia
    upstream_temperature: float,  # upstream temperature, °F
    gas_gravity: float,  # gas specific gravity (air=1)
    orifice_diameter: float,  # orifice diameter, inches
    discharge_coefficient: float = 0.85,  # discharge coefficient
    z_factor: Optional[float] = None,  # gas compressibility factor
    k: Optional[float] = None  # specific heat ratio cp/cv
) -> Dict[str, Any]:
    """
    Calculate gas flow through an orifice or choke, accounting for critical flow.
    
    Args:
        upstream_pressure: Pressure upstream of choke in psia
        downstream_pressure: Pressure downstream of choke in psia
        upstream_temperature: Temperature upstream of choke in °F
        gas_gravity: Gas specific gravity relative to air
        orifice_diameter: Diameter of the orifice/choke in inches
        discharge_coefficient: Discharge coefficient for the orifice
        z_factor: Gas compressibility factor (optional)
        k: Specific heat ratio (cp/cv) (optional)
        
    Returns:
        Dictionary with calculated flow rates and related data
    """
    # Convert units
    upstream_temp_r = upstream_temperature + 460  # °F to °R
    
    # Calculate k if not provided (specific heat ratio)
    if k is None:
        # Estimate k based on gas gravity
        k = 1.32 - 0.05 * gas_gravity
    
    # Calculate z-factor if not provided
    if z_factor is None:
        # Simple compressibility correlation
        p_pc = 709 - 58 * gas_gravity  # pseudo-critical pressure
        t_pc = 170 + 314 * gas_gravity  # pseudo-critical temperature
        p_pr = upstream_pressure / p_pc
        t_pr = upstream_temp_r / t_pc
        z_factor = 1.0 - 0.06 * p_pr / t_pr
    
    # Calculate critical pressure ratio
    critical_ratio = (2 / (k + 1)) ** (k / (k - 1))
    
    # Determine if flow is critical (sonic)
    pressure_ratio = downstream_pressure / upstream_pressure
    is_critical = pressure_ratio <= critical_ratio
    
    # Calculate flow area (square inches)
    area = math.pi * (orifice_diameter / 2) ** 2
    
    # Gas flow calculation
    if is_critical:
        # Critical (sonic) flow
        # When flow is choked, flow rate is independent of downstream pressure
        # Q = C * A * P_up * sqrt(k/(z*R*T)) * sqrt(2/(k+1))^((k+1)/(k-1))
        flow_const = 38.77  # unit conversion constant for Mscf/d
        critical_term = math.sqrt(k * (2 / (k + 1)) ** ((k + 1) / (k - 1)))
        
        gas_rate = flow_const * discharge_coefficient * area * upstream_pressure * \
                   critical_term / math.sqrt(z_factor * gas_gravity * upstream_temp_r)
    else:
        # Subsonic flow
        # Q = C * A * P_up * sqrt(k/(z*R*T)) * (P_d/P_up)^(1/k) * sqrt((1-(P_d/P_up)^((k-1)/k))/(1-(P_d/P_up)))
        flow_const = 38.77
        flow_term = (pressure_ratio ** (1/k)) * math.sqrt((1 - pressure_ratio ** ((k-1)/k)) / (1 - pressure_ratio))
        
        gas_rate = flow_const * discharge_coefficient * area * upstream_pressure * \
                   math.sqrt(k / (z_factor * gas_gravity * upstream_temp_r)) * flow_term
    
    # Calculate gas velocity at choke (ft/s)
    gas_const = 10.73  # psia-ft³/(lbmol-°R)
    mw = 28.97 * gas_gravity  # molecular weight
    
    if is_critical:
        # Critical velocity is sonic velocity
        sound_speed = math.sqrt(k * gas_const * upstream_temp_r / mw) * 32.2  # ft/s
        velocity = sound_speed
    else:
        # Subsonic velocity
        # Convert gas flow from Mscf/d to actual ft³/s
        act_flow_cfs = gas_rate * 1000 / 86400 * (upstream_temp_r / 520) * (14.7 / upstream_pressure) * z_factor
        velocity = act_flow_cfs / (area / 144)  # ft/s
    
    # Calculate if there's potential for hydrate formation
    # Due to cooling effect of expansion
    jt_results = joule_thomson_cooling(
        upstream_pressure, 
        downstream_pressure,
        upstream_temperature,
        gas_gravity
    )
    
    return {
        "gas_flow_rate_mscfd": gas_rate,
        "is_critical_flow": is_critical,
        "critical_pressure_ratio": critical_ratio,
        "actual_pressure_ratio": pressure_ratio,
        "gas_velocity_ft_sec": velocity,
        "sound_speed_ft_sec": math.sqrt(k * gas_const * upstream_temp_r / mw) * 32.2,
        "downstream_temperature": jt_results["outlet_temperature"],
        "temperature_drop": jt_results["temperature_drop"],
        "hydrate_risk": jt_results["hydrate_risk"],
        "hydrate_formation_temp": jt_results["hydrate_formation_temp"]
    }