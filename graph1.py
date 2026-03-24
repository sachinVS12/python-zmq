# import sys
# import struct
# import numpy as np
# from vispy import scene
# from PyQt5.QtWidgets import QApplication, QScrollArea, QWidget, QVBoxLayout
# from PyQt5.QtCore import QTimer, QMutex
# import paho.mqtt.client as mqtt


# BROKER = "192.168.1.231"
# TOPIC = "sarayu/d1/topic1"

# SAMPLE_RATE = 4096
# SAMPLES = 4096
# HEADER_LEN = 100
# TOTAL_LEN = 49252


# class MQTTScope:

#     def __init__(self):

#         self.app = QApplication(sys.argv)

#         self.scroll = QScrollArea()
#         self.scroll.resize(1800, 1200)  # Larger window for better visibility
#         self.scroll.setWindowTitle("MQTT VisPy Scope")

#         self.central = QWidget()
#         self.layout = QVBoxLayout(self.central)

#         self.scroll.setWidgetResizable(True)
#         self.scroll.setWidget(self.central)

#         self.t_axis = np.arange(SAMPLES) / SAMPLE_RATE

#         self.canvases = []
#         self.lines = []
#         self.views = []  # Store views for camera control

#         # Create plots for all 12 channels
#         for i in range(12):

#             canvas = scene.SceneCanvas(
#                 keys='interactive',
#                 bgcolor='white',      # white background
#                 show=True
#             )

#             canvas.native.setMinimumHeight(220)

#             view = canvas.central_widget.add_view()
#             view.camera = scene.PanZoomCamera()
            
#             # Different colors and initial y-ranges for different channel types
#             if i < 10:  # Analog channels - blue, range -0.6 to 0.6
#                 color = 'blue'
#                 view.camera.rect = (0, -0.6, 1, 1.2)  # (x, y, width, height)
#             elif i == 10:  # Tacho frequency - green, range 0 to 1.2
#                 color = 'green'
#                 view.camera.rect = (0, 0, 1, 1.2)  # (x, y, width, height)
#             else:  # Tacho trigger - red, range 0 to 1.2
#                 color = 'red'
#                 view.camera.rect = (0, 0, 1, 1.2)  # (x, y, width, height)

#             # Add a label to identify each plot
#             label = scene.Text(f"Channel {i+1}", color='black', parent=view.scene)
#             label.pos = 10, 10  # Position in the top-left corner
                
#             line = scene.Line(
#                 color=color,
#                 width=2,
#                 parent=view.scene
#             )

#             self.layout.addWidget(canvas.native)

#             self.canvases.append(canvas)
#             self.lines.append(line)
#             self.views.append(view)

#         self.latest = None
#         self.mutex = QMutex()
        
#         # Statistics for debugging
#         self.frame_count = 0
#         self.last_tacho_freq = None

#         # MQTT
#         self.client = mqtt.Client()
#         self.client.on_connect = self.on_connect
#         self.client.on_message = self.on_message
#         self.client.connect(BROKER)
#         self.client.loop_start()

#         # timer
#         self.timer = QTimer()
#         self.timer.timeout.connect(self.update_plot)
#         self.timer.start(30)

#         # Show the window
#         self.scroll.show()

#         sys.exit(self.app.exec_())

#     def on_connect(self, client, userdata, flags, rc):
#         print("MQTT connected:", rc)
#         client.subscribe(TOPIC)

#     def on_message(self, client, userdata, msg):

#         if len(msg.payload) != TOTAL_LEN * 2:
#             print(f"Invalid payload length: {len(msg.payload)}, expected {TOTAL_LEN * 2}")
#             return

#         raw = struct.unpack(f"<{TOTAL_LEN}H", msg.payload)
#         payload = np.array(raw, dtype=np.uint16)

#         idx = HEADER_LEN

