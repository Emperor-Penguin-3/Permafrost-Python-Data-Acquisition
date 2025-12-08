"""
Multi-Temperature Data Collection with Time-Interval VNA Sweeps (PID Mode)
===========================================================================
This script controls a TC-720 temperature controller and a Keysight P5027A VNA.
- Uses Normal Set Mode (mode 0) with PID control for reliable temperature control
- Supports 1-8 user-defined temperature targets
- Optional controlled linear ramping (user-specified ramp rate in °C/min)
- Fine-grained 1°C intermediate steps for highly linear temperature profiles
- VNA sweeps occur every 60 seconds throughout the entire thermal cycle
- Automatic temperature stabilization (±0.5°C for 5 seconds) before moving to next target
- **NEW: Temperature overshoot mode for faster phase transitions (water/ice)**
- **NEW: Repeatable experiments - run multiple experiments in succession**
- Creates organized data structure with metadata tracking
"""

import csv
import time
import json
import threading
from datetime import datetime
import os
import pyvisa as visa

# --- Configuration ---
SAMPLING_INTERVAL_SECONDS = 5  # Temperature logging interval
VNA_SWEEP_INTERVAL = 60  # VNA sweep interval in seconds
NUM_POINTS = 201  # Number of sweep points per VNA acquisition
TEMP_TOLERANCE = 0.5  # Temperature stability tolerance (±°C) - relaxed for faster stabilization
STABILITY_DURATION = 5  # Seconds to maintain stability before proceeding - reduced for efficiency
INTERMEDIATE_STEP_SIZE = 1  # Temperature step size for controlled ramping (°C) - 1°C for high linearity

# --- Global Variables ---
vna_sweep_count = 0
vna_lock = threading.Lock()
experiment_running = True
experiment_start_time = None  # Will be set when experiment starts
keyboard_interrupt_count = 0  # Track consecutive keyboard interrupts

