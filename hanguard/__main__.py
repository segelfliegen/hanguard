import serial, logging, csv, time
logging.basicConfig(level=logging.DEBUG)


class Hanguard():

    def __init__(self):
        super().__init__()

        # Read member cache
        self.door = self.__csv2dict("door.csv", "door_key")
        self.member = self.__csv2dict("member.csv", "chip")
        self.member_door = self.__csv2dict("member_door.csv", ["member_key", "door_key"])

        logging.info(
            "%d door, %d member, %d member_door",
            len(self.door), len(self.member), len(self.member_door)
        )

        # Start serial connection
        self.sp = serial.Serial(
            port="/dev/ttyUSB5",
            baudrate=115200,
            bytesize=8,
            timeout=2,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_EVEN
        )

    def __csv2dict(self, filename, key_fields):
        """
        Reads a csv file into a dict, with a specified, possibly combined key.
        """
        ret = {}
        if not isinstance(key_fields, (list, tuple)):
            key_fields = [key_fields]

        with open(filename) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if key := ";".join([(row[f] or "") for f in key_fields]):
                    #assert key not in ret
                    ret[key] = row

                    logging.debug(f"{filename} {key} = {row}")

        return ret

    def send_hello(self):
        self.sp.write(b"c;0014;07D90C0506110723\r\n")  # Send Hello!

    def run(self):
        self.send_hello()

        while True:
             # Wait until there is data waiting in the serial buffer
            if self.sp.in_waiting > 0:
                # Read data out of the buffer until a carraige return/new line is found
                buf = self.sp.readline()

                while buf: #todo
                    # If ACK or NACK, just log.
                    if buf == b"\x06":
                        #buf = buf[1:]
                        logging.info("ACK")
                        break # continue
                    elif buf == b"\x15":
                        #buf = buf[1:]
                        logging.warning("NACK")
                        break # continue

                    logging.debug("Received %r", buf)

                    msg = buf.decode().strip().split(";")
                    if msg[0] != "c":
                        logging.info("Received junk %r, ignoring (doesn't start with c)", buf)
                        break  # continue

                    if msg := self.handle(msg):
                        logging.info("Sending %r", msg)
                        self.sp.write(msg.encode())

                    break  # remove

    def handle(self, msg):
        cmd = int(msg[1], base=16)

        # check for alarm, if 10th bit is set, ignore
        if cmd & 1 << 10:
            return

        # do we have a sender address?
        if cmd & (1 << 4) == 0:
            door = (cmd & (0xF << 5)) >> 5
            #logging.info(f"Tür {self.door[str(door)]}")

            door = self.door.get(str(door))

            cmd &= 0x1F
            logging.debug(f"cmd = {cmd}")

            # open
            if cmd == 0:
                #     address       target     cmd
                ret = (int(door["door_key"]) << 5) | (1 << 4) | 3
                allow = "00"

                logging.info(self.member.get(msg[2]))

                if member := self.member.get(msg[2]):
                    logging.debug("%s wants to open %s", member["firstname"], door["name"])
                    if member_door := self.member_door.get(f"{member['member_key']};{door['door_key']}"):
                        allow = "%02x" % 3
                    # when allow = "00" => close abschliessen

                return "c;%04X;%s\r\n" % (ret, allow)


hanguard = Hanguard()
hanguard.run()
