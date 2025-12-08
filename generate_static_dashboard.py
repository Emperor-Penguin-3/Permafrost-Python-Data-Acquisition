"""
VNA Static Dashboard Generator
===============================
Creates standalone HTML files that you can open directly in your browser.
No server needed - just double-click the HTML file!

FIXED: Slider positioning issue - now appears below all graphs
"""

import plotly.graph_objs as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
import pandas as pd
import os
import glob
from datetime import datetime
import json

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS_DIR = os.path.join(SCRIPT_DIR, "experiments")
DASHBOARDS_DIR = os.path.join(SCRIPT_DIR, "dashboards")

def get_experiment_directories():
    """Find all experiment directories in the experiments folder"""
    # First check if experiments folder exists
    if not os.path.exists(EXPERIMENTS_DIR):
        # Fall back to old structure (experiment_* in main folder)
        pattern = os.path.join(SCRIPT_DIR, "experiment_*")
        dirs = glob.glob(pattern)
        dirs = [d for d in dirs if os.path.isdir(d)]
    else:
        # New structure: look inside experiments folder
        pattern = os.path.join(EXPERIMENTS_DIR, "experiment_*")
        dirs = glob.glob(pattern)
        dirs = [d for d in dirs if os.path.isdir(d)]
    
    dirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return dirs

