"""
Hanguard is the hangar guard, who only accepts request to doors for people
having the right keys ;)
"""

import json
import datetime
import logging
import serial
import pyodbc

logging.basicConfig(level=logging.DEBUG)


class Hanguard():
    def __init__(self):
        super().__init__()

        # Read configuration
        with open("hanguard_config.json", "r") as f:
            self.config = json.load(f)

        # Start serial connection
        self.sp = serial.Serial(
            port=self.config["port"],
            baudrate=115200,
            bytesize=8,
            timeout=2,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_EVEN
        )

        # Connect to SQL database
        self.sql_conn_str = \
            "Driver={SQL Server};" \
            f"SERVER={self.config["sql"]["server"]};" \
            f"DATABASE={self.config["sql"]["database"]};" \
            f"UID={{{self.config["sql"]["uid"]}}};" \
            f"PWD={self.config["sql"]["password"]}"

        logging.debug(f"{self.sql_conn_str=}")

        # Read & cache doors from database
        self.doors = {
            door["Tür_Nummer"]: door["Tür_Name"]
            for door in self._sql_request("SELECT * FROM dbo.[Türen]"):
        }

        logging.debug(f"{self.doors=}")

    def _sql_request(self, sql, *args):
        """
        Internal helper to execute and run an SQL statement.
        The returned result is a list of dict with the result.
        """
        try:
            with pyodbc.connect(self.sql_conn_str) as conn:
                with conn.cursor() as cursor:
                    logging.debug(f"{sql=} {args=}")
                    cursor.execute(sql, *args)
                    columns = [column[0] for column in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except pyodbc.Error as e:
            logging.exception(e)
            return []

    def check_access(self, chip_id, door_id):
        ret = _sql_request(
            "SELECT Mitgliedsnummer, Vorname, Nachname FROM dbo.[Mitglieder] WHERE Chip_ID = ? OR Chip_ID1 = ? OR Chip_ID2 = ?",
            chip_id, chip_id, chip_id
        )

        if ret:
            logging.debug(
                "%s %s (%s) wants to open %s",
                ret["Vorname"],
                ret["Nachname"],
                ret["Mitgliedsnummer"],
                self.doors[door_id],
            )

            # Does this member have access right to the specified door?
            ret = _sql_request(
                "SELECT * FROM dbo.[Berechtigung_Tür] WHERE Mitgliedsnummer = ? AND {Tür_Nummer} = ?",
                ret["Mitgliedsnummer"], door_id
            )

            # TODO: CHECK DATA VALIDITY!
            return bool(ret)

        return False

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
            door_id = (cmd & (0xF << 5)) >> 5
            cmd &= 0x1F

            logging.debug(f"{cmd=} on {door_id=}")

            # open
            if cmd == 0:
                allow = "" # deny, "00" will send close

                if not self.doors.get(door_id):
                    logging.error(f"Received request from unknown {door_id=}; Either update database or restart.")
                else:
                    # Check for chip id and get specific member identified by this.
                    if self.check_access(msg[2], door_id)
                        allow = "%02x" % 3  # open for 3 seconds

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


if __name__ == "__main__":
    hanguard = Hanguard()
    hanguard.run()