#         six_ch = payload[idx:idx + 6 * SAMPLES].reshape(SAMPLES, 6).astype(np.float32)
#         idx += 6 * SAMPLES

#         four_ch = payload[idx:idx + 4 * SAMPLES].reshape(SAMPLES, 4).astype(np.float32)
#         idx += 4 * SAMPLES

#         tacho_freq_raw = payload[idx:idx + SAMPLES].astype(np.float32)
#         idx += SAMPLES

#         tacho_trig_raw = payload[idx:idx + SAMPLES].astype(np.float32)

#         analog = np.zeros((SAMPLES, 10), dtype=np.float32)
#         analog[:, :6] = six_ch
#         analog[:, 6:] = four_ch
        
#         # Convert analog to mil units (scale down from uint16 range)
#         analog = (analog - 32768) / 32768 * 0.5  # Scale to -0.5 to 0.5 mil range
        
#         # Check tacho data statistics
#         tacho_freq_min = np.min(tacho_freq_raw)
#         tacho_freq_max = np.max(tacho_freq_raw)
#         tacho_freq_mean = np.mean(tacho_freq_raw)
#         tacho_freq_std = np.std(tacho_freq_raw)
        
#         tacho_trig_min = np.min(tacho_trig_raw)
#         tacho_trig_max = np.max(tacho_trig_raw)
        
#         print(f"Tacho Freq - Min: {tacho_freq_min:.2f}, Max: {tacho_freq_max:.2f}, Mean: {tacho_freq_mean:.2f}, Std: {tacho_freq_std:.2f}")
#         print(f"Tacho Trig - Min: {tacho_trig_min:.2f}, Max: {tacho_trig_max:.2f}")
        
#         # Scale tacho frequency - keep raw values if they're already in reasonable range
#         # Based on debug, raw max is 10.0, so likely already in engineering units (Hz?)
#         if tacho_freq_max > 0:
#             # If all values are identical, they might be constant
#             if tacho_freq_std < 0.01 and tacho_freq_max > 0:
#                 print(f"WARNING: Tacho frequency appears constant at {tacho_freq_mean:.2f}")
            
#             # Use raw values without scaling if they're in reasonable range (0-100)
#             if tacho_freq_max <= 100:
#                 tacho_freq_scaled = tacho_freq_raw
#                 print(f"Using raw tacho frequency values (range: 0-{tacho_freq_max:.2f})")
#             else:
#                 # Scale down if values are too large
#                 tacho_freq_scaled = tacho_freq_raw / 100.0
#         else:
#             tacho_freq_scaled = tacho_freq_raw
            
#         # Scale tacho trigger - keep raw values if they're in reasonable range
#         if tacho_trig_max <= 10:
#             tacho_trig_scaled = tacho_trig_raw
#         else:
#             tacho_trig_scaled = tacho_trig_raw / 100.0
        
#         self.mutex.lock()
#         self.latest = (analog, tacho_freq_scaled, tacho_trig_scaled)
#         self.mutex.unlock()

#     def update_plot(self):

#         self.mutex.lock()
#         data = self.latest
#         self.mutex.unlock()

#         if data is None:
#             return

#         analog, tacho_freq, tacho_trig = data
#         self.frame_count += 1
        
#         # Update analog channels
#         for ch in range(10):
#             y = analog[:, ch]
#             pts = np.column_stack((self.t_axis, y))
#             self.lines[ch].set_data(pts)

#         # Update tacho frequency (channel 10)
#         # Check if there's actual data to plot
#         tacho_freq_max = np.max(tacho_freq)
#         tacho_freq_min = np.min(tacho_freq)
        
#         if tacho_freq_max > 0 or tacho_freq_min < 0:
#             pts = np.column_stack((self.t_axis, tacho_freq))
#             self.lines[10].set_data(pts)
            
