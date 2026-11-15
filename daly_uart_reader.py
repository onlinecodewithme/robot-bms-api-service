#!/usr/bin/env python3
"""
Daly BMS UART Reader (RS485/TTL via USB serial adapter)

Drop-in alternative to the BLE reader (daly_bms_reader.DalyBMSReader) that
talks the classic Daly 13-byte UART protocol over a USB-UART module
(e.g. CH340 at /dev/ttyUSB0, 9600 8N1).

Frame layout (both directions, 13 bytes):
    A5 <addr> <cmd> 08 <8 data bytes> <checksum = low byte of sum of first 12>
    addr 0x40 = host -> BMS (UART), BMS replies with addr 0x01.

Registers used:
    0x50  rated capacity (mAh) / nominal cell voltage (mV)   (read once)
    0x90  pack voltage, current, SOC
    0x91  max / min cell voltage and cell numbers
    0x92  max / min temperature and sensor numbers
    0x93  charge/discharge state, MOS status, BMS life, remaining mAh
    0x94  cell count, temp sensor count, charger/load, cycles
    0x95  cell voltages (3 cells per frame, ceil(cells/3) frames)
    0x96  temperatures (7 per frame, +40 offset)
    0x97  balance status bits                                 (optional)
    0x98  failure status bits                                 (optional)

It exposes the same public surface the background service uses with the BLE
reader (scan_for_bms / connect_to_bms / read_bms_data / create_json_output /
disconnect, plus .connected, .device and .client.is_connected) and emits the
same JSON document shape, so bms_api_service.py and bms_data_formatter.py
work unchanged.
"""

import asyncio
import json
import logging
import struct
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import serial

from daly_bms_reader import BMSData

logger = logging.getLogger(__name__)

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 9600
HOST_ADDR = 0x40   # host -> BMS over UART
BMS_ADDR = 0x01    # BMS -> host
FRAME_LEN = 13
CURRENT_OFFSET = 30000
TEMP_OFFSET = 40


@dataclass
class UARTDevice:
    """Minimal stand-in for a BLEDevice so the service loop can log it."""
    name: str
    address: str


def build_frame(cmd: int, addr: int = HOST_ADDR, data: bytes = bytes(8)) -> bytes:
    body = bytes([0xA5, addr, cmd, 0x08]) + data
    return body + bytes([sum(body) & 0xFF])


def frame_ok(frame: bytes, cmd: int) -> bool:
    return (len(frame) == FRAME_LEN
            and frame[0] == 0xA5
            and frame[1] == BMS_ADDR
            and frame[2] == cmd
            and frame[3] == 0x08
            and (sum(frame[:12]) & 0xFF) == frame[12])


def extract_frames(buf: bytes, cmd: int) -> List[bytes]:
    """Scan a byte buffer for valid frames of the given command (resyncs on
    garbage, e.g. if another process shares the port)."""
    frames = []
    i = 0
    while i + FRAME_LEN <= len(buf):
        if buf[i] == 0xA5 and frame_ok(buf[i:i + FRAME_LEN], cmd):
            frames.append(bytes(buf[i:i + FRAME_LEN]))
            i += FRAME_LEN
        else:
            i += 1
    return frames


