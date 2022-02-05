import serial, time

sp = serial.Serial(
    port="/dev/ttyUSB5",
    baudrate=115200,
    bytesize=8,
    timeout=2,
    stopbits=serial.STOPBITS_ONE,
    parity=serial.PARITY_EVEN
)

sp.write(b"c;0014;07D90C0506110723\r\n")
while True:
    # Wait until there is data waiting in the serial buffer
    if sp.in_waiting > 0:

        # Read data out of the buffer until a carraige return/new line is found
        serialString = sp.readline()

        # Ignore ACK
        if serialString == b"\x06":
            continue

        print(serialString)

        # Fluglehrerzimmer
        if serialString[:7] == b"c;00A0;":
            #sp.write(b"c;00B3;03\r\n")  # 3sek öffnen
            sp.write(b"c;00B3;00\r\n")  # ablehnen (0 sek erlauben)
        # Geschäftsführerzimmer
        elif serialString[:7] == b"c;0080;":
            sp.write(b"c;0093;03\r\n")  # 3sek erlauben

        # Print the contents of the serial data
        #sp.write(b"t\r\n")