#             # Auto-adjust y-range for tacho frequency
#             # Get current rect as a list/tuple
#             current_rect = self.views[10].camera.rect
#             # Convert to tuple if it's a Rect object
#             if hasattr(current_rect, 'left'):
#                 # It's a Rect object, extract coordinates
#                 rect_left = current_rect.left
#                 rect_bottom = current_rect.bottom
#                 rect_width = current_rect.width
#                 rect_height = current_rect.height
#                 current_y_min = rect_bottom
#                 current_y_max = rect_bottom + rect_height
#             else:
#                 # It's a tuple or list
#                 rect_x, rect_y, rect_width, rect_height = current_rect
#                 current_y_min = rect_y
#                 current_y_max = rect_y + rect_height
            
#             # Adjust range if needed
#             if tacho_freq_max > current_y_max or tacho_freq_min < current_y_min:
#                 new_y_min = min(0, tacho_freq_min * 0.9)
#                 new_y_max = max(tacho_freq_max * 1.1, 1.0)
#                 new_rect = (0, new_y_min, 1, new_y_max - new_y_min)
#                 self.views[10].camera.rect = new_rect
#                 print(f"Adjusted tacho freq range to [{new_y_min:.2f}, {new_y_max:.2f}]")
#         else:
#             # Plot a constant line at 0 if no data
#             pts = np.column_stack((self.t_axis, np.zeros_like(self.t_axis)))
#             self.lines[10].set_data(pts)

#         # Update tacho trigger (channel 11)
#         tacho_trig_max = np.max(tacho_trig)
#         tacho_trig_min = np.min(tacho_trig)
        
#         if tacho_trig_max > 0 or tacho_trig_min < 0:
#             pts = np.column_stack((self.t_axis, tacho_trig))
#             self.lines[11].set_data(pts)
            
#             # Auto-adjust y-range for tacho trigger
#             current_rect = self.views[11].camera.rect
#             if hasattr(current_rect, 'left'):
#                 rect_bottom = current_rect.bottom
#                 rect_height = current_rect.height
#                 current_y_min = rect_bottom
#                 current_y_max = rect_bottom + rect_height
#             else:
#                 rect_x, rect_y, rect_width, rect_height = current_rect
#                 current_y_min = rect_y
#                 current_y_max = rect_y + rect_height
            
#             if tacho_trig_max > current_y_max or tacho_trig_min < current_y_min:
#                 new_y_min = min(0, tacho_trig_min * 0.9)
#                 new_y_max = max(tacho_trig_max * 1.1, 1.0)
#                 new_rect = (0, new_y_min, 1, new_y_max - new_y_min)
#                 self.views[11].camera.rect = new_rect
#                 print(f"Adjusted tacho trig range to [{new_y_min:.2f}, {new_y_max:.2f}]")
#         else:
#             pts = np.column_stack((self.t_axis, np.zeros_like(self.t_axis)))
#             self.lines[11].set_data(pts)
        
#         # Print debug info every 50 frames
#         if self.frame_count % 50 == 0:
#             print(f"Frame {self.frame_count}: Tacho freq range=[{tacho_freq_min:.2f}, {tacho_freq_max:.2f}], "
#                   f"Tacho trig range=[{tacho_trig_min:.2f}, {tacho_trig_max:.2f}]")


# if __name__ == "__main__":
#     MQTTScope()




# import sys
# import struct
# import numpy as np
# from vispy import scene
# from PyQt5.QtWidgets import QApplication, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
# from PyQt5.QtCore import QTimer, QMutex
# import paho.mqtt.client as mqtt


# BROKER = "192.168.1.231"
# TOPIC = "sarayu/d1/topic1"

# SAMPLE_RATE = 4096
# SAMPLES = 4096
# HEADER_LEN = 100
# TOTAL_LEN = 49252

# # Time axis in milliseconds for better readability
# TIME_AXIS_MS = np.arange(SAMPLES) / SAMPLE_RATE * 1000  # Convert to milliseconds


# class MQTTScope:

