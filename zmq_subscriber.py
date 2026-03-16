import zmq
import json
import time

# ---------------- CONFIG ----------------
zmq_port = 5555
zmq_host = "localhost"

# ---------------- ZMQ SETUP ----------------
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect(f"tcp://{zmq_host}:{zmq_port}")
socket.subscribe("")  # Subscribe to all messages

print(f"ZMQ Subscriber connected to {zmq_host}:{zmq_port}")
print("Waiting for messages...")

# ---------------- MAIN LOOP ----------------
try:
    while True:
        # Receive message
        message = socket.recv_string()
        
        # Parse JSON
        try:
            data = json.loads(message)
            
            # Print formatted output
            print("\n" + "="*60)
            print(f"📨 Message received at: {time.strftime('%H:%M:%S', time.localtime(data['timestamp']))}")
            
            # Header info
            header = data['header']
            print(f"📋 Header: Frame=({header['frameA']},{header['frameB']}) | "
                  f"Channels={header['numChannels']} | "
                  f"SampleRate={header['sampleRate']}Hz | "
                  f"Samples={header['samplesCount']} (1 second)")
            
            # Metadata
            metadata = data['metadata']
            print(f"📊 Metadata: 6ch={metadata['totalSamples6ch']} samples | "
                  f"4ch={metadata['totalSamples4ch']} samples | "
                  f"Tacho={metadata['totalTachoSamples']} samples | "
                  f"Duration={metadata.get('duration', 'Unknown')} | "
                  f"Samples/sec={metadata.get('samplesPerSecond', 'Unknown')}")
            
            # Data samples (showing first few)
            print(f"📈 Data Samples (first 20):")
            print(f"   6ch channels: {data['data']['channels6ch'][:20]}")
            print(f"   4ch channels: {data['data']['channels4ch'][:20]}")
            print(f"   Tacho freq:   {data['data']['tachoFrequency'][:20]}")
            print(f"   Tacho trigger:{data['data']['tachoTrigger'][:20]}")
            
            # Tacho trigger positions (check more samples for 1-second data)
            tacho_triggers = [i for i, val in enumerate(data['data']['tachoTrigger'][:200]) if val == 1]
            if tacho_triggers:
                print(f"⚡ Tacho triggers at positions: {tacho_triggers}")
            else:
                print(f"⚡ No tacho triggers found in first 200 samples")
            
            print("="*60)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            print(f"Raw message: {message[:200]}...")
            
except KeyboardInterrupt:
    print("\n👋 Subscriber stopped by user")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    socket.close()
    context.term()
