import sys
import struct
import numpy as np
from PyQt5.QtWidgets import (QApplication, QScrollArea, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QGridLayout)
from PyQt5.QtCore import QTimer, QMutex
from PyQt5.QtGui import QColor
import pyqtgraph as pg
import paho.mqtt.client as mqtt

# Set PyQtGraph options for better performance
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

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
        self.scroll.setWindowTitle("MQTT PyQtGraph Scope - 10 Analog Channels + 2 Tacho Channels")

        self.central = QWidget()
        self.layout = QVBoxLayout(self.central)
        self.layout.setSpacing(10)

        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.central)

        self.plots = []
        self.curves = []
        self.plot_widgets = []

        # Create plots for all 12 channels (0-9: analog, 10: tacho freq, 11: tacho trigger)
        for i in range(12):
            # Create a container widget for each channel with title
            channel_widget = QWidget()
            channel_layout = QVBoxLayout(channel_widget)
            channel_layout.setSpacing(2)
            channel_layout.setContentsMargins(5, 5, 5, 5)
            
            # Add channel title
            if i < 10:
                channel_title = QLabel(f"Analog Channel {i+1} (Amplitude - mil units)")
                channel_title.setStyleSheet("font-weight: bold; color: #0066cc; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
            elif i == 10:
                channel_title = QLabel("Tacho Channel 1 - Frequency (Hz)")
                channel_title.setStyleSheet("font-weight: bold; color: #00aa00; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
            else:
                channel_title = QLabel("Tacho Channel 2 - Trigger Signal")
                channel_title.setStyleSheet("font-weight: bold; color: #cc0000; background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
            
            channel_layout.addWidget(channel_title)

            # Create plot widget
            plot_widget = pg.PlotWidget()
            plot_widget.setMinimumHeight(280)
            plot_widget.setMaximumHeight(350)
            plot_widget.setLabel('left', self.get_y_label(i))
            plot_widget.setLabel('bottom', 'Time (ms)')
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            
            # Set colors based on channel type
            if i < 10:
                pen_color = pg.mkColor('#0066cc')
            elif i == 10:
                pen_color = pg.mkColor('#00aa00')
            else:
                pen_color = pg.mkColor('#cc0000')
            
            pen = pg.mkPen(pen_color, width=2)
            curve = plot_widget.plot(TIME_AXIS_MS, np.zeros(SAMPLES), pen=pen)
            
            # Set different initial Y-axis ranges based on channel type
            if i < 10:  # Analog channels - amplitude in mil units
                plot_widget.setYRange(-0.6, 0.6)
                plot_widget.setXRange(0, TIME_AXIS_MS[-1])
            elif i == 10:  # Tacho frequency
                plot_widget.setYRange(0, 50)
                plot_widget.setXRange(0, TIME_AXIS_MS[-1])
            else:  # Tacho trigger (i == 11)
                plot_widget.setYRange(0, 1.2)
                plot_widget.setXRange(0, TIME_AXIS_MS[-1])
            
            # Add legend for channel number
            legend_text = pg.TextItem(text=f"Ch{i+1}", color=(100, 100, 100), anchor=(1, 1))
            legend_text.setPos(TIME_AXIS_MS[-1] - 50, plot_widget.viewRect().bottom() - 20)
            plot_widget.addItem(legend_text)
            
            # Enable auto-range button for individual plots
            auto_range_btn = QPushButton("Auto Range")
            auto_range_btn.setMaximumWidth(100)
            auto_range_btn.clicked.connect(lambda checked, ch=i: self.auto_range_single(ch))
            
            # Add button to the channel layout
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            button_layout.addWidget(auto_range_btn)
            channel_layout.addLayout(button_layout)
            
            channel_layout.addWidget(plot_widget)
            self.layout.addWidget(channel_widget)
            
            # Add separator line between channels
            if i < 11:
                separator = QLabel("")
                separator.setStyleSheet("border-top: 1px solid #cccccc;")
                separator.setMaximumHeight(1)
                self.layout.addWidget(separator)
            
            self.plots.append(plot_widget)
            self.curves.append(curve)
            self.plot_widgets.append(plot_widget)

        # Add control panel at the bottom
        control_widget = QWidget()
        control_widget.setStyleSheet("background-color: #f8f8f8; padding: 8px; border-top: 1px solid #cccccc;")
        control_layout = QHBoxLayout(control_widget)
        
        # Add buttons for controlling all plots
        reset_zoom_btn = QPushButton("Reset All Zooms")
        reset_zoom_btn.clicked.connect(self.reset_all_zooms)
        reset_zoom_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #e0e0e0;")
        reset_zoom_btn.setMinimumWidth(120)
        control_layout.addWidget(reset_zoom_btn)
        
        auto_range_btn = QPushButton("Auto Range All")
        auto_range_btn.clicked.connect(self.auto_range_all)
        auto_range_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #e0e0e0;")
        auto_range_btn.setMinimumWidth(120)
        control_layout.addWidget(auto_range_btn)
        
        # Add pause/resume button
        self.paused = False
        pause_btn = QPushButton("Pause")
        pause_btn.clicked.connect(self.toggle_pause)
        pause_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ffaa66;")
        pause_btn.setMinimumWidth(100)
        control_layout.addWidget(pause_btn)
        
        # Add status label
        self.status_label = QLabel("Status: Waiting for data...")
        self.status_label.setStyleSheet("color: #666666; padding: 8px; font-weight: bold; background-color: #f0f0f0; border-radius: 3px;")
        control_layout.addWidget(self.status_label)
        
        control_layout.addStretch()
        self.layout.addWidget(control_widget)

        self.latest = None
        self.mutex = QMutex()
        
        # Statistics for debugging
        self.frame_count = 0
        self.last_update_time = 0

        # MQTT
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(BROKER)
        self.client.loop_start()

        # Timer for updating plots (slower update for better performance)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)  # 20 fps for better performance

        # Show the window
        self.scroll.show()

        sys.exit(self.app.exec_())

    def get_y_label(self, channel):
        """Return appropriate Y-axis label based on channel"""
        if channel < 10:
            return "Amplitude (mil)"
        elif channel == 10:
            return "Frequency (Hz)"
        else:
            return "Trigger (V)"

    def on_connect(self, client, userdata, flags, rc):
        print("MQTT connected:", rc)
        client.subscribe(TOPIC)
        self.status_label.setText("Status: Connected to MQTT broker")
        self.status_label.setStyleSheet("color: green; padding: 5px; font-weight: bold; background-color: #e8f5e9; border-radius: 3px;")

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

    def toggle_pause(self):
        """Toggle pause/resume of plot updates"""
        self.paused = not self.paused
        sender = self.sender()
        if self.paused:
            sender.setText("Resume")
            sender.setStyleSheet("padding: 8px; font-weight: bold; background-color: #66cc66;")
            self.status_label.setText("Status: Paused")
        else:
            sender.setText("Pause")
            sender.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ffaa66;")
            self.status_label.setText("Status: Running")

    def reset_all_zooms(self):
        """Reset camera views to default ranges"""
        for i, plot in enumerate(self.plots):
            if i < 10:  # Analog channels
                plot.setYRange(-0.6, 0.6)
                plot.setXRange(0, TIME_AXIS_MS[-1])
            elif i == 10:  # Tacho frequency
                plot.setYRange(0, 50)
                plot.setXRange(0, TIME_AXIS_MS[-1])
            else:  # Tacho trigger (i == 11)
                plot.setYRange(0, 1.2)
                plot.setXRange(0, TIME_AXIS_MS[-1])
        print("Reset all zooms to default")

    def auto_range_single(self, channel):
        """Auto-range a single channel"""
        self.mutex.lock()
        data = self.latest
        self.mutex.unlock()
        
        if data is None:
            return
            
        analog, tacho_freq, tacho_trig = data
        
        try:
            if channel < 10:  # Analog channel
                y = analog[:, channel]
                y_min = np.min(y)
                y_max = np.max(y)
                if y_max > y_min:
                    padding = (y_max - y_min) * 0.1
                    if padding == 0:
                        padding = 0.1
                    self.plots[channel].setYRange(y_min - padding, y_max + padding)
            
            elif channel == 10:  # Tacho frequency
                freq_min = np.min(tacho_freq)
                freq_max = np.max(tacho_freq)
                if freq_max > freq_min:
                    padding = (freq_max - freq_min) * 0.1
                    if padding == 0:
                        padding = 1.0
                    self.plots[10].setYRange(max(0, freq_min - padding), freq_max + padding)
            
            else:  # Tacho trigger (channel 11)
                trig_min = np.min(tacho_trig)
                trig_max = np.max(tacho_trig)
                if trig_max > trig_min:
                    padding = (trig_max - trig_min) * 0.1
                    if padding == 0:
                        padding = 0.1
                    self.plots[11].setYRange(max(0, trig_min - padding), trig_max + padding)
            
            print(f"Auto-ranged channel {channel+1}")
            
        except Exception as e:
            print(f"Error auto-ranging channel {channel+1}: {e}")

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
                self.plots[i].setYRange(y_min - padding, y_max + padding)
        
        # Auto-range tacho frequency
        freq_min = np.min(tacho_freq)
        freq_max = np.max(tacho_freq)
        if freq_max > freq_min:
            padding = (freq_max - freq_min) * 0.1
            if padding == 0:
                padding = 1.0
            self.plots[10].setYRange(max(0, freq_min - padding), freq_max + padding)
        
        # Auto-range tacho trigger
        trig_min = np.min(tacho_trig)
        trig_max = np.max(tacho_trig)
        if trig_max > trig_min:
            padding = (trig_max - trig_min) * 0.1
            if padding == 0:
                padding = 0.1
            self.plots[11].setYRange(max(0, trig_min - padding), trig_max + padding)
        
        print(f"Auto-ranged all channels | Trigger range: {trig_min:.3f} to {trig_max:.3f}")

    def update_plot(self):
        """Update all plots with latest data"""
        if self.paused:
            return
            
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
                self.curves[ch].setData(TIME_AXIS_MS, y)
                # Force update
                self.plots[ch].update()

            # Update tacho frequency (channel 10)
            self.curves[10].setData(TIME_AXIS_MS, tacho_freq)
            self.plots[10].update()
            
            # Update tacho trigger (channel 11)
            self.curves[11].setData(TIME_AXIS_MS, tacho_trig)
            self.plots[11].update()
            
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