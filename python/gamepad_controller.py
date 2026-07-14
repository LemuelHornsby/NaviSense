"""Gamepad controller for the NaviSense bridge.

Uses ``pygame.joystick`` so it works with Xbox, PlayStation, and generic
HID gamepads on Windows/macOS/Linux. Drop-in replacement for
:class:`python.demo_controller.DemoController` and
:class:`python.keyboard_controller.KeyboardController`.

Default Xbox mapping (PlayStation labels in parentheses):
    Left stick X             rudder (-max ... +max)
    Left stick Y (up=ahead)  throttle, both shafts
    Right stick X            bow thruster (-1 ... +1)
    LB / RB                  port / starboard shaft individual trim
    A (Cross)                zero all
    B (Circle)               ahead standard (70% RPM, rudder=0)
    X (Square)               hard port (-35 deg rudder)
    Y (Triangle)             hard starboard (+35 deg rudder)
    Start                    quit

Sticks use a deadzone + cubic-expo curve so small deflections produce
small commands, which matters for low-speed maneuvering. Override any
axis or button index by constructing :class:`GamepadControllerParams`
directly if your controller enumerates differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import pygame  # type: ignore
except ImportError:  # pragma: no cover
    pygame = None


@dataclass
class GamepadControllerParams:
    # ---- Command ranges ----
    max_rpm: float = 300.0
    max_rudder_deg: float = 35.0
    max_bow_thruster_norm: float = 1.0

    # ---- Stick shaping ----
    deadzone: float = 0.12           # absolute axis value below which stick is "centered"
    stick_expo: float = 0.35         # 0 = linear, 1 = fully cubic (more fine control near center)

    # ---- Preset behavior ----
    ahead_standard_rpm_frac: float = 0.70
    preset_rudder_deg: float = 35.0
    shaft_trim_increment: float = 10.0   # per-frame increment while bumper held

    # ---- Axis mapping (Xbox controller defaults under SDL/pygame) ----
    # Override if your controller enumerates axes differently.
    axis_rudder: int = 0             # left stick X
    axis_throttle: int = 1           # left stick Y (inverted -> up is -1)
    invert_throttle: bool = True
    axis_bow_thruster: int = 3       # right stick X (sometimes axis 2 depending on platform)

    # ---- Button mapping ----
    button_zero: int = 0             # A / Cross
    button_ahead_std: int = 1        # B / Circle
    button_hard_port: int = 2        # X / Square
    button_hard_starboard: int = 3   # Y / Triangle
    button_lb: int = 4               # port shaft trim
    button_rb: int = 5               # starboard shaft trim
    button_quit: int = 7             # Start

    # ---- HUD ----
    window_size: tuple = (460, 200)
    font_size: int = 16


@dataclass
class ControllerOutput:
    port_rpm_cmd: float
    starboard_rpm_cmd: float
    rudder_cmd_deg: float
    bow_thruster_cmd_norm: float
    mode: str


class GamepadController:
    """Stateful gamepad-driven controller.

    Maintains its own pygame joystick handle and a tiny HUD window. The
    HUD is only there for sanity feedback; it does not need focus for the
    pad to be polled.
    """

    def __init__(self, params: Optional[GamepadControllerParams] = None, joystick_index: int = 0) -> None:
        if pygame is None:
            raise ImportError("pygame not installed. Run: pip install pygame")

        self.params = params or GamepadControllerParams()
        self._closed = False

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            raise RuntimeError(
                "No gamepad detected. Plug one in and retry. "
                "On Windows, the controller should appear under 'Set up USB game controllers'."
            )

        self._joy = pygame.joystick.Joystick(joystick_index)
        self._joy.init()
        self._joy_name = self._joy.get_name()
        self._num_axes = self._joy.get_numaxes()
        self._num_buttons = self._joy.get_numbuttons()

        pygame.display.set_caption(f"NaviSense Gamepad — {self._joy_name}")
        self._screen = pygame.display.set_mode(self.params.window_size)
        self._font = pygame.font.SysFont("consolas", self.params.font_size)

        # Latched trim offsets applied on top of stick throttle.
        self._port_trim = 0.0
        self._starboard_trim = 0.0

        # Last computed output for the HUD.
        self._last = ControllerOutput(0.0, 0.0, 0.0, 0.0, "init")

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------
    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        if self._closed:
            return self._output(0.0, 0.0, 0.0, 0.0, "closed")

        self._pump_events()

        p = self.params

        # Raw stick axes.
        rudder_axis = self._axis(p.axis_rudder)
        throttle_axis = self._axis(p.axis_throttle)
        if p.invert_throttle:
            throttle_axis = -throttle_axis
        bow_axis = self._axis(p.axis_bow_thruster)

        # Shape each stick.
        rudder_shaped = self._shape(rudder_axis)
        throttle_shaped = self._shape(throttle_axis)
        bow_shaped = self._shape(bow_axis)

        # Held-bumper trim (per-frame increment). Only applied while pressed.
        # LB/RB let you bias a single shaft for docking-style maneuvers.
        if self._button(p.button_lb):
            self._port_trim = self._clamp(
                self._port_trim + p.shaft_trim_increment * 0.016,  # approx per-frame at 60 Hz
                -p.max_rpm, p.max_rpm,
            )
        if self._button(p.button_rb):
            self._starboard_trim = self._clamp(
                self._starboard_trim + p.shaft_trim_increment * 0.016,
                -p.max_rpm, p.max_rpm,
            )

        # Preset buttons (edge-triggered so holding doesn't spam).
        if self._button_edge(p.button_zero):
            self._zero_all()
        if self._button_edge(p.button_ahead_std):
            return self._apply_ahead_standard()
        if self._button_edge(p.button_hard_port):
            return self._apply_hard_rudder(-1.0)
        if self._button_edge(p.button_hard_starboard):
            return self._apply_hard_rudder(+1.0)
        if self._button_edge(p.button_quit):
            self._closed = True
            return self._output(0.0, 0.0, 0.0, 0.0, "closed")

        # Assemble commands.
        base_rpm = throttle_shaped * p.max_rpm
        port_rpm = self._clamp(base_rpm + self._port_trim, -p.max_rpm, p.max_rpm)
        starboard_rpm = self._clamp(base_rpm + self._starboard_trim, -p.max_rpm, p.max_rpm)
        rudder = rudder_shaped * p.max_rudder_deg
        bow = bow_shaped * p.max_bow_thruster_norm

        self._render(port_rpm, starboard_rpm, rudder, bow,
                     rudder_axis, throttle_axis, bow_axis)
        return self._output(port_rpm, starboard_rpm, rudder, bow, "auto")

    # ------------------------------------------------------------------
    # Input plumbing
    # ------------------------------------------------------------------
    def _pump_events(self) -> None:
        # Track button-press edges by comparing against the previous frame.
        self._prev_buttons = getattr(self, "_cur_buttons", [False] * self._num_buttons)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._closed = True
                return
        self._cur_buttons = [self._joy.get_button(i) == 1 for i in range(self._num_buttons)]

    def _axis(self, index: int) -> float:
        if index >= self._num_axes:
            return 0.0
        v = self._joy.get_axis(index)
        if abs(v) < self.params.deadzone:
            return 0.0
        # Rescale so (deadzone, 1) maps to (0, 1).
        sign = 1.0 if v > 0 else -1.0
        scaled = (abs(v) - self.params.deadzone) / (1.0 - self.params.deadzone)
        return self._clamp(sign * scaled, -1.0, 1.0)

    def _button(self, index: int) -> bool:
        return index < self._num_buttons and self._joy.get_button(index) == 1

    def _button_edge(self, index: int) -> bool:
        """True only on the frame the button was first pressed."""
        if index >= self._num_buttons:
            return False
        cur = getattr(self, "_cur_buttons", [False] * self._num_buttons)[index]
        prev = self._prev_buttons[index] if hasattr(self, "_prev_buttons") else False
        return cur and not prev

    def _shape(self, x: float) -> float:
        """Deadzoned value (already in [-1,1]) -> expo-shaped."""
        e = self.params.stick_expo
        return (1.0 - e) * x + e * (x * x * x)

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------
    def _apply_ahead_standard(self) -> ControllerOutput:
        p = self.params
        rpm = p.ahead_standard_rpm_frac * p.max_rpm
        self._port_trim = 0.0
        self._starboard_trim = 0.0
        out = self._output(rpm, rpm, 0.0, 0.0, "ahead_std")
        self._render(rpm, rpm, 0.0, 0.0, 0.0, p.ahead_standard_rpm_frac, 0.0)
        return out

    def _apply_hard_rudder(self, sign: float) -> ControllerOutput:
        p = self.params
        rud = sign * p.preset_rudder_deg
        # Hold current throttle (from stick) rather than zeroing.
        throttle_axis = self._axis(p.axis_throttle)
        if p.invert_throttle:
            throttle_axis = -throttle_axis
        rpm = self._shape(throttle_axis) * p.max_rpm
        out = self._output(rpm + self._port_trim, rpm + self._starboard_trim, rud, 0.0, "hard_rudder")
        self._render(rpm, rpm, rud, 0.0, 0.0, throttle_axis, 0.0)
        return out

    def _zero_all(self) -> None:
        self._port_trim = 0.0
        self._starboard_trim = 0.0

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _render(self, port_rpm, starboard_rpm, rudder_deg, bow_norm,
                rx, ry, rbx) -> None:
        self._screen.fill((10, 20, 30))
        lines = [
            f"Device: {self._joy_name}",
            "",
            f"Port RPM cmd:      {port_rpm:+7.1f}    trim {self._port_trim:+.1f}",
            f"Starboard RPM cmd: {starboard_rpm:+7.1f}    trim {self._starboard_trim:+.1f}",
            f"Rudder cmd [deg]:  {rudder_deg:+7.2f}",
            f"Bow thruster:      {bow_norm:+5.2f}",
            "",
            f"Axes  rudder={rx:+.2f}  throttle={ry:+.2f}  bow={rbx:+.2f}",
            "A=zero  B=ahead-std  X=hard-port  Y=hard-stbd  LB/RB=trim  Start=quit",
        ]
        y = 8
        for line in lines:
            surf = self._font.render(line, True, (220, 220, 220))
            self._screen.blit(surf, (10, y))
            y += self._font.get_height() + 2
        pygame.display.flip()

    def _output(self, pr, sr, rud, bt, mode) -> ControllerOutput:
        self._last = ControllerOutput(pr, sr, rud, bt, mode)
        return self._last

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))
