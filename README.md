# VNA + TC-720 Integrated Data Collection System

## 📋 Overview

This integrated system combines **TC-720 Temperature Controller** and **Keysight P5027A VNA** for synchronized data collection and analysis. The system enables precise correlation between temperature changes and RF/microwave device performance.

---

## 🗂️ File Structure

### Data Collection Scripts

1. **`data_collection_multi_temp_time_interval.py`**
   - Multi-temperature mode (1-8 user-defined targets)
   - VNA sweeps every 60 seconds (time-based)
   - Automatic temperature stabilization (±0.1°C for 30s)

2. **`data_collection_multi_temp_temp_interval.py`**
   - Multi-temperature mode (1-8 user-defined targets)
   - VNA sweeps every 0.5°C temperature change (temperature-based)
   - Captures data at consistent temperature intervals

3. **`data_collection_single_temp.py`**
   - Single temperature target (backward compatible)
   - VNA sweeps every 60 seconds
   - Simplified operation for single-point measurements

### Analysis Tool

4. **`analysis_dashboard.py`**
   - Web-based Plotly Dash interface
   - Interactive temperature slider
   - Real and Imaginary S11 plots
   - Runs locally at http://127.0.0.1:8050

### Phase 4 Enhancements (Optional)

5. **`enhancement_export.py`**
   - Export sweeps to CSV or Excel
   - Filter by temperature range
   - Create combined datasets

6. **`enhancement_overlay.py`**
   - Overlay multiple temperature sweeps
   - Temperature gradient color coding
   - Difference plots between temperatures

7. **`enhancement_derived_params.py`**
   - Calculate RF parameters: Return Loss, VSWR, Impedance
   - Smith Chart generation
   - Resonance frequency analysis

---

## 🔧 Installation

### Prerequisites

```bash
# Python 3.8 or higher required

# Core dependencies
pip install pyvisa
pip install pandas
pip install numpy

# For analysis dashboard
pip install dash
pip install plotly

# For enhancements (optional)
pip install openpyxl  # Excel export
pip install kaleido   # Static image export
```

### Additional Requirements

1. **TC-720 Library**: Place `Py_TC720.py` in the same directory as the scripts
2. **VISA Driver**: Install NI-VISA or Keysight IO Libraries
3. **Hardware**: 
   - TC-720 Temperature Controller (USB/Serial connection)
   - Keysight P5027A VNA (LAN/USB connection)

---

## 🚀 Quick Start

### Option 1: Time-Interval Multi-Temperature Collection

```bash
python data_collection_multi_temp_time_interval.py
```

**User Prompts:**
```
How many target temperatures? (1-8): 3
Target Temperature 1 (°C): 25.0
Ramp Time 1 (seconds): 300
Target Temperature 2 (°C): 35.0
Ramp Time 2 (seconds): 600
Target Temperature 3 (°C): 45.0
Ramp Time 3 (seconds): 600
```

**What happens:**
- System ramps to each temperature sequentially
- VNA takes measurements every 60 seconds throughout
- Automatically waits for temperature stability at each target
- Creates organized experiment directory with all data

### Option 2: Temperature-Interval Multi-Temperature Collection

```bash
python data_collection_multi_temp_temp_interval.py
```

**Same user prompts as Option 1**

**What happens:**
- System ramps to each temperature sequentially
- VNA takes measurements every time temperature changes by 0.5°C
- Captures data at consistent temperature intervals
- Ideal for detailed temperature-dependent characterization

### Option 3: Single Temperature (Simple)

```bash
python data_collection_single_temp.py
```

**User Prompts:**
```
Target Temperature (float): 30.0
Time to Get to Target Temperature (integer): 600
```

---

## 📁 Data Organization

Each experiment creates a structured directory:

```
experiment_20250108_143000/
├── temperature_log.csv          # Continuous temperature data
├── sweep_data/                  # Individual VNA sweeps
│   ├── sweep_001_25.3C_20250108_143100.csv
│   ├── sweep_002_26.1C_20250108_143200.csv
│   └── ...
└── metadata.json               # Experiment metadata
```