#     def __init__(self):

#         self.app = QApplication(sys.argv)

#         # Create main window with scroll area
#         self.scroll = QScrollArea()
#         self.scroll.resize(1800, 1200)
#         self.scroll.setWindowTitle("MQTT VisPy Scope - 10 Analog Channels + 2 Tacho Channels")

#         self.central = QWidget()
#         self.layout = QVBoxLayout(self.central)
#         self.layout.setSpacing(10)

#         self.scroll.setWidgetResizable(True)
#         self.scroll.setWidget(self.central)

#         self.canvases = []
#         self.lines = []
#         self.views = []

#         # Create plots for all 12 channels
#         for i in range(12):
#             # Create a container widget for each channel with title
#             channel_widget = QWidget()
#             channel_layout = QVBoxLayout(channel_widget)
#             channel_layout.setSpacing(2)
            
#             # Add channel title
#             if i < 10:
#                 channel_title = QLabel(f"Analog Channel {i+1} (Amplitude - mil units)")
#                 channel_title.setStyleSheet("font-weight: bold; color: blue; background-color: #f0f0f0; padding: 5px;")
#             elif i == 10:
#                 channel_title = QLabel("Tacho Channel 1 - Frequency (Hz)")
#                 channel_title.setStyleSheet("font-weight: bold; color: green; background-color: #f0f0f0; padding: 5px;")
#             else:
#                 channel_title = QLabel("Tacho Channel 2 - Trigger Signal")
#                 channel_title.setStyleSheet("font-weight: bold; color: red; background-color: #f0f0f0; padding: 5px;")
            
#             channel_layout.addWidget(channel_title)

#             # Create canvas
#             canvas = scene.SceneCanvas(
#                 keys='interactive',
#                 bgcolor='white',
#                 show=True,
#                 size=(1600, 300)
#             )
            
#             canvas.native.setMinimumHeight(280)
#             canvas.native.setMaximumHeight(350)
            
#             view = canvas.central_widget.add_view()
#             view.camera = scene.PanZoomCamera()
            
#             # Set different initial Y-axis ranges based on channel type
#             if i < 10:  # Analog channels - amplitude in mil units
#                 view.camera.rect = (0, -0.6, TIME_AXIS_MS[-1], 1.2)  # (x, y, width, height)
#             elif i == 10:  # Tacho frequency
#                 view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 50)  # Assume 0-50 Hz range
#             else:  # Tacho trigger
#                 view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 1.2)  # Trigger signal
            
#             # Add grid for better readability
#             grid = scene.visuals.GridLines(parent=view.scene, color='lightgray')
            
#             # Add axis labels with fixed positions (don't depend on rect)
#             # Y-axis label
#             if i < 10:
#                 y_label_text = "Amplitude (mil)"
#             elif i == 10:
#                 y_label_text = "Frequency (Hz)"
#             else:
#                 y_label_text = "Trigger (V)"
            
#             y_label = scene.Text(y_label_text, color='black', font_size=10, parent=view.scene)
#             y_label.pos = (10, 0)  # Fixed position, will be updated later
            
#             # X-axis label
#             x_label = scene.Text("Time (ms)", color='black', font_size=10, parent=view.scene)
#             x_label.pos = (TIME_AXIS_MS[-1] / 2, -30)
            
#             # Channel number label
#             ch_label = scene.Text(f"Ch{i+1}", color='gray', font_size=9, parent=view.scene)
#             ch_label.pos = (TIME_AXIS_MS[-1] - 50, -20)
            
#             # Line for plotting
#             if i < 10:
#                 color = 'blue'
#             elif i == 10:
#                 color = 'green'
#             else:
#                 color = 'red'
                
#             line = scene.Line(
#                 color=color,
#                 width=2,
#                 parent=view.scene
#             )
            
#             channel_layout.addWidget(canvas.native)
#             self.layout.addWidget(channel_widget)
            