def load_experiment_metadata(exp_dir):
    """Load metadata.json"""
    metadata_path = os.path.join(exp_dir, "metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def load_temperature_log(exp_dir):
    """Load temperature log CSV"""
    temp_log_path = os.path.join(exp_dir, "temperature_log.csv")
    if os.path.exists(temp_log_path):
        try:
            return pd.read_csv(temp_log_path)
        except:
            return None
    return None

def get_sweep_files(exp_dir):
    """Get all sweep CSV files"""
    sweep_dir = os.path.join(exp_dir, "sweep_data")
    if not os.path.exists(sweep_dir):
        return []
    
    sweep_files = glob.glob(os.path.join(sweep_dir, "sweep_*.csv"))
    sweep_files.sort()
    return sweep_files

def parse_sweep_filename(filename):
    """Extract sweep number and temperature from filename"""
    basename = os.path.basename(filename)
    parts = basename.split('_')
    
    try:
        sweep_num = int(parts[1])
        temp_str = parts[2].replace('C', '')
        temp = float(temp_str)
        return sweep_num, temp
    except:
        return None, None

def load_sweep_data(filepath):
    """Load a single sweep CSV file"""
    try:
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def create_dashboard_for_experiment(exp_dir):
    """Create a complete interactive dashboard for one experiment"""
    
    exp_name = os.path.basename(exp_dir)
    print(f"\n📊 Processing: {exp_name}")
    
    metadata = load_experiment_metadata(exp_dir)
    sweep_files = get_sweep_files(exp_dir)
    
    if not sweep_files:
        print(f"   ⚠️  No sweep files found. Skipping.")
        return None
    
    print(f"   Found {len(sweep_files)} sweeps")
    
    # Parse all sweep data
    sweep_data = []
    for filepath in sweep_files:
        sweep_num, temp = parse_sweep_filename(filepath)
        if sweep_num is not None and temp is not None:
            df = load_sweep_data(filepath)
            if df is not None and not df.empty:
                sweep_data.append({
                    'sweep_num': sweep_num,
                    'temperature': temp,
                    'filepath': filepath,
                    'data': df
                })
    
    if not sweep_data:
        print(f"   ⚠️  Could not load sweep data. Skipping.")
        return None
    
    sweep_data.sort(key=lambda x: x['temperature'])
    
    # Create the main figure with subplots
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            'Real S11 vs Frequency',
            'Imaginary S11 vs Frequency',
            'Temperature Profile Over Time',
            'All Sweeps Overview (Real S11)',
            'All Sweeps Overview (Imaginary S11)',
            ''  # Empty placeholder for 2x3 grid
        ),
        specs=[[{'type': 'scatter'}, {'type': 'scatter'}, {'type': 'scatter'}],
               [{'type': 'scatter'}, {'type': 'scatter'}, {'type': 'scatter'}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )
    
    # Create frames for slider animation
    frames = []
    
    for idx, sweep in enumerate(sweep_data):
        df = sweep['data']
        
        # Frame for this temperature
        frame_data = [
            # Real S11
            go.Scatter(
                x=df['Frequency_Hz'],
                y=df['Real_S11'],
                mode='lines',
                line=dict(color='#e74c3c', width=2),
                name=f"Real S11 @ {sweep['temperature']:.1f}°C",
                hovertemplate='Freq: %{x:.2e} Hz<br>Real S11: %{y:.6f}<extra></extra>'
            ),
            # Imaginary S11
            go.Scatter(
                x=df['Frequency_Hz'],
                y=df['Imag_S11'],
                mode='lines',
                line=dict(color='#3498db', width=2),
                name=f"Imag S11 @ {sweep['temperature']:.1f}°C",
                hovertemplate='Freq: %{x:.2e} Hz<br>Imag S11: %{y:.6f}<extra></extra>'
            )
        ]
        
        frames.append(go.Frame(
            data=frame_data,
            name=str(sweep['temperature']),
            layout=go.Layout(
                title_text=f"VNA Sweep @ {sweep['temperature']:.2f}°C - Sweep #{sweep['sweep_num']}"
            )
        ))
    
    # Add initial data (first sweep)
    first_sweep = sweep_data[0]
    df_first = first_sweep['data']
    
    # Row 1, Col 1: Real S11
    fig.add_trace(
        go.Scatter(
            x=df_first['Frequency_Hz'],
            y=df_first['Real_S11'],
            mode='lines',
            line=dict(color='#e74c3c', width=2),
            name='Real S11',
            hovertemplate='Freq: %{x:.2e} Hz<br>Real S11: %{y:.6f}<extra></extra>'
        ),
        row=1, col=1
    )
    
    # Row 1, Col 2: Imaginary S11
    fig.add_trace(
        go.Scatter(
            x=df_first['Frequency_Hz'],
            y=df_first['Imag_S11'],
            mode='lines',
            line=dict(color='#3498db', width=2),
            name='Imag S11',
            hovertemplate='Freq: %{x:.2e} Hz<br>Imag S11: %{y:.6f}<extra></extra>'
        ),
        row=1, col=2
    )
    
    # Row 1, Col 3: Temperature vs Time
    df_temp = load_temperature_log(exp_dir)
    if df_temp is not None and not df_temp.empty:
        df_temp['Timestamp'] = pd.to_datetime(df_temp['Timestamp'])
        
        fig.add_trace(
            go.Scatter(
                x=df_temp['Timestamp'],
                y=df_temp['Sensor_Temp_1_C'],
                mode='lines',
                line=dict(color='#e74c3c', width=2),
                name='Sensor 1',
                hovertemplate='Time: %{x}<br>Temp: %{y:.2f}°C<extra></extra>'
            ),
            row=1, col=3
        )
        
        if 'Target_Temp_C' in df_temp.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_temp['Timestamp'],
                    y=df_temp['Target_Temp_C'],
                    mode='lines',
                    line=dict(color='#2ecc71', width=2, dash='dash'),
                    name='Target',
                    hovertemplate='Time: %{x}<br>Target: %{y:.2f}°C<extra></extra>'
                ),
                row=1, col=3
            )
    
    # Row 2, Col 1: Overview of all sweeps (Real S11)
    # Show every 5th sweep to avoid overcrowding
    step = max(1, len(sweep_data) // 20)
    for idx, sweep in enumerate(sweep_data[::step]):
        df = sweep['data']
        
        # Color based on temperature (cool to warm)
        color_val = (sweep['temperature'] - sweep_data[0]['temperature']) / \
                    (sweep_data[-1]['temperature'] - sweep_data[0]['temperature']) if len(sweep_data) > 1 else 0
        color = f"rgb({int(color_val*255)}, {int((1-color_val)*100)}, {int((1-color_val)*255)})"
        
        fig.add_trace(
            go.Scatter(
                x=df['Frequency_Hz'],
                y=df['Real_S11'],
                mode='lines',
                line=dict(color=color, width=1),
                name=f"{sweep['temperature']:.1f}°C",
                hovertemplate=f"Temp: {sweep['temperature']:.1f}°C<br>Freq: %{{x:.2e}} Hz<br>Real S11: %{{y:.6f}}<extra></extra>",
                showlegend=False
            ),
            row=2, col=1
        )
    
    # Row 2, Col 2: Overview of all sweeps (Imaginary S11)
    for idx, sweep in enumerate(sweep_data[::step]):
        df = sweep['data']
        
        # Color based on temperature (cool to warm) - same as Real S11
        color_val = (sweep['temperature'] - sweep_data[0]['temperature']) / \
                    (sweep_data[-1]['temperature'] - sweep_data[0]['temperature']) if len(sweep_data) > 1 else 0
        color = f"rgb({int(color_val*255)}, {int((1-color_val)*100)}, {int((1-color_val)*255)})"
        
        fig.add_trace(
            go.Scatter(
                x=df['Frequency_Hz'],
                y=df['Imag_S11'],
                mode='lines',
                line=dict(color=color, width=1),
                name=f"{sweep['temperature']:.1f}°C",
                hovertemplate=f"Temp: {sweep['temperature']:.1f}°C<br>Freq: %{{x:.2e}} Hz<br>Imag S11: %{{y:.6f}}<extra></extra>",
                showlegend=False
            ),
            row=2, col=2
        )
    
    # Add frames to figure
    fig.frames = frames
    
    # Create slider - FIXED POSITIONING (above all graphs)
    temps = [s['temperature'] for s in sweep_data]
    sliders = [{
        'active': 0,
        'yanchor': 'bottom',
        'y': 1.02,  # FIXED: Positioned above all graphs
        'xanchor': 'left',
        'x': 0.05,
        'currentvalue': {
            'prefix': 'Temperature: ',
            'suffix': '°C',
            'visible': True,
            'xanchor': 'center',
            'font': {'size': 16}
        },
        'pad': {'b': 50, 't': 10},  # FIXED: Bottom padding to separate from graphs
        'len': 0.9,
        'transition': {'duration': 300},
        'steps': [
            {
                'args': [
                    [str(sweep['temperature'])],
                    {'frame': {'duration': 300, 'redraw': True},
                     'mode': 'immediate',
                     'transition': {'duration': 300}}
                ],
                'method': 'animate',
                'label': f"{sweep['temperature']:.1f}°C"
            }
            for sweep in sweep_data
        ]
    }]
    
    # Update layout
    title_text = f"VNA Temperature Sweep Analysis: {exp_name}"
    if metadata and 'experiment_start' in metadata:
        title_text += f"<br><sub>Started: {metadata['experiment_start']}</sub>"
    
    fig.update_layout(
        title_text=title_text,
        title_font_size=20,
        height=1000,  # FIXED: Increased from 900 to 1000 to accommodate slider above
        showlegend=True,
        hovermode='closest',
        sliders=sliders,
        template='plotly_white',
        margin=dict(t=150)  # FIXED: Added top margin for slider
    )
    
    # Update axes labels
    fig.update_xaxes(title_text="Frequency (Hz)", row=1, col=1)
    fig.update_yaxes(title_text="Real S11", row=1, col=1)
    
    fig.update_xaxes(title_text="Frequency (Hz)", row=1, col=2)
    fig.update_yaxes(title_text="Imaginary S11", row=1, col=2)
    
    fig.update_xaxes(title_text="Time", row=1, col=3)
    fig.update_yaxes(title_text="Temperature (°C)", row=1, col=3)
    
    fig.update_xaxes(title_text="Frequency (Hz)", row=2, col=1)
    fig.update_yaxes(title_text="Real S11", row=2, col=1)
    
    fig.update_xaxes(title_text="Frequency (Hz)", row=2, col=2)
    fig.update_yaxes(title_text="Imaginary S11", row=2, col=2)
    
    # Save to HTML in two locations:
    # 1. In the dashboards folder (organized collection)
    # 2. Inside the experiment folder itself (for easy access)
    
    # Create dashboards folder if it doesn't exist
    os.makedirs(DASHBOARDS_DIR, exist_ok=True)
    
    output_filename = f"{exp_name}_dashboard.html"
    
    # Location 1: Centralized dashboards folder
    output_path_central = os.path.join(DASHBOARDS_DIR, output_filename)
    
    # Location 2: Inside the experiment folder
    output_path_local = os.path.join(exp_dir, "dashboard.html")
    
    # Create HTML with plotly
    html_string = f"""
    <html>
    <head>
        <title>{exp_name} - VNA Dashboard</title>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f8f9fa;
            }}
            .info-box {{
                background-color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .info-box h2 {{
                margin-top: 0;
                color: #2c3e50;
            }}
            .instructions {{
                background-color: #fff3cd;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
                border-left: 4px solid #ffc107;
            }}
        </style>
    </head>
    <body>
        <div class="instructions">
            <h3>📊 How to Use This Dashboard:</h3>
            <ul>
                <li><strong>Use the slider at the top</strong> to navigate through different temperature points</li>
                <li><strong>Hover over any plot</strong> to see detailed values</li>
                <li><strong>Click and drag</strong> to zoom into specific regions</li>
                <li><strong>Double-click</strong> to reset the zoom</li>
                <li><strong>Click legend items</strong> to show/hide traces</li>
            </ul>
        </div>
        
        <div class="info-box">
            <h2>Experiment Information</h2>
            <p><strong>Directory:</strong> {exp_name}</p>
            {'<p><strong>Started:</strong> ' + metadata['experiment_start'] + '</p>' if metadata and 'experiment_start' in metadata else ''}
            {'<p><strong>Temperature Targets:</strong> ' + str(metadata['temperature_targets']) + ' °C</p>' if metadata and 'temperature_targets' in metadata else ''}
            {'<p><strong>Ramp Mode:</strong> ' + metadata['ramp_mode'] + '</p>' if metadata and 'ramp_mode' in metadata else ''}
            <p><strong>Total Sweeps:</strong> {len(sweep_data)}</p>
            <p><strong>Temperature Range:</strong> {temps[0]:.1f}°C to {temps[-1]:.1f}°C</p>
        </div>
    """
    
    # Add the plotly figure
    fig_html = pyo.plot(fig, output_type='div', include_plotlyjs='cdn')
    html_string += fig_html
    html_string += """
    </body>
    </html>
    """
    
    # Write to both locations
    with open(output_path_central, 'w', encoding='utf-8') as f:
        f.write(html_string)
    
    with open(output_path_local, 'w', encoding='utf-8') as f:
        f.write(html_string)
    
    print(f"   ✅ Created: {output_filename}")
    print(f"      📁 Centralized: dashboards/{output_filename}")
    print(f"      📁 Local: {exp_name}/dashboard.html")
    
    return output_path_central

def main():
    """Main function to generate dashboards for all experiments"""
    
    print("\n" + "="*70)
    print("🌡️  VNA Static Dashboard Generator")
    print("="*70)
    print(f"\n📁 Script directory: {SCRIPT_DIR}")
    
    # Check folder structure
    if os.path.exists(EXPERIMENTS_DIR):
        print(f"📁 Experiments folder: {EXPERIMENTS_DIR}")
    else:
        print(f"📁 Searching in main directory (old structure)")
    
    exp_dirs = get_experiment_directories()
    
    if not exp_dirs:
        print("\n❌ No experiment directories found!")
        print("   Make sure you have:")
        print("   • experiments/experiment_*/ folders (new structure)")
        print("   • OR experiment_*/ folders in main directory (old structure)")
        return
    
    print(f"\n✅ Found {len(exp_dirs)} experiment directories")
    print(f"\n📂 HTML dashboards will be saved in two locations:")
    print(f"   1. dashboards/ folder (organized collection)")
    print(f"   2. Inside each experiment folder (for quick access)")
    print("\nGenerating HTML dashboards...")
    
    created_files = []
    for exp_dir in exp_dirs:
        result = create_dashboard_for_experiment(exp_dir)
        if result:
            created_files.append(result)
    
    print("\n" + "="*70)
    print(f"✅ Generated {len(created_files)} dashboard(s)")
    print("="*70)
    
    if created_files:
        print(f"\n📂 All dashboards are in: {DASHBOARDS_DIR}")
        print(f"\n💡 Two ways to access dashboards:")
        print(f"   1. Go to 'dashboards' folder and open any HTML file")
        print(f"   2. Go to any experiment folder and open 'dashboard.html'")
        
        print(f"\n📊 Generated dashboards:")
        for file in created_files:
            print(f"   • {os.path.basename(file)}")
        
        # Try to open the most recent one
        import webbrowser
        print(f"\n🌐 Opening most recent dashboard in your browser...")
        try:
            webbrowser.open('file://' + created_files[0])
        except:
            pass
    
    print("\n")

if __name__ == '__main__':
    main()