### CSV File Structure

**Temperature Log:**
```csv
Timestamp,Elapsed_Time_s,Target_Temp_C,Sensor_Temp_1_C,Sensor_Temp_2_C,Current_Step
2025-01-08 14:31:00,0,25.0,24.8,24.9,1
```

**VNA Sweep:**
```csv
Point_Index,Sweep_Timestamp,Temperature_C,Frequency_Hz,Real_S11,Imag_S11
1,2025-01-08 14:31:00,25.3,1000000000,0.123456,-0.234567
```

---

## 📊 Analysis Dashboard Usage

### Launch Dashboard

```bash
python analysis_dashboard.py
```

### Using the Interface

1. **Open Browser**: Navigate to http://127.0.0.1:8050
2. **Select Experiment**: Choose from dropdown menu
3. **Navigate Data**: Use temperature slider to view different measurements
4. **Interactive Plots**: Hover for detailed values, zoom, pan

### Dashboard Features

- 📉 **Real S11 vs Frequency** (left plot)
- 📉 **Imaginary S11 vs Frequency** (right plot)
- 🎚️ **Temperature Slider** (snaps to actual recorded temperatures)
- 📊 **Experiment Info** (metadata display)

---

## 🎁 Enhancement Usage

### Export Data

```bash
python enhancement_export.py
```

**Features:**
- Export temperature ranges to Excel
- Create combined CSV files
- Generate summary reports

### Overlay Plots

```bash
python enhancement_overlay.py
```

**Features:**
- Overlay multiple temperatures on single plot
- Temperature-gradient color coding
- Difference plots between temperatures
- Save as interactive HTML or static images

### Derived Parameters

```bash
python enhancement_derived_params.py
```

**Calculated Parameters:**
- Return Loss (dB)
- VSWR (Voltage Standing Wave Ratio)
- Input Impedance (Z_in)
- Reflection Coefficient (magnitude & phase)
- Smith Chart visualization
- Resonance frequency analysis

---

## ⚙️ Configuration

### Modifiable Parameters

**In data collection scripts:**

```python
# Temperature Settings
SAMPLING_INTERVAL_SECONDS = 5    # Temperature log interval
TEMP_TOLERANCE = 0.1             # Stability tolerance (±°C)
STABILITY_DURATION = 30          # Stability wait time (seconds)

# VNA Settings
VNA_SWEEP_INTERVAL = 60          # Time between sweeps (seconds)
TEMP_SWEEP_THRESHOLD = 0.5       # Temp change trigger (°C)
NUM_POINTS = 201                 # Points per VNA sweep

# RF Settings
Z0 = 50.0                        # Characteristic impedance (Ω)
```

### Device Connection

**TC-720:**
- Auto-detected via `Py_TC720.find_address()`
- Manual: Set `COM_PORT = 'COM3'` or `'/dev/ttyUSB0'`

**VNA:**
- Current: `'TCPIP0::DESKTOP-N8PF739::hislip_PXI10_CHASSIS1_SLOT1_INDEX0::INSTR'`
- Modify the VISA resource string as needed

---

## 🐛 Troubleshooting

### Common Issues

**1. TC-720 Not Found**
```
Error connecting to TC-720: Could not find device
```
**Solution:** Check USB connection, verify `Py_TC720.py` is in directory

**2. VNA Connection Failed**
```
Error connecting to VNA: Could not open resource
```
**Solution:** 
- Verify VNA is on network
- Check VISA resource string
- Install VISA libraries (NI-VISA or Keysight IO)

**3. Dashboard Won't Start**
```
ModuleNotFoundError: No module named 'dash'
```
**Solution:** `pip install dash plotly`

**4. No Experiment Directories Found**
```
❌ No experiment directories found.
```
**Solution:** Run a data collection script first to generate experiment data

### Temperature Stability Issues