# --- Helper Function for Time Formatting ---
def format_elapsed_time(seconds):
    """Convert seconds to human-readable format (HH:MM:SS)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

# --- 1. Setup Script Directory ---
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
os.chdir(script_dir)
print(f"Current Working Directory: {os.getcwd()}")

# --- 2. Import TC-720 Library ---
import Py_TC720

# --- 3. Setup Experiment Directory ---
def setup_experiment_directory():
    """Create organized directory structure for this experiment"""
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create main experiments folder if it doesn't exist
    experiments_base = os.path.join(script_dir, "experiments")
    os.makedirs(experiments_base, exist_ok=True)
    
    # Create this specific experiment folder
    exp_dir = os.path.join(experiments_base, f"experiment_{timestamp_str}")
    sweep_dir = os.path.join(exp_dir, "sweep_data")
    os.makedirs(sweep_dir, exist_ok=True)
    
    return exp_dir, sweep_dir, timestamp_str

# --- 4. Get User Input for Temperature Profile ---
def get_temperature_profile():
    """Prompt user for 1-8 temperature targets and optional ramp rate control"""
    while True:
        try:
            num_temps = int(input("\nHow many target temperatures? (1-8): "))
            if 1 <= num_temps <= 8:
                break
            print("Please enter a number between 1 and 8.")
        except ValueError:
            print("Invalid input. Please enter an integer.")
    
    temps = []
    
    for i in range(num_temps):
        print(f"\n--- Temperature Target {i+1} ---")
        while True:
            try:
                temp = float(input(f"Target Temperature {i+1} (°C): "))
                temps.append(temp)
                break
            except ValueError:
                print("Invalid input. Please enter a number.")
    
    # Ask about ramp rate control
    print("\n--- Ramp Rate Control ---")
    print("Choose ramping method:")
    print("1. Fast (PID-controlled, fastest possible ramping)")
    print("2. Controlled Linear (specify ramp rate in °C/minute)")
    
    while True:
        try:
            choice = int(input("Choice (1 or 2): "))
            if choice in [1, 2]:
                break
            print("Please enter 1 or 2.")
        except ValueError:
            print("Invalid input. Please enter 1 or 2.")
    
    ramp_rate = None
    if choice == 2:
        while True:
            try:
                ramp_rate = float(input("Desired ramp rate (°C/minute): "))
                if ramp_rate > 0:
                    break
                print("Ramp rate must be positive.")
            except ValueError:
                print("Invalid input. Please enter a number.")
    
    # Ask about overshoot mode
    print("\n--- Temperature Overshoot Mode ---")
    print("Enable overshoot mode for faster phase transitions (e.g., freezing/melting water)?")
    print("This temporarily sets the target ±10°C beyond actual target, then returns to target.")
    
    while True:
        overshoot_choice = input("Enable overshoot mode? (y/n): ").strip().lower()
        if overshoot_choice in ['y', 'n']:
            break
        print("Please enter 'y' or 'n'.")
    
    use_overshoot = (overshoot_choice == 'y')
    
    overshoot_amount = 10  # Default
    if use_overshoot:
        while True:
            try:
                overshoot_amount = float(input("Overshoot amount in °C (default 10): ") or "10")
                if overshoot_amount > 0:
                    break
                print("Overshoot amount must be positive.")
            except ValueError:
                print("Invalid input. Please enter a number.")
    
    return temps, ramp_rate, use_overshoot, overshoot_amount

# --- 5. Initialize Devices ---
def initialize_devices():
    """Initialize TC-720 and VNA"""
    # Initialize TC-720
    COM_PORT = Py_TC720.find_address()
    if hasattr(COM_PORT, 'device'):
        COM_PORT = COM_PORT.device
    
    try:
        # Set mode to 0 (Normal Set) with control_type 0 (PID temperature control)
        tc720 = Py_TC720.TC720(address=COM_PORT, mode=0, control_type=0)
        print(f"✅ TC-720 connected on {COM_PORT}")
        print(f"   Mode: Normal Set (PID Control)")
    except Exception as e:
        print(f"❌ Error connecting to TC-720: {e}")
        return None, None
    
    # Initialize VNA
    try:
        rm = visa.ResourceManager()
        print("Available VISA Resources:", rm.list_resources())

        vna = rm.open_resource('TCPIP0::DESKTOP-N8PF739::hislip_PXI10_CHASSIS2_SLOT1_INDEX0::INSTR')
        
        # P5027A: 'TCPIP0::DESKTOP-N8PF739::hislip_PXI10_CHASSIS1_SLOT1_INDEX0::INSTR'
        # P3974A: 'TCPIP0::DESKTOP-N8PF739::hislip_PXI10_CHASSIS2_SLOT1_INDEX0::INSTR'
       
        vna = rm.open_resource('TCPIP0::DESKTOP-N8PF739::hislip_PXI10_CHASSIS1_SLOT1_INDEX0::INSTR')
        print(f"✅ VNA connected: {vna.query('*IDN?').strip()}")
        
        # Configure VNA
        vna.write(f':SENSe:SWEep:POINts {NUM_POINTS}')
        vna.write(':SENSe:SWEep:MODE CONTinuous')
        vna.write(':FORMat:DATA ASCII')
        
    except Exception as e:
        print(f"❌ Error connecting to VNA: {e}")
        return tc720, None
    
    return tc720, vna

# --- 6. Calculate Intermediate Temperature Setpoints ---
def calculate_intermediate_temps(current_temp, target_temp, ramp_rate):
    """
    Calculate intermediate temperature setpoints for controlled linear ramping.
    
    Parameters:
    - current_temp: Starting temperature (°C)
    - target_temp: Final target temperature (°C)
    - ramp_rate: Desired ramp rate (°C/minute)
    
    Returns:
    - List of intermediate temperatures
    - Time to wait at each setpoint (seconds)
    """
    temp_change = target_temp - current_temp
    direction = 1 if temp_change > 0 else -1
    
    # Calculate number of steps
    num_steps = int(abs(temp_change) / INTERMEDIATE_STEP_SIZE)
    
    if num_steps == 0:
        # Already at target or very close
        return [target_temp], 0
    
    # Generate intermediate temperatures
    intermediate_temps = []
    for i in range(1, num_steps + 1):
        intermediate_temp = current_temp + (direction * INTERMEDIATE_STEP_SIZE * i)
        intermediate_temps.append(intermediate_temp)
    
    # Add final target if not already included
    if abs(intermediate_temps[-1] - target_temp) > 0.1:
        intermediate_temps.append(target_temp)
    
    # Calculate wait time per step based on ramp rate
    # ramp_rate is in °C/min, we need seconds per step
    time_per_step = (INTERMEDIATE_STEP_SIZE / ramp_rate) * 60  # seconds
    
    return intermediate_temps, time_per_step

# --- 7. Wait for Temperature Stability (WITH OVERSHOOT MODE) ---
def wait_for_stability(device, target_temp, use_overshoot=False, overshoot_amount=10, 
                      temp_log_callback=None, csvwriter=None, csvfile=None, start_time=None, step_idx=None):
    """
    Wait until temperature is stable within tolerance for specified duration.
    
    Parameters:
    - device: TC-720 device object
    - target_temp: Final target temperature (°C)
    - use_overshoot: If True, temporarily overshoot target to speed up phase transitions
    - overshoot_amount: How many degrees to overshoot (default 10°C)
    - temp_log_callback: Dictionary to update current temperature
    - csvwriter: CSV writer for logging
    - csvfile: CSV file object for flushing
    - start_time: Experiment start time
    - step_idx: Current step index
    """
    current_temp = device.get_temp()
    
    if use_overshoot:
        # Determine if we're heating or cooling
        if current_temp > target_temp:
            # Cooling - set target LOWER temporarily
            overshoot_temp = target_temp - overshoot_amount
            direction = "cooling"
            print(f"🎯 Overshoot mode: COOLING")
        else:
            # Heating - set target HIGHER temporarily
            overshoot_temp = target_temp + overshoot_amount
            direction = "heating"
            print(f"🎯 Overshoot mode: HEATING")
        
        print(f"   Temporarily setting to {overshoot_temp:.1f}°C (actual target: {target_temp:.1f}°C)")
        print(f"   Will return to {target_temp:.1f}°C when within 2°C")
        device.set_temp(overshoot_temp)
        
        # Wait until temperature CROSSES the actual target
        # For cooling: wait until current_temp <= target_temp
        # For heating: wait until current_temp >= target_temp
        overshoot_active = True
        initial_temp = current_temp  # Store starting temperature
        
        while overshoot_active:
            current_temp = device.get_temp()
            if temp_log_callback is not None:
                temp_log_callback['temp'] = current_temp
            
            distance_to_target = abs(current_temp - target_temp)
            
            # Log temperature during overshoot
            if csvwriter is not None and csvfile is not None and start_time is not None:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elapsed_time = round(time.time() - start_time)
                
                csvwriter.writerow({
                    'Timestamp': current_time,
                    'Elapsed_Time_s': elapsed_time,
                    'Target_Temp_C': overshoot_temp,  # Show overshoot target in log
                    'Sensor_Temp_1_C': current_temp,
                    'Sensor_Temp_2_C': device.get_temp2(),
                    'Current_Step': step_idx
                })
                csvfile.flush()
            
            # Check if temperature has CROSSED the target
            if direction == "cooling":
                # For cooling: current temp must be <= target
                has_crossed = (current_temp <= target_temp)
            else:
                # For heating: current temp must be >= target
                has_crossed = (current_temp >= target_temp)
            
            if has_crossed:
                # Temperature has crossed the target - reset to actual target
                print(f"   ✓ Temperature crossed target! ({current_temp:.2f}°C)")
                print(f"   🎯 Resetting controller to actual target: {target_temp:.1f}°C")
                device.set_temp(target_temp)
                overshoot_active = False
            else:
                print(f"   [{direction.upper()}] {current_temp:.2f}°C → {target_temp:.1f}°C (Δ={distance_to_target:.2f}°C)")
            
            time.sleep(2)
        
        time.sleep(1)  # Brief pause after resetting
    
    # Now proceed with normal stability check
    print(f"⏳ Waiting for temperature to stabilize at {target_temp}°C (±{TEMP_TOLERANCE}°C for {STABILITY_DURATION}s)...")
    
    stable_start = None
    
    while True:
        current_temp = device.get_temp()
        if temp_log_callback is not None:
            temp_log_callback['temp'] = current_temp
        
        # Log temperature during stability check
        if csvwriter is not None and csvfile is not None and start_time is not None:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            elapsed_time = round(time.time() - start_time)
            
            csvwriter.writerow({
                'Timestamp': current_time,
                'Elapsed_Time_s': elapsed_time,
                'Target_Temp_C': target_temp,
                'Sensor_Temp_1_C': current_temp,
                'Sensor_Temp_2_C': device.get_temp2(),
                'Current_Step': step_idx
            })
            csvfile.flush()
        
        # Check if within tolerance
        if abs(current_temp - target_temp) <= TEMP_TOLERANCE:
            if stable_start is None:
                stable_start = time.time()
                print(f"   ✓ Entered tolerance range at {current_temp}°C")
            else:
                stable_duration = time.time() - stable_start
                if stable_duration >= STABILITY_DURATION:
                    print(f"✅ Temperature stabilized at {current_temp}°C (stable for {stable_duration:.1f}s)")
                    return True
        else:
            if stable_start is not None:
                print(f"   ✗ Left tolerance range ({current_temp}°C). Resetting timer.")
            stable_start = None
        
        time.sleep(2)

# --- 8. Ramp to Temperature with Optional Rate Control ---
def ramp_to_temperature(device, target_temp, ramp_rate, temp_log_callback, csvwriter, csvfile, start_time, step_idx):
    """
    Ramp to target temperature with optional rate control.
    
    Parameters:
    - device: TC-720 device object
    - target_temp: Final target temperature (°C)
    - ramp_rate: Ramp rate (°C/min) or None for fast mode
    - temp_log_callback: Function to update current temperature tracker
    - csvwriter: CSV writer object for temperature logging
    - csvfile: CSV file object for flushing
    - start_time: Experiment start time for elapsed time calculation
    - step_idx: Current temperature step index
    """
    current_temp = device.get_temp()
    
    if ramp_rate is None:
        # Fast mode - set temperature directly and wait for stability
        print(f"🚀 Fast ramping mode: {current_temp:.1f}°C → {target_temp}°C")
        device.set_temp(target_temp)
        
        # Log temperature during ramping
        while True:
            current_temp = device.get_temp()
            temp_log_callback['temp'] = current_temp
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            elapsed_time = round(time.time() - start_time)
            elapsed_formatted = format_elapsed_time(elapsed_time)
            power = device.get_output()
            
            csvwriter.writerow({
                'Timestamp': current_time,
                'Elapsed_Time_s': elapsed_time,
                'Target_Temp_C': target_temp,
                'Sensor_Temp_1_C': current_temp,
                'Sensor_Temp_2_C': device.get_temp2(),
                'Current_Step': step_idx
            })
            csvfile.flush()
            
            print(f"  [TEMP] {current_time} | +{elapsed_formatted} | Step {step_idx} | Target: {target_temp}°C | Current: {current_temp:.2f}°C | Power: {power:.1f}")
            
            # Check if we're close enough to start stability check
            if abs(current_temp - target_temp) <= TEMP_TOLERANCE * 2:
                break
            
            time.sleep(SAMPLING_INTERVAL_SECONDS)
    
    else:
        # Controlled linear ramping mode
        intermediate_temps, time_per_step = calculate_intermediate_temps(current_temp, target_temp, ramp_rate)
        
        print(f"📈 Controlled ramping: {current_temp:.1f}°C → {target_temp}°C at {ramp_rate}°C/min")
        print(f"   Intermediate steps: {len(intermediate_temps)} steps of {INTERMEDIATE_STEP_SIZE}°C")
        print(f"   Time per step: {time_per_step:.1f}s")
        
        for i, intermediate_temp in enumerate(intermediate_temps, 1):
            device.set_temp(intermediate_temp)
            print(f"   → Setpoint {i}/{len(intermediate_temps)}: {intermediate_temp}°C")
            
            step_start = time.time()
            
            # Wait for this intermediate step
            while time.time() - step_start < time_per_step:
                current_temp = device.get_temp()
                temp_log_callback['temp'] = current_temp
                
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elapsed_time = round(time.time() - start_time)
                elapsed_formatted = format_elapsed_time(elapsed_time)
                power = device.get_output()
                
                csvwriter.writerow({
                    'Timestamp': current_time,
                    'Elapsed_Time_s': elapsed_time,
                    'Target_Temp_C': intermediate_temp,
                    'Sensor_Temp_1_C': current_temp,
                    'Sensor_Temp_2_C': device.get_temp2(),
                    'Current_Step': step_idx
                })
                csvfile.flush()
                
                print(f"  [TEMP] {current_time} | +{elapsed_formatted} | Step {step_idx}.{i} | Target: {intermediate_temp}°C | Current: {current_temp:.2f}°C | Power: {power:.1f}")
                
                time.sleep(SAMPLING_INTERVAL_SECONDS)

# --- 9. VNA Sweep Thread ---
def vna_sweep_thread(vna, sweep_dir, temp_log_callback):
    """Background thread that performs VNA sweeps every 60 seconds"""
    global vna_sweep_count, experiment_running, experiment_start_time
    
    print("🔄 VNA sweep thread started")
    
    while experiment_running:
        try:
            # Get current temperature
            current_temp = temp_log_callback()
            
            # Perform VNA sweep
            with vna_lock:
                vna_sweep_count += 1
                sweep_num = vna_sweep_count
            
            collection_time = datetime.now()
            timestamp_str = collection_time.strftime("%Y%m%d_%H%M%S")
            
            # Calculate elapsed time
            elapsed_seconds = time.time() - experiment_start_time
            elapsed_formatted = format_elapsed_time(elapsed_seconds)
            
            # Query VNA data
            temp_values = vna.query_ascii_values('CALCulate:DATA:SNP? 1')
            total_len = len(temp_values)
            points_per_var = total_len // 3
            
            freq = temp_values[0:points_per_var]
            real = temp_values[points_per_var:2*points_per_var]
            imag = temp_values[2*points_per_var:3*points_per_var]
            
            # Create filename
            filename = f"sweep_{sweep_num:03d}_{current_temp:.1f}C_{timestamp_str}.csv"
            file_path = os.path.join(sweep_dir, filename)
            
            # Write to CSV
            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = ['Point_Index', 'Sweep_Timestamp', 'Temperature_C', 'Frequency_Hz', 'Real_S11', 'Imag_S11']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for i in range(points_per_var):
                    writer.writerow({
                        'Point_Index': i + 1,
                        'Sweep_Timestamp': collection_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'Temperature_C': current_temp,
                        'Frequency_Hz': freq[i],
                        'Real_S11': real[i],
                        'Imag_S11': imag[i]
                    })
            
            print(f"  [VNA] {collection_time.strftime('%H:%M:%S')} | +{elapsed_formatted} | Sweep #{sweep_num} @ {current_temp:.2f}°C → {filename}")
            
            # Wait for next interval
            time.sleep(VNA_SWEEP_INTERVAL)
            
        except Exception as e:
            if experiment_running:
                print(f"⚠️ VNA sweep error: {e}")
            time.sleep(5)

# --- 10. Main Data Collection Loop ---
def collect_data(device, vna, temps, ramp_rate, exp_dir, sweep_dir, use_overshoot, overshoot_amount):
    """Main data collection orchestration"""
    global experiment_running, experiment_start_time, vna_sweep_count, keyboard_interrupt_count
    
    # Reset experiment-specific globals
    vna_sweep_count = 0
    experiment_running = True
    keyboard_interrupt_count = 0
    
    # Create temperature log file
    temp_log_file = os.path.join(exp_dir, "temperature_log.csv")
    
    # Metadata storage
    metadata = {
        'experiment_start': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'temperature_targets': temps,
        'ramp_mode': 'Controlled Linear' if ramp_rate else 'Fast PID',
        'ramp_rate_C_per_min': ramp_rate if ramp_rate else 'N/A',
        'control_mode': 'Normal Set Mode (PID)',
        'overshoot_enabled': use_overshoot,
        'overshoot_amount_C': overshoot_amount if use_overshoot else 'N/A',
        'sweeps': []
    }
    
    # Current temperature tracker for VNA thread
    current_temp_tracker = {'temp': device.get_temp()}
    
    def get_current_temp():
        return current_temp_tracker['temp']
    
    # Start VNA sweep thread
    vna_thread = threading.Thread(target=vna_sweep_thread, args=(vna, sweep_dir, get_current_temp), daemon=True)
    vna_thread.start()
    
    # Open temperature log file
    with open(temp_log_file, 'w', newline='') as csvfile:
        fieldnames = ['Timestamp', 'Elapsed_Time_s', 'Target_Temp_C', 'Sensor_Temp_1_C', 'Sensor_Temp_2_C', 'Current_Step']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        print(f"\n🚀 Starting data collection. Temperature log: {temp_log_file}")
        print(f"📊 VNA sweeps will occur every {VNA_SWEEP_INTERVAL} seconds")
        if use_overshoot:
            print(f"🎯 Overshoot mode enabled: ±{overshoot_amount}°C temporary offset\n")
        else:
            print()
        
        start_time = time.time()
        experiment_start_time = start_time  # Set global start time for VNA thread
        
        experiment_completed = False
        
        try:
            for step_idx, target_temp in enumerate(temps, 1):
                print(f"\n{'='*60}")
                print(f"STEP {step_idx}/{len(temps)}: Ramping to {target_temp}°C")
                print(f"{'='*60}")
                
                # Ramp to temperature (handles both fast and controlled modes)
                ramp_to_temperature(
                    device, 
                    target_temp, 
                    ramp_rate, 
                    current_temp_tracker, 
                    writer, 
                    csvfile, 
                    start_time, 
                    step_idx
                )
                
                # Wait for stability (with optional overshoot)
                wait_for_stability(
                    device, 
                    target_temp, 
                    use_overshoot, 
                    overshoot_amount,
                    current_temp_tracker,
                    writer,
                    csvfile,
                    start_time,
                    step_idx
                )
                
                # Log final stable temperature
                current_temp = device.get_temp()
                current_temp_tracker['temp'] = current_temp
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                elapsed_time = round(time.time() - start_time)
                
                writer.writerow({
                    'Timestamp': current_time,
                    'Elapsed_Time_s': elapsed_time,
                    'Target_Temp_C': target_temp,
                    'Sensor_Temp_1_C': current_temp,
                    'Sensor_Temp_2_C': device.get_temp2(),
                    'Current_Step': step_idx
                })
                csvfile.flush()
                
                print(f"✅ Step {step_idx} complete at {current_temp:.2f}°C. Moving to next step...\n")
            
            # All steps completed successfully
            experiment_completed = True
            print(f"\n{'='*60}")
            print(f"✅ All temperature steps completed!")
            total_elapsed = time.time() - start_time
            print(f"⏱️  Total experiment time: {format_elapsed_time(total_elapsed)}")
            print(f"{'='*60}\n")
            
        except KeyboardInterrupt:
            print("\n⚠️ Experiment interrupted by user (Ctrl+C).")
            keyboard_interrupt_count = 1
        
        finally:
            experiment_running = False
            
            # Set to idle (0 output)
            try:
                device.set_idle()
                print("🔌 TC-720 set to idle mode")
            except:
                pass
            
            time.sleep(2)  # Allow VNA thread to finish
            
            # Save metadata
            metadata['experiment_end'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            metadata['total_sweeps'] = vna_sweep_count
            metadata['completed'] = experiment_completed
            
            metadata_file = os.path.join(exp_dir, "metadata.json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            print(f"\n📁 Experiment data saved to: {exp_dir}")
            print(f"📊 Total VNA sweeps collected: {vna_sweep_count}")
            print(f"📋 Metadata saved to: {metadata_file}")
    
    return experiment_completed

# --- 11. Main Execution ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print("Multi-Temperature Data Collection (PID Control Mode)")
    print("With Temperature Overshoot for Phase Transitions")
    print("REPEATABLE EXPERIMENTS MODE")
    print("="*60)
    
    # Initialize devices once at startup
    print("\n🔧 Initializing devices...")
    tc720, vna = initialize_devices()
    if tc720 is None or vna is None:
        print("❌ Device initialization failed. Exiting.")
        exit(1)
    
    experiment_number = 0
    continue_experiments = True
    
    while continue_experiments:
        experiment_number += 1
        
        print(f"\n{'='*60}")
        print(f"EXPERIMENT #{experiment_number}")
        print(f"{'='*60}")
        
        # Get user inputs for this experiment
        temps, ramp_rate, use_overshoot, overshoot_amount = get_temperature_profile()
        
        # Setup directories for this experiment
        exp_dir, sweep_dir, timestamp = setup_experiment_directory()
        print(f"\n📁 Experiment directory: {exp_dir}")
        
        # Display configuration summary
        print(f"\n📋 Configuration Summary:")
        print(f"   Temperature targets: {temps}")
        print(f"   Ramping mode: {'Controlled Linear (' + str(ramp_rate) + '°C/min)' if ramp_rate else 'Fast PID'}")
        print(f"   Overshoot mode: {'Enabled (±' + str(overshoot_amount) + '°C)' if use_overshoot else 'Disabled'}")
        print(f"   Stability criteria: ±{TEMP_TOLERANCE}°C for {STABILITY_DURATION}s")
        print(f"   VNA sweep interval: {VNA_SWEEP_INTERVAL}s")
        
        input("\nPress Enter to start this experiment...")
        
        # Start data collection
        try:
            experiment_completed = collect_data(tc720, vna, temps, ramp_rate, exp_dir, sweep_dir, use_overshoot, overshoot_amount)
            
            # After experiment ends, ask if user wants to continue
            print(f"\n{'='*60}")
            print(f"EXPERIMENT #{experiment_number} FINISHED")
            print(f"{'='*60}")
            
            if keyboard_interrupt_count > 0:
                # Keyboard interrupt occurred - ask with Ctrl+C option
                print("\n⚠️ Previous experiment was interrupted.")
                print("Options:")
                print("  • Press Enter to start a NEW experiment")
                print("  • Press Ctrl+C again to EXIT the program")
                
                try:
                    input()
                    # User pressed Enter - continue to next experiment
                    keyboard_interrupt_count = 0
                    continue
                except KeyboardInterrupt:
                    # Second Ctrl+C - exit
                    print("\n\n⚠️ Second interrupt received. Exiting program...")
                    continue_experiments = False
            else:
                # Normal completion - simple prompt
                print("\nOptions:")
                print("  • Press Enter to start a NEW experiment")
                print("  • Press Ctrl+C to EXIT the program")
                
                try:
                    input()
                    # User pressed Enter - continue to next experiment
                    continue
                except KeyboardInterrupt:
                    # Ctrl+C - exit
                    print("\n\n⚠️ Exiting program...")
                    continue_experiments = False
        
        except Exception as e:
            print(f"\n❌ Unexpected error during experiment: {e}")
            print("Would you like to continue with a new experiment? (Press Enter to continue, Ctrl+C to exit)")
            try:
                input()
                continue
            except KeyboardInterrupt:
                print("\n\n⚠️ Exiting program...")
                continue_experiments = False
    
    # Cleanup
    try:
        if vna:
            vna.close()
            print("🔌 VNA connection closed")
        if tc720:
            tc720.set_idle()
            print("🔌 TC-720 set to idle")
    except:
        pass
    
    print(f"\n✅ Program terminated. Total experiments run: {experiment_number}")
    print("="*60)