import paho.mqtt.client as mqtt
import zmq
import struct
import json
import time
from collections import deque

# ---------------- CONFIG ----------------
mqtt_broker = "192.168.1.231"
mqtt_topics = ["sarayu/d1/topic1"]
zmq_port = 5555

# ---------------- PARAMETERS ----------------
HEADER_LEN = 100
TOTAL_LEN = 49252
num6ch = 6
num4ch = 4
samples_per_message = 4096

# ---------------- ZMQ SETUP ----------------
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind(f"tcp://*:{zmq_port}")
print(f"ZMQ Publisher started on port {zmq_port}")

# ---------------- MQTT SETUP ----------------
client = mqtt.Client()

def on_message(client, userdata, msg):
    try:
        # Unpack binary data
        buffer = msg.payload
        if len(buffer) != TOTAL_LEN * 2:  # 2 bytes per uint16
            print(f"Invalid message size: {len(buffer)} bytes")
            return
        
        # Unpack uint16 LE array
        data = struct.unpack("<" + "H" * TOTAL_LEN, buffer)
        
        # Extract header
        header = data[:HEADER_LEN]
        frameA, frameB, numChannels, sampleRate, _, samplesCount, numTachoChannels = header[:7]
        
        # Extract data sections
        idx = HEADER_LEN
        
        # 6-channel data
        data6ch = data[idx:idx + (samplesCount * num6ch)]
        idx += len(data6ch)
        
        # 4-channel data  
        data4ch = data[idx:idx + (samplesCount * num4ch)]
        idx += len(data4ch)
        
        # Tacho frequency
        tachoFreq = data[idx:idx + samplesCount]
        idx += len(tachoFreq)
        
        # Tacho trigger
        tachoTrigger = data[idx:idx + samplesCount]
        
        # Create JSON message (1 second, 4096 samples)
        json_msg = {
            "timestamp": time.time(),
            "header": {
                "frameA": frameA,
                "frameB": frameB,
                "numChannels": numChannels,
                "sampleRate": sampleRate,
                "samplesCount": samples_per_message,  # 4096 samples (1 second)
                "numTachoChannels": numTachoChannels
            },
            "data": {
                "channels6ch": list(data6ch[:samples_per_message]),  # Limit to 4096 samples
                "channels4ch": list(data4ch[:samples_per_message]),  # Limit to 4096 samples
                "tachoFrequency": list(tachoFreq[:samples_per_message]),  # Limit to 4096 samples
                "tachoTrigger": list(tachoTrigger[:samples_per_message])  # Limit to 4096 samples
            },
            "metadata": {
                "totalSamples6ch": len(data6ch[:samples_per_message]),
                "totalSamples4ch": len(data4ch[:samples_per_message]),
                "totalTachoSamples": len(tachoFreq[:samples_per_message]),
                "duration": "1.0 second",
                "samplesPerSecond": samples_per_message
            }
        }
        
        # Send via ZMQ
        socket.send_string(json.dumps(json_msg))
        print(f"Sent 1-second message | Frame=({frameA},{frameB}) | Samples={samples_per_message}")
        
    except Exception as e:
        print(f"Error processing message: {e}")

client.on_message = on_message

# Connect to MQTT
client.connect(mqtt_broker)
print(f"Connected to MQTT broker: {mqtt_broker}")

# Subscribe to topics
for topic in mqtt_topics:
    client.subscribe(topic)
    print(f"Subscribed to: {topic}")

print("MQTT to ZMQ Bridge started...")

# Start MQTT loop
client.loop_forever()