If system takes too long to stabilize:
- Increase `TEMP_TOLERANCE` (e.g., 0.2°C)
- Decrease `STABILITY_DURATION` (e.g., 15 seconds)
- Check TC-720 PID tuning parameters

---

## 📖 Best Practices

### For Accurate Measurements

1. **Pre-warm Equipment**: Let TC-720 and VNA warm up for 30 minutes
2. **Calibrate VNA**: Perform full 2-port calibration before experiments
3. **Temperature Ramping**: Use gradual ramp times (avoid thermal shock)
4. **Minimize Vibrations**: Keep setup stable during measurements
5. **Cable Management**: Secure all RF cables to prevent movement

### For Efficient Data Collection

1. **Plan Temperature Points**: Choose meaningful temperature intervals
2. **Estimate Ramp Times**: 
   - Small changes (5°C): 5-10 minutes
   - Medium changes (20°C): 15-30 minutes
   - Large changes (50°C): 30-60 minutes
3. **Monitor First Run**: Watch initial experiment to verify stability
4. **Backup Data**: Copy experiment directories to external storage

---

## 📈 Example Workflow

### Complete Characterization Example

```bash
# Step 1: Collect data with time-interval sweeps
python data_collection_multi_temp_time_interval.py
# Input: 5 temperatures from 20°C to 60°C in 10°C increments
# Duration: ~2-3 hours depending on ramp times

# Step 2: Analyze data
python analysis_dashboard.py
# Open browser, select experiment, review data quality

# Step 3: Calculate derived parameters
python enhancement_derived_params.py
# Generates return loss, VSWR, impedance analysis

# Step 4: Create overlay plots
python enhancement_overlay.py
# Compare S11 across all temperatures

# Step 5: Export results
python enhancement_export.py
# Create Excel report for documentation
```

---

## 🔬 Scientific Applications

This system is ideal for:

- **Antenna Characterization**: Temperature-dependent impedance matching
- **Filter Performance**: Thermal drift in RF filters
- **Material Testing**: Permittivity changes with temperature
- **Device Reliability**: Thermal cycling effects on components
- **Quality Control**: Production testing at multiple temperatures

---

## 📝 Citation & Credits

### Dependencies

- **Py_TC720**: TC-720 Python interface (GitHub: Py_TC720)
- **PyVISA**: Instrument communication
- **Plotly Dash**: Interactive web visualization
- **Pandas/NumPy**: Data processing

### Version History

- **v1.0** (2025-01-08): Initial release
  - Multi-temperature support (1-8 targets)
  - Time and temperature interval modes
  - Web-based analysis dashboard
  - Export and overlay enhancements
  - Derived parameter calculations

---

## 🆘 Support

### For Issues

1. Check this README's Troubleshooting section
2. Verify all dependencies are installed
3. Confirm hardware connections
4. Review error messages carefully

### For Feature Requests

Consider modifying the scripts directly - they are well-commented and modular.

---

## 📄 License

These scripts are provided as-is for research and development purposes.

---

## 🎯 Quick Reference

### File Selection Guide

| Use Case | Script to Use |
|----------|--------------|
| Multiple temps, regular intervals | `data_collection_multi_temp_time_interval.py` |
| Multiple temps, at specific temps | `data_collection_multi_temp_temp_interval.py` |
| Single temperature, simple | `data_collection_single_temp.py` |
| View collected data | `analysis_dashboard.py` |
| Export to Excel/CSV | `enhancement_export.py` |
| Compare temperatures | `enhancement_overlay.py` |
| Calculate RF parameters | `enhancement_derived_params.py` |

### Key Commands

```bash
# Data collection (choose one)
python data_collection_multi_temp_time_interval.py
python data_collection_multi_temp_temp_interval.py
python data_collection_single_temp.py

# Analysis
python analysis_dashboard.py

# Enhancements (optional)
python enhancement_export.py
python enhancement_overlay.py
python enhancement_derived_params.py
```

---

**Last Updated**: January 8, 2025
**Version**: 1.0
