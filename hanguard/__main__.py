import serial, logging, csv, datetime
logging.basicConfig(level=logging.DEBUG)


class Hanguard():
    """
    Hanguard is the hangar guard, who only accepts request to doors with the right keys ;)
    """

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
                if (key := ";".join([(row[f] or "") for f in key_fields])) and key != "0":
                    # fixme: Is it okay that a key might match multiple times? e.g. chip 8D00000369491F14
                    #assert key not in ret, f"{key} already set"
                    ret[key] = row

                    logging.debug(f"{filename} {key} = {row}")

        return ret

    def send_hello(self):
        now = datetime.datetime.now()
        date = "%04X%02X%02X%02X%02X%02X%02X" % (
            now.year,
            now.month,
            now.day,
            now.weekday() + 1,  # 1 is monday
            now.hour,
            now.minute,
            now.second
        )
        send = b"c;0014;%s\r\n" % date.encode()
        logging.debug("send %r", send)
        self.sp.write(send)  # Send Hello!

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
        if cmd & 0x1 << 10:
            return

        # do we have a sender address?
        if cmd & (1 << 4) == 0:
            cmd &= 0x1F
            door_key = (cmd & (0xF << 5)) >> 5

            logging.debug(f"cmd={cmd} on door={door_key}")

            if not (door := self.door.get(str(door_key))):
                logging.error(f"Received request from unknown door_key={door_key}")
                return

            # open
            if cmd == 0:
                #     address       target     cmd
                ret = (door_key << 5) | (0x1 << 4) | 3
                allow = "" # deny, "00" will send close

                if member := self.member.get(msg[2]):
                    logging.debug(
                        "%s %s wants to open %s",
                        member["firstname"],
                        member["lastname"],
                        door["name"]
                    )

                    if member_door := self.member_door.get(f"{member['member_key']};{door['door_key']}"):
                        allow = "%02x" % 3

                return "c;%04X;%s\r\n" % (ret, allow)


hanguard = Hanguard()
hanguard.run()