class DalyUARTReader:
    """Daly BMS reader over a serial port, API-compatible with DalyBMSReader."""

    DEVICE_NAME = "Daly BMS (UART)"

    def __init__(self, port: str = DEFAULT_PORT, baudrate: int = DEFAULT_BAUD,
                 read_interval: float = 5.0, frame_timeout: float = 1.0,
                 **_ignored):
        self.port = port
        self.baudrate = baudrate
        self.read_interval = read_interval
        self.frame_timeout = frame_timeout
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.device: Optional[UARTDevice] = None
        self.last_response = bytearray()
        self.response_received = False
        self.rated_capacity_ah: Optional[float] = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.cell_count = 0
        self.temp_sensor_count = 0
        self.bms_data = BMSData(
            timestamp=int(time.time() * 1000),
            device_name=self.DEVICE_NAME,
            mac_address=port,
        )

    # --- compatibility shim: service loop checks reader.client.is_connected ---
    @property
    def client(self):
        return self

    @property
    def is_connected(self) -> bool:
        return self.serial is not None and self.serial.is_open and self.connected

    # ------------------------------------------------------------------ I/O
    def _query(self, cmd: int, expected_frames: int = 1,
               timeout: Optional[float] = None) -> List[bytes]:
        """Send one request and collect `expected_frames` valid reply frames.
        Returns whatever valid frames arrived before the timeout (may be [])."""
        if not self.serial:
            return []
        deadline = time.monotonic() + (timeout or self.frame_timeout)
        self.serial.reset_input_buffer()
        self.serial.write(build_frame(cmd))
        self.serial.flush()

        buf = bytearray()
        frames: List[bytes] = []
        while time.monotonic() < deadline:
            chunk = self.serial.read(FRAME_LEN * expected_frames)
            if chunk:
                buf.extend(chunk)
                frames = extract_frames(buf, cmd)
                if len(frames) >= expected_frames:
                    break
            elif frames:
                # inter-byte timeout elapsed and we already have something
                break
        if frames:
            self.last_response.extend(b"".join(frames))
        logger.debug("cmd 0x%02X -> %d/%d frames", cmd, len(frames), expected_frames)
        return frames

    # ----------------------------------------------------- service interface
    async def scan_for_bms(self) -> Optional[UARTDevice]:
        """'Scan' = check that the serial port exists."""
        import os
        if os.path.exists(self.port):
            self.device = UARTDevice(name=self.DEVICE_NAME, address=self.port)
            logger.info("Serial port present: %s", self.port)
            return self.device
        logger.warning("Serial port not found: %s", self.port)
        self.device = None
        return None

    async def connect_to_bms(self) -> bool:
        """Open the port and verify the BMS answers register 0x90."""
        try:
            self.serial = serial.Serial(
                self.port, self.baudrate, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                timeout=0.15, write_timeout=1.0,
            )
        except Exception as e:
            logger.error("Failed to open %s: %s", self.port, e)
            self.serial = None
            return False

        # Probe
        frames = await asyncio.to_thread(self._query, 0x90, 1)
        if not frames:
            logger.error("BMS did not answer on %s @ %d baud", self.port, self.baudrate)
            self.serial.close()
            self.serial = None
            return False

        self.connected = True
        self.bms_data.device_name = self.DEVICE_NAME
        self.bms_data.mac_address = self.port
        logger.info("*** Connected to Daly BMS over UART (%s @ %d) ***", self.port, self.baudrate)

        # Rated capacity is static: read it once.
        cap = await asyncio.to_thread(self._query, 0x50, 1)
        if cap:
            rated_mah, nominal_mv = struct.unpack(">II", cap[0][4:12])
            if rated_mah > 0:
                self.rated_capacity_ah = rated_mah / 1000.0
            logger.info("Rated capacity %.1f Ah, nominal cell %d mV",
                        rated_mah / 1000.0, nominal_mv)
        else:
            logger.warning("Register 0x50 (rated capacity) not answered; "
                           "total capacity will be estimated from SOC")
        return True

    async def read_bms_data(self) -> bool:
        if not self.is_connected:
            logger.error("Not connected to BMS")
            return False
        try:
            return await asyncio.to_thread(self._read_all)
        except serial.SerialException as e:
            logger.error("Serial error: %s", e)
            self.connected = False
            return False
        except Exception as e:
            logger.error("Error reading BMS data: %s", e)
            return False

    def _read_all(self) -> bool:
        self.last_response = bytearray()
        self.response_received = False
        d = self.bms_data

        # 0x90 pack voltage / current / SOC  (mandatory)
        f90 = self._query(0x90, 1)
        if not f90:
            self.consecutive_failures += 1
            logger.warning("No response to 0x90 (%d/%d)",
                           self.consecutive_failures, self.max_consecutive_failures)
            # Another process sharing the tty may have changed the line
            # settings (termios is per-device, not per-fd). Re-apply ours.
            try:
                self.serial.apply_settings({"baudrate": self.baudrate})
                self.serial.reset_input_buffer()
            except Exception as e:
                logger.warning("Could not re-apply serial settings: %s", e)
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.error("BMS silent for %d reads; closing port to force a reconnect",
                             self.consecutive_failures)
                self.connected = False
                try:
                    self.serial.close()
                except Exception:
                    pass
                self.serial = None
                self.consecutive_failures = 0
            return False
        self.consecutive_failures = 0
        pack_raw, _acq, cur_raw, soc_raw = struct.unpack(">HHHH", f90[0][4:12])
        d.timestamp = int(time.time() * 1000)
        d.pack_voltage = pack_raw / 10.0
        d.current = (cur_raw - CURRENT_OFFSET) / 10.0
        d.soc = soc_raw / 10.0

        # 0x94 status: cell count, temp sensor count, cycles
        f94 = self._query(0x94, 1)
        if f94:
            p = f94[0][4:12]
            self.cell_count = p[0]
            self.temp_sensor_count = p[1]
            d.cycles = struct.unpack(">H", p[5:7])[0]

        # 0x93 MOS / remaining capacity
        f93 = self._query(0x93, 1)
        charging_mos = discharging_mos = True
        if f93:
            p = f93[0][4:12]
            charging_mos = bool(p[1])
            discharging_mos = bool(p[2])
            d.remaining_capacity = struct.unpack(">I", p[4:8])[0] / 1000.0

        if self.rated_capacity_ah:
            d.total_capacity = self.rated_capacity_ah
        elif d.soc > 0 and d.remaining_capacity > 0:
            d.total_capacity = round(d.remaining_capacity * 100.0 / d.soc, 1)
        if not f93:
            d.remaining_capacity = round(d.total_capacity * d.soc / 100.0, 3)

        # 0x91 max/min cell voltage
        f91 = self._query(0x91, 1)
        if f91:
            p = f91[0][4:12]
            d.max_cell_voltage = struct.unpack(">H", p[0:2])[0]
            d.min_cell_voltage = struct.unpack(">H", p[3:5])[0]

        # 0x95 cell voltages
        n_cells = self.cell_count or 16
        n_frames = (n_cells + 2) // 3
        f95 = self._query(0x95, n_frames, timeout=max(self.frame_timeout, 0.25 * n_frames))
        cells: List[Dict[str, float]] = []
        by_frame = {fr[4]: fr for fr in f95}  # byte 4 = frame number (1-based)
        for idx in range(n_cells):
            frame_no, slot = divmod(idx, 3)
            fr = by_frame.get(frame_no + 1)
            if fr is None:
                continue
            mv = struct.unpack(">H", fr[5 + slot * 2:7 + slot * 2])[0]
            cells.append({"cellNumber": idx + 1, "voltage": round(mv / 1000.0, 3)})
        d.cell_voltages = cells
        if len(cells) != n_cells:
            logger.warning("Got %d of %d cell voltages", len(cells), n_cells)

        # 0x96 temperatures
        n_temps = self.temp_sensor_count or 2
        f96 = self._query(0x96, (n_temps + 6) // 7)
        temps: List[Dict[str, int]] = []
        by_frame = {fr[4]: fr for fr in f96}
        for idx in range(n_temps):
            frame_no, slot = divmod(idx, 7)
            fr = by_frame.get(frame_no + 1)
            if fr is None:
                continue
            raw = fr[5 + slot]
            if raw == 0xFF:
                continue
            temps.append({"sensor": f"T{idx + 1}", "temperature": raw - TEMP_OFFSET})
        d.temperatures = temps

        # 0x97 balance bits (optional; many firmwares don't answer)
        balancing = False
        f97 = self._query(0x97, 1, timeout=0.3)
        if f97:
            balancing = any(f97[0][4:12])

        d.mos_status = {
            "chargingMos": charging_mos,
            "dischargingMos": discharging_mos,
            "balancing": balancing,
        }
        d.data_valid = True
        self.response_received = True
        logger.info("BMS data parsed: %.1fV, %.1fA, %.1f%%, %d cells, %d temps",
                    d.pack_voltage, d.current, d.soc, len(cells), len(temps))
        return True

    def create_json_output(self) -> str:
        """Same document shape as DalyBMSReader.create_json_output()."""
        d = self.bms_data
        cmd90 = build_frame(0x90)
        f90 = extract_frames(self.last_response, 0x90)
        checksum = f"0x{f90[0][12]:02X}" if f90 else "0x00"
        output = {
            "timestamp": d.timestamp,
            "device": d.device_name,
            "mac_address": d.mac_address,
            "transport": "uart",
            "port": self.port,
            "baudrate": self.baudrate,
            "daly_protocol": {
                "status": "uart_connected" if self.is_connected else "disconnected",
                "notifications": "n/a",
                "commands": {
                    "main_info": {
                        "command_sent": cmd90.hex().upper(),
                        "response_received": self.response_received,
                        "response_data": self.last_response.hex(),
                        "parsed_data": {
                            "header": {
                                "startByte": "0xA5",
                                "commandId": "0x90",
                                "dataLength": 8,
                            },
                            "cellVoltages": d.cell_voltages,
                            "packVoltage": d.pack_voltage,
                            "current": d.current,
                            "soc": d.soc,
                            "remainingCapacity": d.remaining_capacity,
                            "totalCapacity": d.total_capacity,
                            "cycles": d.cycles,
                            "temperatures": d.temperatures,
                            "mosStatus": d.mos_status,
                            "maxCellVoltage": d.max_cell_voltage,
                            "minCellVoltage": d.min_cell_voltage,
                            "checksum": checksum,
                            "timestamp": str(d.timestamp),
                        },
                    }
                },
            },
            "data_found": d.data_valid,
        }
        return json.dumps(output, separators=(",", ":"))

    async def disconnect(self):
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
        self.serial = None
        self.connected = False
        logger.info("Serial port closed")

    async def run_continuous_reading(self):
        """Standalone loop: print BMS_DATA:<json> every read_interval."""
        try:
            while True:
                if not self.connected:
                    if await self.scan_for_bms() and await self.connect_to_bms():
                        pass
                    else:
                        await asyncio.sleep(5)
                        continue
                if await self.read_bms_data():
                    print(f"BMS_DATA:{self.create_json_output()}", flush=True)
                else:
                    logger.warning("Failed to read BMS data")
                await asyncio.sleep(self.read_interval)
        except KeyboardInterrupt:
            pass
        finally:
            await self.disconnect()


async def _main():
    import argparse
    ap = argparse.ArgumentParser(description="Daly BMS UART reader")
    ap.add_argument("--port", default=DEFAULT_PORT)
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--once", action="store_true", help="read once, print JSON, exit")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s - %(levelname)s - %(message)s")

    r = DalyUARTReader(port=args.port, baudrate=args.baud, read_interval=args.interval)
    if args.once:
        if await r.scan_for_bms() and await r.connect_to_bms() and await r.read_bms_data():
            print(json.dumps(json.loads(r.create_json_output()), indent=2))
            await r.disconnect()
            return 0
        await r.disconnect()
        return 1
    await r.run_continuous_reading()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
