# Protokoll

Protokolle beginnen ein- wie ausgehend mit einem Steuerzeichen, Semikolon, Dateninhalt und enden mit CR+LF.

Jedes Protokoll wird nach Empfang von CR von ACK(=0x06) oder NACK(=0x15) gem#ß ASCII-Tabelle ohne nachfolgendes CR+LF beantwortet. Radix für Zahlenwerte ist Hex mit Großbuchstaben, kein führendes 0x o.ä. Leerzeichen zwischen Bytes im Protokoll werden ignoriert.

## Schnittstelle

- VCP über CP210x
- 115200 Baud
- 1 Startbit
- 8 Datenbits
- Even Parity
- 1 Stopbit
- ASCII
- kein Handshake

## Timeout

Da offenbar der CP210x-Treiber Probleme mit der Initialisierung hat, wenn der USB-Chip beim Booten bereits mit dem Rechner verbunden ist, löst das Gateway nach einem Timeout von 5 Minuten einen internen Reset mit Reset des CP210x aus, was auch den Comport schließt. Zum Rücksetzen des Timeout dient der Empfang jedes ACK oder CR.

## Befehlsaufbau

```
c;AABBCCDD;aabbccddeeff...
```

- AA = optional, highest(Message ID) nur bei extended Frames
- BB = optional, upper(Message ID) nur bei extended Frames
- CC = high(Message ID)
- DD = Low(Message ID)
- aa, bb, cc, usw. = Message-Dateninhalt, beginnend mit dem MSB.

Die Anzahl Datenbytes wird nicht separat übertragen, sondern ergibt sich aus der übermittelten Anzahl Datenbytes.

Achtung: auch bei 0 Datenbytes das zweite Semikolon nicht vergessen!

- ACK lässt darauf schließen, dass ein CAN-Sendepuffer zur Verfügung stand.
- NACK lässt darauf schließen, dass der Befehl einen unbekannten Steuerbefehl oder ungültige Argumente enthielt (z.B. ungerade Anzahl Nibbles) oder die CAN-Schnittstelle blockiert ist.

Ob die CAN-Schnittstelle zur Verfügung steht, ohne ungewollte Reaktionen auszulösen, kannst Du einfach mit einem Versand des Datums/Uhrzeit und Auswertung der Antwort prüfen. Damit wissen dann auch die Türöffner, dass der Server da ist.

## Beipiel

1. Türmodul Nr. 1 sendet Öffnungsanfrage mit einer fiktiven Chip-ID, 0x5E ist die CRC, 0x14 der Familycode: `c;0020;5E00070022631F914`
2. Öffnungsbefehl an Türmodul 1 für 10 Stunden (0x8CA0 Sekunden): `c;0033;8CA0`
3. Ablehnungsbefehl an Türmodul 1: `c;0033;`
4. Schließbefehl an alle Türen: `c;0013;0`
5. Türmodul 9 hat für 10 Stunden geöffnet: `c;0123;8CA0`
6. Datum/Zeit=Samstag, 5.12.2009, 17:07:35: `c;0014;07D90C0506110723`

## CAN-Befehle

### Übertragungsfehler abfragen
```
> e
< e;TX=aa;RX=bb;USB=cc
```

- aa = CAN-Tx-Fehler (Maximum seit letzter Abfrage)
- bb = CAN-Rx-Fehler (Maximum seit letzter Abfrage)
- cc = USB-Empfangsfehler (Overflow, Parity etc.)

Die Abfrage setzt alle 3 Zähler zurück.

### CAN-Parametrierung einstellen oder abfragen
```
> p
< p;SJW=aa;BRP=bb;PH1=cc;PH2=dd;PROP=ee;PRIO=ff
```

Einstellen ohne Schlüsselwörter `p;aa;bb;cc;dd;ee;ff`

Einstellen wird mit Ausgabe wie nach Anfrage beantwortet
- aa = SJW (1..4)
- bb = BRP (Baudrate-Prescaler, 1..64)
- cc = PHSEG1 (1..8)
- dd = PHSEG2 (1..8)
- ee = PROPSEG (1..8)
- ff = Sendepriorität (0..3)

Irrtümliches Verstellen der Parameter kann durch 1s-Tastendruck (im Betrieb, nicht beim Powerup!) resettet werden.

### Gateways resetten