#             # Add separator line between channels
#             if i < 11:
#                 separator = QLabel("")
#                 separator.setStyleSheet("border-top: 1px solid #cccccc;")
#                 separator.setMaximumHeight(1)
#                 self.layout.addWidget(separator)
            
#             self.canvases.append(canvas)
#             self.lines.append(line)
#             self.views.append(view)

#         # Add control panel at the bottom
#         control_widget = QWidget()
#         control_widget.setStyleSheet("background-color: #f8f8f8; padding: 5px;")
#         control_layout = QHBoxLayout(control_widget)
        
#         # Add buttons for controlling all plots
#         reset_zoom_btn = QPushButton("Reset All Zooms")
#         reset_zoom_btn.clicked.connect(self.reset_all_zooms)
#         reset_zoom_btn.setStyleSheet("padding: 5px; font-weight: bold;")
#         control_layout.addWidget(reset_zoom_btn)
        
#         auto_range_btn = QPushButton("Auto Range All")
#         auto_range_btn.clicked.connect(self.auto_range_all)
#         auto_range_btn.setStyleSheet("padding: 5px; font-weight: bold;")
#         control_layout.addWidget(auto_range_btn)
        
#         # Add status label
#         self.status_label = QLabel("Status: Waiting for data...")
#         self.status_label.setStyleSheet("color: gray; padding: 5px; font-weight: bold;")
#         control_layout.addWidget(self.status_label)
        
#         control_layout.addStretch()
#         self.layout.addWidget(control_widget)

#         self.latest = None
#         self.mutex = QMutex()
        
#         # Statistics for debugging
#         self.frame_count = 0

#         # MQTT
#         self.client = mqtt.Client()
#         self.client.on_connect = self.on_connect
#         self.client.on_message = self.on_message
#         self.client.connect(BROKER)
#         self.client.loop_start()

#         # Timer for updating plots
#         self.timer = QTimer()
#         self.timer.timeout.connect(self.update_plot)
#         self.timer.start(30)  # ~33 fps

#         # Show the window
#         self.scroll.show()

#         sys.exit(self.app.exec_())

#     def on_connect(self, client, userdata, flags, rc):
#         print("MQTT connected:", rc)
#         client.subscribe(TOPIC)
#         self.status_label.setText("Status: Connected to MQTT broker")
#         self.status_label.setStyleSheet("color: green; padding: 5px; font-weight: bold;")

#     def on_message(self, client, userdata, msg):

#         if len(msg.payload) != TOTAL_LEN * 2:
#             print(f"Invalid payload length: {len(msg.payload)}, expected {TOTAL_LEN * 2}")
#             return

#         raw = struct.unpack(f"<{TOTAL_LEN}H", msg.payload)
#         payload = np.array(raw, dtype=np.uint16)

#         idx = HEADER_LEN

#         six_ch = payload[idx:idx + 6 * SAMPLES].reshape(SAMPLES, 6).astype(np.float32)
#         idx += 6 * SAMPLES

#         four_ch = payload[idx:idx + 4 * SAMPLES].reshape(SAMPLES, 4).astype(np.float32)
#         idx += 4 * SAMPLES

#         tacho_freq_raw = payload[idx:idx + SAMPLES].astype(np.float32)
#         idx += SAMPLES

#         tacho_trig_raw = payload[idx:idx + SAMPLES].astype(np.float32)

#         analog = np.zeros((SAMPLES, 10), dtype=np.float32)
#         analog[:, :6] = six_ch
#         analog[:, 6:] = four_ch
        
#         # Convert analog to mil units (scale down from uint16 range)
#         analog = (analog - 32768) / 32768 * 0.5  # Scale to -0.5 to 0.5 mil range
        
#         # Process tacho frequency - keep raw values as they appear to be in Hz
#         tacho_freq_scaled = tacho_freq_raw
            
