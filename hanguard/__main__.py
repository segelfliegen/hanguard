import serial, logging, csv, datetime
logging.basicConfig(level=logging.DEBUG)


class Hanguard():
    """
    Hanguard is the hangar guard, who only accepts request to doors for people
    having the right keys ;)
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

    def send(self, cmd, recipient=0, msg=""):
        """
        Sends a CAN-bus command.

        cmd is the command as described from protokoll.md.
        recipient is a specific recipient (door_id), 0 is a broadcast
        msg is the message part to be send.
        """

        #     recipient          target       command
        if recipient:
            cmd = (recipient << 5) | (0x1 << 4) | cmd

        msg = b"c;%04X;%s\r\n" % (cmd, msg.encode())

        logging.debug("Sending >>> %r", msg)
        self.sp.write(msg)

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

        self.send(20, msg=date)  # broadcast

    def run(self):
        self.send_hello()

        while True:
             # Wait until there is data waiting in the serial buffer
            if self.sp.in_waiting > 0:
                # Read data out of the buffer until a carraige return/new line is found
                buf = self.sp.readline()
                logging.debug("Received <<< %r", buf)

                buf = buf.decode()

                while buf:
                    # ACK
                    if buf[0] == "\x06":
                        buf = buf[1:]
                        logging.debug("ACK")
                    # NACK
                    elif buf[0] == "\x15":
                        buf = buf[1:]
                        logging.debug("NACK")
                    # Message
                    elif buf.startswith("c;"):
                        #msg, buf = buf.split("\r\n", 1)
                        msg = buf
                        buf = ""

                        parts = msg.strip().split(";")
                        if len(parts) != 3:
                            logging.error("Received invalid msg %r", msg)
                            continue

                        self.handle(parts)
                    # Junk
                    else:
                        logging.error("Don't know how to handle %r", buf[0])
                        buf = buf[1:]

    def handle(self, msg):
        cmd = int(msg[1], base=16)

        # check for alarm, if 10th bit is set, ignore
        if cmd & 0x1 << 10:
            logging.info("Received an alarm system message, ignoring")
            return

        # do we have a sender address?
        if cmd & (1 << 4) == 0:
            door_key = (cmd & (0xF << 5)) >> 5
            cmd &= 0x1F

            logging.debug(f"cmd={cmd} on door={door_key}")

            if not (door := self.door.get(str(door_key))):
                logging.error(f"Received request from unknown door_key={door_key}")
                return

            # open
            if cmd == 0:
                allow = "" # deny, "00" will send close

                # Check for chip id and get specific member identified by this.
                if member := self.member.get(msg[2]):
                    logging.debug(
                        "%s %s wants to open %s",
                        member["firstname"],
                        member["lastname"],
                        door["name"]
                    )

                    # Does this member have access right to the specified door?
                    if member_door := self.member_door.get(f"{member['member_key']};{door['door_key']}"):
                        allow = "%02x" % 3  # open for 3 seconds
                    else:
                        logging.debug("DENIED")

                self.send(3, door_key, allow)

            # status
            elif cmd == 2:
                status = int(msg[2], base=16)
                meaning = []
                if status & 0x1:
                    meaning.append("abgeschlossen")
                else:
                    meaning.append("nicht abgeschlossen")

                if status & 0x2:
                    meaning.append("sabotiert")
                if status & 0x4:
                    meaning.append("alarm")

                logging.debug(f"Status door {self.door.get(str(door_key))} => {', '.join(meaning)}")

            else:
                logging.warning(f"cmd={cmd} not implemented")


hanguard = Hanguard()
hanguard.run()