(verstellt keine Parameter)
```
> r
```

Der Befehl setzt auch den USB-Chip zurück und schließt damit den Port. Es darf deshalb nicht mit Empfang von ACK gerechnet werden.

### UART-Empfangstimeouts abschalten

Anwendbar in Gateways zum temporären Anschluss an einen PC.
```
> t
```
Der Befehl wirkt bis zum Reset

### CAN-Empfangsfilter einstellen
```
> f;NN;AABBCCDD;aabbccdd
```

- NN = Nummer des Filters: 00 oder 01
  - Standard: Filter akzeptiert Ext. und Std.-Frames
  - Extended: Filter akzeptiert abhängig von Option im Filterwert, s.u.
- AA = optional, highest(Message ID) nur bei extended Frames
- BB = optional, upper(Message ID) nur bei extended Frames
- CC = high(Message ID)
- DD = Low(Message ID) Filterwert abängig von Maske (s.o.)
  - Standard: Filter akzeptiert nur Std.-Frames
  - Extended: Filter akzeptiert nur Ext.-Frames
- aa = optional, highest(Message ID) nur bei extended Frames
- bb = optional, upper(Message ID) nur bei extended Frames
- cc = high(Message ID)
- dd = Low(Message ID)

Der Befehl wirkt bis zum Reset oder bis zur Einstellung eines neuen Filters.

### Loopback-Mode

```
> l
```

Der Befehl wirkt bis zum Reset.

## CAN-Messages

