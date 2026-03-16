import sys
import struct
import numpy as np
from vispy import scene
from PyQt5.QtWidgets import QApplication, QScrollArea, QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer, QMutex
import paho.mqtt.client as mqtt


BROKER = "192.168.1.231"
TOPIC = "sarayu/d1/topic1"

SAMPLE_RATE = 4096
SAMPLES = 4096
HEADER_LEN = 100
TOTAL_LEN = 49252


class MQTTScope:

    def __init__(self):

        self.app = QApplication(sys.argv)

        self.scroll = QScrollArea()
        self.scroll.resize(1800, 1200)  # Larger window for better visibility
        self.scroll.setWindowTitle("MQTT VisPy Scope")

        self.central = QWidget()
        self.layout = QVBoxLayout(self.central)

        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.central)

        self.t_axis = np.arange(SAMPLES) / SAMPLE_RATE

        self.canvases = []
        self.lines = []

        for i in range(12):

            canvas = scene.SceneCanvas(
                keys='interactive',
                bgcolor='white',      # white background
                show=True
            )

            # canvas.setMinimumHeight(320)   # larger plots
            canvas.native.setMinimumHeight(220)

            view = canvas.central_widget.add_view()
            view.camera = scene.PanZoomCamera()
            # Set camera to show full y-axis range for proper waveform display
            view.camera.rect = [0, -0.6, 1, 1.2]  # [x, y, width, height] for full range

            # line (no dummy plotting)
            # Different colors for different channel types
            if i < 10:  # Analog channels - blue
                color = 'blue'
            elif i == 10:  # Tacho frequency - green
                color = 'green'
            else:  # Tacho trigger - red
                color = 'red'
                
            line = scene.Line(
                color=color,
                width=2,
                parent=view.scene
            )

            self.layout.addWidget(canvas.native)

            self.canvases.append(canvas)
            self.lines.append(line)

        self.latest = None
        self.mutex = QMutex()

        # MQTT
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(BROKER)
        self.client.loop_start()

        # timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(30)

        # Show the window
        self.scroll.show()

        sys.exit(self.app.exec_())

    def on_connect(self, client, userdata, flags, rc):
        print("MQTT connected:", rc)
        client.subscribe(TOPIC)

    def on_message(self, client, userdata, msg):

        if len(msg.payload) != TOTAL_LEN * 2:
            print("Invalid payload length")
            return

        raw = struct.unpack(f"<{TOTAL_LEN}H", msg.payload)
        payload = np.array(raw, dtype=np.uint16)

        idx = HEADER_LEN

        six_ch = payload[idx:idx + 6 * SAMPLES].reshape(SAMPLES, 6).astype(np.float32)
        idx += 6 * SAMPLES

        four_ch = payload[idx:idx + 4 * SAMPLES].reshape(SAMPLES, 4).astype(np.float32)
        idx += 4 * SAMPLES

        tacho_freq = payload[idx:idx + SAMPLES].astype(np.float32)
        idx += SAMPLES

        tacho_trig = payload[idx:idx + SAMPLES].astype(np.float32)

        analog = np.zeros((SAMPLES, 10), dtype=np.float32)
        analog[:, :6] = six_ch
        analog[:, 6:] = four_ch
        
        # Convert to mil units (scale down from uint16 range)
        analog = (analog - 32768) / 32768 * 0.5  # Scale to -0.5 to 0.5 mil range

        self.mutex.lock()
        self.latest = (analog, tacho_freq, tacho_trig)
        self.mutex.unlock()

    def update_plot(self):

        self.mutex.lock()
        data = self.latest
        self.mutex.unlock()

        if data is None:
            return

        analog, tacho_freq, tacho_trig = data

        # analog channels
        for ch in range(10):

            y = analog[:, ch]
            pts = np.column_stack((self.t_axis, y))

            self.lines[ch].set_data(pts)

        # tacho freq
        pts = np.column_stack((self.t_axis, tacho_freq))
        self.lines[10].set_data(pts)

        # tacho trigger
        pts = np.column_stack((self.t_axis, tacho_trig))
        self.lines[11].set_data(pts)


if __name__ == "__main__":
    MQTTScope()