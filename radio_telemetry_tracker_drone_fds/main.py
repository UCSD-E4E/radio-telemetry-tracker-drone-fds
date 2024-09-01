import smbus2
import os
import time

# Read I2C bus number and device address from environment variables
i2c_bus = int(os.getenv('GPS_I2C_BUS'))
neo_m9n_address = int(os.getenv('GPS_ADDRESS'), 16)
bus = smbus2.SMBus(i2c_bus)

buffer = ""

def read_gps_data(address, total_length=32):
    try:
        data = bus.read_i2c_block_data(address, 0xFF, total_length)
        return data
    except Exception as e:
        print(f"Error reading GPS data: {e}")
        return None

def process_buffer(buffer):
    sentences = buffer.split('\n')
    for sentence in sentences[:-1]:  # Process all complete sentences
        if sentence.startswith('$GNRMC'):
            parts = sentence.split(',')
            if len(parts) >= 6:
                latitude = convert_to_degrees(parts[3], parts[4], is_latitude=True)
                longitude = convert_to_degrees(parts[5], parts[6], is_latitude=False)
                print(f"Latitude: {latitude}, Longitude: {longitude}")
    return sentences[-1]  # Return the last part of the buffer (incomplete sentence)

def convert_to_degrees(value, direction, is_latitude):
    if not value or not direction:
        return None
    
    if is_latitude:
        degrees = float(value[:2])
        minutes = float(value[2:])
    else:
        degrees = float(value[:3])
        minutes = float(value[3:])
    
    decimal_degrees = degrees + minutes / 60
    
    if direction in ['S', 'W']:
        decimal_degrees *= -1
    
    return decimal_degrees

# Read and parse data continuously
while True:
    data = read_gps_data(neo_m9n_address, 32)
    if data:
        buffer += ''.join(chr(c) for c in data)
        buffer = process_buffer(buffer)
    time.sleep(0.1)  # Short sleep to reduce CPU usage

if __name__ == "__main__":
    # Add any code here that you want to run when the script is executed directly
    print("GPS module running...")
    # For example, you might want to start a loop to continuously read GPS data
    while True:
        data = read_gps_data(neo_m9n_address)
        if data:
            buffer = process_buffer(buffer + ''.join(chr(b) for b in data))
        time.sleep(1)  # Wait for 1 second before reading again