| Funktion                                            | Message-ID, binär                                                                           | ID dez, n=0 | ID hex, n=s.u. | ID hex, n=s.u. | Bytes                | Format                                                                                                    | wird gesendet bei                                                                         | Bestätigung durch                  |
|:----------------------------------------------------|:--------------------------------------------------------------------------------------------|:------------|:---------------|:---------------|:---------------------|:----------------------------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------|:-----------------------------------|
| Chip-ID Kurzbetätigung (Öffnen)                     | b'nnnnnn00000'                                                                              | 0           | 40             | 1E0            | 8                    | MSB (CRC) zuerst                                                                                          | Loslassen des Chips nach kurzer Betätigung, zyklisch bis zur Bestätigung oder Timeout     | Tür öffnen/schließen               |
| Chip-ID Langbetätigung (Schließen)                  | b'nnnnnn00001'                                                                              | 1           | 41             | 1E1            | 8                    | MSB (CRC) zuerst                                                                                          | Lange Betätigung des Chips, zyklisch bis zur Bestätigung oder Timeout                     | Tür öffnen/schließen               |
| Verschlusszustand einer Tür                         | b'nnnnnn00010'                                                                              | 2           | 42             | 1E2            | 1                    | Bit0: 1=abgeschlossen, Bit1:1=sabotiert, Bit2:1=Alarm                                                     | Änderung & zyklisch, Anfrage                                                              | keine                              |
| Verschlusszustand aller Türen, vom Server berechnet | b'00000000010'                                                                              | 2           | 2              | 2              | 1                    | Bit0: 1=alle abgeschlossen, Bit1:1=mind. 1 sabotiert, Bit2:1=mind. 1 Alarm, Bit3:1=mind. 1 Türmodul fehlt | Änderung & zyklisch                                                                       | keine                              |
| Verschlusszustand anfragen                          | b'nnnnnn10010'                                                                              | 18          | 52             | 1F2            | 0                    |                                                                                                           | Bedarf                                                                                    | Verschlusszustand einer Tür        |
| Tür öffnen/schließen                                | b'nnnnnn10011'                                                                              | 19          | 53             | 1F3            | 0-8                  | 0 Bytes: Ablehnung durch Server, sonst Öffnungszeit[s], LSB zuerst, triggert nach, 0s=schließen           | Chip-ID Kurz-/Langbetätigung                                                              | Tür geöffnet/geschlossen           |
| Tür geöffnet/geschlossen                            | b'nnnnnn00011'                                                                              | 3           | 43             | 1E3            | 0-8                  | [s], LSB zuerst                                                                                           | Tür öffnen/schließen                                                                      | keine                              |
| zykl. Hallo (Datum/Zeit) vom Server                 | b'00000010100'                                                                              | 20          | 14             | 14             | 8                    | yymdWhms, W=Wochentag(Montag=1, Sonntag=7, 0=automatisch-nicht zyklisch verwenden!)                       | Anfrage & zyklisch. Beispiel: Samstag, 5.12.2009,17:07:35=07h,D9h,0Ch,05h,06h,11h,07h,23h | keine                              |
| Anfrage Zeit                                        | b'nnnnnn00100'                                                                              | 4           | 44             | 1E4            | 0                    |                                                                                                           | Bedarf                                                                                    | Hallo (Datum/Zeit)                 |
| Chip-Lernmodus starten/stoppen                      | b'nnnnnn10101'                                                                              | 21          | 55             | 1F5            | 1                    | 0=Lernmodus aus, 1=ein                                                                                    | Bedarf                                                                                    | Chip-Lernmodus gestartet, gestoppt |
| Chip-Lernmodus gestartet, gestoppt                  | b'nnnnnn00101'                                                                              | 5           | 45             | 1E5            | 1                    | 0=Lernmodus aus, 1=ein                                                                                    | Chip-Lernmodus starten/stoppen durch CAN-Telegramm                                        | keine                              |
| einzelne Chip-ID einlernen                          | b'nnnnnn10110'                                                                              | 22          | 56             | 1F6            | 8                    | MSB (CRC) zuerst                                                                                          | Umprogrammierung am Server                                                                | einzelne Chip-ID eingelernt        |
| einzelne Chip-ID auslernen                          | b'nnnnnn10111'                                                                              | 23          | 57             | 1F7            | 8                    | MSB (CRC) zuerst                                                                                          | Umprogrammierung am Server oder im Lernmodus                                              | einzelne Chip-ID ausgelernt        |
| alle Chip-IDs auslernen                             | b'nnnnnn10111'                                                                              | 23          | 57             | 1F7            | 0                    |                                                                                                           | Umprogrammierung am Server oder im Lernmodus                                              | alle Chip-IDs ausgelernt           |
| einzelne Chip-ID eingelernt                         | b'nnnnnn00110'                                                                              | 6           | 46             | 1E6            | 8                    | MSB (CRC) zuerst                                                                                          | erfolgreicher Programmierung durch Server oder Lernmodus                                  | keine                              |
| einzelne Chip-ID ausgelernt                         | b'nnnnnn00111'                                                                              | 7           | 47             | 1E7            | 8                    | MSB (CRC) zuerst                                                                                          | erfolgreicher Programmierung durch Server oder Lernmodus                                  | keine                              |
| alle Chip-IDs ausgelernt                            | b'nnnnnn00111'                                                                              | 7           | 47             | 1E7            | 0                    |                                                                                                           | erfolgreicher Programmierung durch Server oder Lernmodus                                  | keine                              |
| Admin-Chip-ID einlernen                             | b'nnnnnn11011'                                                                              | 27          | 5B             | 1FB            | 8                    | MSB (CRC) zuerst                                                                                          | Umprogrammierung am Server                                                                | Admin-Chip-ID eingelernt           |
| Admin-Chip-ID eingelernt                            | b'nnnnnn01011'                                                                              | 11          | 4B             | 1EB            | 8                    | MSB (CRC) zuerst                                                                                          | erfolgreicher Programmierung durch Server oder lokal am Gerät                             | keine                              |
|                                                     |                                                                                             | n           | 2              | 15             |                      |                                                                                                           |                                                                                           |                                    |
|                                                     | Prinzip:                                                                                    |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
|                                                     | Bit 4: 1= n ist Zieladresse, 0=n ist Absenderadresse, hat auch funktionelle Bedeutung, s.o. |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
|                                                     | Bits 5..10 (n): Teilnehmernummer . 0=Ziel ist Broadcast oder Server ist Absender            |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
| Filter RXF0                                         | b'n10000'                                                                                   |             |                |                | RXB0 (high priority) |                                                                                                           | Maske RXM0                                                                                | 0x7F0                              |
| Filter RXF1                                         | 0x010 (Broadcast)                                                                           |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
| Filter RXF2                                         | 0x002                                                                                       |             |                |                | RXB1 (low priority)  |                                                                                                           | Maske RXM1                                                                                | 0x01F                              |
| Filter RXF3                                         |                                                                                             |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
| Filter RXF4                                         |                                                                                             |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
| Filter RXF5                                         |                                                                                             |             |                |                |                      |                                                                                                           |                                                                                           |                                    |