#         # Process tacho trigger - scale to 0-1 range if needed
#         tacho_trig_max = np.max(tacho_trig_raw)
#         if tacho_trig_max > 1:
#             tacho_trig_scaled = tacho_trig_raw / 65535.0
#         else:
#             tacho_trig_scaled = tacho_trig_raw

#         self.mutex.lock()
#         self.latest = (analog, tacho_freq_scaled, tacho_trig_scaled)
#         self.mutex.unlock()

#     def reset_all_zooms(self):
#         """Reset camera views to default ranges"""
#         for i, view in enumerate(self.views):
#             if i < 10:  # Analog channels
#                 view.camera.rect = (0, -0.6, TIME_AXIS_MS[-1], 1.2)
#             elif i == 10:  # Tacho frequency
#                 view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 50)
#             else:  # Tacho trigger
#                 view.camera.rect = (0, 0, TIME_AXIS_MS[-1], 1.2)
#         print("Reset all zooms to default")

#     def auto_range_all(self):
#         """Auto-range all channels based on current data"""
#         self.mutex.lock()
#         data = self.latest
#         self.mutex.unlock()
        
#         if data is None:
#             return
            
#         analog, tacho_freq, tacho_trig = data
        
#         # Auto-range analog channels
#         for i in range(10):
#             y = analog[:, i]
#             y_min = np.min(y)
#             y_max = np.max(y)
#             if y_max > y_min:
#                 padding = (y_max - y_min) * 0.1
#                 if padding == 0:
#                     padding = 0.1
#                 self.views[i].camera.rect = (0, y_min - padding, TIME_AXIS_MS[-1], (y_max - y_min) + 2*padding)
        
#         # Auto-range tacho frequency
#         freq_min = np.min(tacho_freq)
#         freq_max = np.max(tacho_freq)
#         if freq_max > freq_min:
#             padding = (freq_max - freq_min) * 0.1
#             if padding == 0:
#                 padding = 1.0
#             self.views[10].camera.rect = (0, max(0, freq_min - padding), TIME_AXIS_MS[-1], (freq_max - freq_min) + 2*padding)
        
#         # Auto-range tacho trigger
#         trig_min = np.min(tacho_trig)
#         trig_max = np.max(tacho_trig)
#         if trig_max > trig_min:
#             padding = (trig_max - trig_min) * 0.1
#             if padding == 0:
#                 padding = 0.1
#             self.views[11].camera.rect = (0, max(0, trig_min - padding), TIME_AXIS_MS[-1], (trig_max - trig_min) + 2*padding)
        
#         print("Auto-ranged all channels")

#     def update_plot(self):

#         self.mutex.lock()
#         data = self.latest
#         self.mutex.unlock()

#         if data is None:
#             return

#         analog, tacho_freq, tacho_trig = data
#         self.frame_count += 1
        
#         try:
#             # Update analog channels
#             for ch in range(10):
#                 y = analog[:, ch]
#                 # Use time in milliseconds for X-axis
#                 pts = np.column_stack((TIME_AXIS_MS, y))
#                 self.lines[ch].set_data(pts)

#             # Update tacho frequency (channel 10)
#             pts = np.column_stack((TIME_AXIS_MS, tacho_freq))
#             self.lines[10].set_data(pts)
            
#             # Update tacho trigger (channel 11)
#             pts = np.column_stack((TIME_AXIS_MS, tacho_trig))
#             self.lines[11].set_data(pts)
            
#             # Update status periodically
#             if self.frame_count % 30 == 0:
#                 # Calculate some statistics for status display
#                 freq_val = np.mean(tacho_freq) if len(tacho_freq) > 0 else 0
#                 self.status_label.setText(f"Status: Receiving data | Avg Freq: {freq_val:.1f} Hz | Frames: {self.frame_count}")
#         except Exception as e:
#             print(f"Error in update_plot: {e}")


# if __name__ == "__main__":
#     MQTTScope()