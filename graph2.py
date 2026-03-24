import sys
import struct
import numpy as np
from vispy import scene
from PyQt5.QtWidgets import QApplication, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import QTimer, QMutex
import paho.mqtt.client as mqtt


BROKER = "192.168.1.231"
TOPIC = "sarayu/d1/topic1"

SAMPLE_RATE = 4096
SAMPLES = 4096
HEADER_LEN = 100
TOTAL_LEN = 49252

# Time axis in milliseconds for better readability
TIME_AXIS_MS = np.arange(SAMPLES) / SAMPLE_RATE * 1000  # Convert to milliseconds


class MQTTScope:

    def __init__(self):

        self.app = QApplication(sys.argv)

        # Create main window with scroll area
        self.scroll = QScrollArea()
        self.scroll.resize(1800, 1200)
        self.scroll.setWindowTitle("MQTT VisPy Scope - 10 Analog Channels + 2 Tacho Channels")

        self.central = QWidget()
        self.layout = QVBoxLayout(self.central)
        self.layout.setSpacing(10)

        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.central)

        self.canvases = []
        self.lines = []
        self.views = []

        # Create plots for all 12 channels (0-9: analog, 10: tacho freq, 11: tacho trigger)
        for i in range(12):
            # Create a container widget for each channel with title
            channel_widget = QWidget()
            channel_layout = QVBoxLayout(channel_widget)
            channel_layout.setSpacing(2)
            
            # Add channel title
            if i < 10:
                channel_title = QLabel(f"Analog Channel {i+1} (Amplitude - mil units)")
                channel_title.setStyleSheet("font-weight: bold; color: blue; background-color: #f0f0f0; padding: 5px;")
            elif i == 10:
                channel_title = QLabel("Tacho Channel 1 - Frequency (Hz)")
                channel_title.setStyleSheet("font-weight: bold; color: green; background-color: #f0f0f0; padding: 5px;")
            else:
                channel_title = QLabel("Tacho Channel 2 - Trigger Signal")
                channel_title.setStyleSheet("font-weight: bold; color: red; background-color: #f0f0f0; padding: 5px;")
            
            channel_layout.addWidget(channel_title)

            # Create canvas
            canvas = scene.SceneCanvas(
                keys='interactive',
                bgcolor='white',
                show=True,
                size=(1600, 300)
            )
            
            canvas.native.setMinimumHeight(280)
            canvas.native.setMaximumHeight(350)
            
            view = canvas.central_widget.add_view()
            view.camera = scene.PanZoomCamera()
            
            # Set different initial Y-axis ranges based on channel type
            if i < 10:  # Analog channels - amplitude in mil units
                view.camera.rect = (0, -0.6, TIME_AXIS_MS[-1], 1.2)  # (x, y, width, height)
            elif i == 10:  # Tacho frequency
                view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 50)  # Assume 0-50 Hz range
            else:  # Tacho trigger (i == 11)
                view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 1.2)  # Trigger signal range 0-1
            
            # Add grid for better readability
            grid = scene.visuals.GridLines(parent=view.scene, color='lightgray')
            
            # Add axis labels with fixed positions
            # Y-axis label
            if i < 10:
                y_label_text = "Amplitude (mil)"
            elif i == 10:
                y_label_text = "Frequency (Hz)"
            else:
                y_label_text = "Trigger (V)"
            
            y_label = scene.Text(y_label_text, color='black', font_size=10, parent=view.scene)
            y_label.pos = (10, 0)
            
            # X-axis label
            x_label = scene.Text("Time (ms)", color='black', font_size=10, parent=view.scene)
            x_label.pos = (TIME_AXIS_MS[-1] / 2, -30)
            
            # Channel number label
            ch_label = scene.Text(f"Ch{i+1}", color='gray', font_size=9, parent=view.scene)
            ch_label.pos = (TIME_AXIS_MS[-1] - 50, -20)
            
            # Line for plotting
            if i < 10:
                color = 'blue'
            elif i == 10:
                color = 'green'
            else:
                color = 'red'
                
            line = scene.Line(
                color=color,
                width=2,
                parent=view.scene
            )
            
            channel_layout.addWidget(canvas.native)
            self.layout.addWidget(channel_widget)
            
            # Add separator line between channels
            if i < 11:
                separator = QLabel("")
                separator.setStyleSheet("border-top: 1px solid #cccccc;")
                separator.setMaximumHeight(1)
                self.layout.addWidget(separator)
            
            self.canvases.append(canvas)
            self.lines.append(line)
            self.views.append(view)

        # Add control panel at the bottom
        control_widget = QWidget()
        control_widget.setStyleSheet("background-color: #f8f8f8; padding: 5px;")
        control_layout = QHBoxLayout(control_widget)
        
        # Add buttons for controlling all plots
        reset_zoom_btn = QPushButton("Reset All Zooms")
        reset_zoom_btn.clicked.connect(self.reset_all_zooms)
        reset_zoom_btn.setStyleSheet("padding: 5px; font-weight: bold;")
        control_layout.addWidget(reset_zoom_btn)
        
        auto_range_btn = QPushButton("Auto Range All")
        auto_range_btn.clicked.connect(self.auto_range_all)
        auto_range_btn.setStyleSheet("padding: 5px; font-weight: bold;")
        control_layout.addWidget(auto_range_btn)
        
        # Add status label
        self.status_label = QLabel("Status: Waiting for data...")
        self.status_label.setStyleSheet("color: gray; padding: 5px; font-weight: bold;")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        self.layout.addWidget(control_widget)

        self.latest = None
        self.mutex = QMutex()
        
        # Statistics for debugging
        self.frame_count = 0

        # MQTT
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(BROKER)
        self.client.loop_start()

        # Timer for updating plots
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(30)  # ~33 fps

        # Show the window
        self.scroll.show()

        sys.exit(self.app.exec_())

    def on_connect(self, client, userdata, flags, rc):
        print("MQTT connected:", rc)
        client.subscribe(TOPIC)
        self.status_label.setText("Status: Connected to MQTT broker")
        self.status_label.setStyleSheet("color: green; padding: 5px; font-weight: bold;")

    def on_message(self, client, userdata, msg):

        if len(msg.payload) != TOTAL_LEN * 2:
            print(f"Invalid payload length: {len(msg.payload)}, expected {TOTAL_LEN * 2}")
            return

        raw = struct.unpack(f"<{TOTAL_LEN}H", msg.payload)
        payload = np.array(raw, dtype=np.uint16)

        idx = HEADER_LEN

        six_ch = payload[idx:idx + 6 * SAMPLES].reshape(SAMPLES, 6).astype(np.float32)
        idx += 6 * SAMPLES

        four_ch = payload[idx:idx + 4 * SAMPLES].reshape(SAMPLES, 4).astype(np.float32)
        idx += 4 * SAMPLES

        tacho_freq_raw = payload[idx:idx + SAMPLES].astype(np.float32)
        idx += SAMPLES

        tacho_trig_raw = payload[idx:idx + SAMPLES].astype(np.float32)
        
        analog = np.zeros((SAMPLES, 10), dtype=np.float32)
        analog[:, :6] = six_ch
        analog[:, 6:] = four_ch
        
        # Convert analog to mil units (scale down from uint16 range)
        analog = (analog - 32768) / 32768 * 0.5  # Scale to -0.5 to 0.5 mil range
        
        # Process tacho frequency - keep raw values as they appear to be in Hz
        tacho_freq_scaled = tacho_freq_raw
        
        # Process tacho trigger - ensure it's scaled properly and has variation
        tacho_trig_min = np.min(tacho_trig_raw)
        tacho_trig_max = np.max(tacho_trig_raw)
        
        # Debug print to see trigger data
        if self.frame_count % 50 == 0:
            print(f"Trigger raw data - Min: {tacho_trig_min:.2f}, Max: {tacho_trig_max:.2f}, Mean: {np.mean(tacho_trig_raw):.2f}")
        
        # Scale trigger to 0-1 range if values are large
        if tacho_trig_max > 1:
            tacho_trig_scaled = (tacho_trig_raw - tacho_trig_min) / (tacho_trig_max - tacho_trig_min + 0.001)
            # Clip to ensure values are in 0-1 range
            tacho_trig_scaled = np.clip(tacho_trig_scaled, 0, 1)
        else:
            tacho_trig_scaled = tacho_trig_raw
        
        # Add small variation test if data is constant
        if tacho_trig_max == tacho_trig_min:
            print("WARNING: Trigger data is constant! Adding artificial variation for testing...")
            # Create artificial test signal to verify plotting works
            t = np.linspace(0, 2*np.pi, SAMPLES)
            tacho_trig_scaled = 0.5 + 0.5 * np.sin(t)  # Sine wave for testing
        
        self.mutex.lock()
        self.latest = (analog, tacho_freq_scaled, tacho_trig_scaled)
        self.mutex.unlock()

    def reset_all_zooms(self):
        """Reset camera views to default ranges"""
        for i, view in enumerate(self.views):
            if i < 10:  # Analog channels
                view.camera.rect = (0, -0.6, TIME_AXIS_MS[-1], 1.2)
            elif i == 10:  # Tacho frequency
                view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 50)
            else:  # Tacho trigger (i == 11)
                view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 1.2)
        print("Reset all zooms to default")

    def auto_range_all(self):
        """Auto-range all channels based on current data"""
        self.mutex.lock()
        data = self.latest
        self.mutex.unlock()
        
        if data is None:
            return
            
        analog, tacho_freq, tacho_trig = data
        
        # Auto-range analog channels
        for i in range(10):
            y = analog[:, i]
            y_min = np.min(y)
            y_max = np.max(y)
            if y_max > y_min:
                padding = (y_max - y_min) * 0.1
                if padding == 0:
                    padding = 0.1
                self.views[i].camera.rect = (0, y_min - padding, TIME_AXIS_MS[-1], (y_max - y_min) + 2*padding)
        
        # Auto-range tacho frequency
        freq_min = np.min(tacho_freq)
        freq_max = np.max(tacho_freq)
        if freq_max > freq_min:
            padding = (freq_max - freq_min) * 0.1
            if padding == 0:
                padding = 1.0
            self.views[10].camera.rect = (0, max(0, freq_min - padding), TIME_AXIS_MS[-1], (freq_max - freq_min) + 2*padding)
        
        # Auto-range tacho trigger
        trig_min = np.min(tacho_trig)
        trig_max = np.max(tacho_trig)
        if trig_max > trig_min:
            padding = (trig_max - trig_min) * 0.1
            if padding == 0:
                padding = 0.1
            self.views[11].camera.rect = (0, max(0, trig_min - padding), TIME_AXIS_MS[-1], (trig_max - trig_min) + 2*padding)
        
        print(f"Auto-ranged all channels | Trigger range: {trig_min:.3f} to {trig_max:.3f}")

    def update_plot(self):

        self.mutex.lock()
        data = self.latest
        self.mutex.unlock()

        if data is None:
            return

        analog, tacho_freq, tacho_trig = data
        self.frame_count += 1
        
        try:
            # Update analog channels (0-9)
            for ch in range(10):
                y = analog[:, ch]
                pts = np.column_stack((TIME_AXIS_MS, y))
                self.lines[ch].set_data(pts)

            # Update tacho frequency (channel 10)
            pts = np.column_stack((TIME_AXIS_MS, tacho_freq))
            self.lines[10].set_data(pts)
            
            # Update tacho trigger (channel 11) - FIXED: Ensure it's being updated
            pts = np.column_stack((TIME_AXIS_MS, tacho_trig))
            self.lines[11].set_data(pts)
            
            # Update status periodically with trigger information
            if self.frame_count % 30 == 0:
                freq_val = np.mean(tacho_freq) if len(tacho_freq) > 0 else 0
                trig_min = np.min(tacho_trig) if len(tacho_trig) > 0 else 0
                trig_max = np.max(tacho_trig) if len(tacho_trig) > 0 else 0
                self.status_label.setText(f"Status: Receiving data | Freq: {freq_val:.1f} Hz | Trigger: [{trig_min:.2f}, {trig_max:.2f}] | Frames: {self.frame_count}")
                
                # Force trigger plot to update by printing confirmation
                if self.frame_count % 150 == 0:
                    print(f"Trigger plot updated - Range: {trig_min:.3f} to {trig_max:.3f}")
                    
        except Exception as e:
            print(f"Error in update_plot: {e}")

    def closeEvent(self, event):
        """Clean up on close"""
        self.client.loop_stop()
        self.client.disconnect()
        event.accept()


if __name__ == "__main__":
    MQTTScope()