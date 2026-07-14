"""Free-running keyboard controller for the NaviSense bridge.

Opens a small pygame window that captures keyboard focus and emits
actuator commands on every ``step(t_sim, sensors)`` call. Drop-in
replacement for :class:`python.demo_controller.DemoController`.

Key map (while the pygame window has focus):
    W / S           increase / decrease both-shaft RPM command
    Shift+W / S     same, faster (10x increment)
    A / D           rudder port / starboard
    Q / E           bow thruster port / starboard
    SPACE           zero all commands
    R               quick-reset: RPM=0, rudder=0, bow thruster=0
    [ / ]           port shaft only  -/+
    ; / '           starboard shaft only  -/+
    ESC             quit (closes the window; controller falls back to idle)

The controller keeps state across calls -- the window does not need to be
focused every tick, but key events are only registered while it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

try:
    import pygame  # type: ignore
except ImportError:  # pragma: no cover
    pygame = None  # the listener will fall back to demo if this is None


@dataclass
class KeyboardControllerParams:
    rpm_increment: float = 10.0
    rudder_increment_deg: float = 1.0      # per key press; repeat keys apply continuously
    bow_thruster_increment: float = 0.05
    max_rpm: float = 300.0
    max_rudder_deg: float = 35.0
    window_size: tuple = (420, 160)
    font_size: int = 16


@dataclass
class ControllerOutput:
    port_rpm_cmd: float
    starboard_rpm_cmd: float
    rudder_cmd_deg: float
    bow_thruster_cmd_norm: float
    mode: str


class KeyboardController:
    """Stateful keyboard-driven controller."""

    def __init__(self, params: Optional[KeyboardControllerParams] = None) -> None:
        if pygame is None:
            raise ImportError("pygame not installed. Run: pip install pygame")

        self.params = params or KeyboardControllerParams()
        self._closed = False

        pygame.init()
        pygame.display.set_caption("NaviSense Keyboard Controller")
        self._screen = pygame.display.set_mode(self.params.window_size)
        self._font = pygame.font.SysFont("consolas", self.params.font_size)

        # Latched commands.
        self._port_cmd = 0.0
        self._starboard_cmd = 0.0
        self._rudder_cmd = 0.0
        self._bt_cmd = 0.0

    def step(self, t_sim: float, sensors: dict | None = None) -> ControllerOutput:
        if self._closed:
            return self._output("closed")

        self._pump_events()
        self._handle_held_keys()
        self._render()

        return self._output("auto")

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def _pump_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._closed = True
                return
            if event.type == pygame.KEYDOWN:
                k = event.key
                mods = pygame.key.get_mods()
                shift = bool(mods & pygame.KMOD_SHIFT)

                if k == pygame.K_ESCAPE:
                    self._closed = True
                elif k == pygame.K_SPACE:
                    self._zero_all()
                elif k == pygame.K_r:
                    self._zero_all()
                elif k == pygame.K_w:
                    step = self.params.rpm_increment * (10.0 if shift else 1.0)
                    self._port_cmd = self._clamp(self._port_cmd + step, -self.params.max_rpm, self.params.max_rpm)
                    self._starboard_cmd = self._clamp(self._starboard_cmd + step, -self.params.max_rpm, self.params.max_rpm)
                elif k == pygame.K_s:
                    step = self.params.rpm_increment * (10.0 if shift else 1.0)
                    self._port_cmd = self._clamp(self._port_cmd - step, -self.params.max_rpm, self.params.max_rpm)
                    self._starboard_cmd = self._clamp(self._starboard_cmd - step, -self.params.max_rpm, self.params.max_rpm)
                elif k == pygame.K_LEFTBRACKET:
                    self._port_cmd = self._clamp(self._port_cmd - self.params.rpm_increment, -self.params.max_rpm, self.params.max_rpm)
                elif k == pygame.K_RIGHTBRACKET:
                    self._port_cmd = self._clamp(self._port_cmd + self.params.rpm_increment, -self.params.max_rpm, self.params.max_rpm)
                elif k == pygame.K_SEMICOLON:
                    self._starboard_cmd = self._clamp(self._starboard_cmd - self.params.rpm_increment, -self.params.max_rpm, self.params.max_rpm)
                elif k == pygame.K_QUOTE:
                    self._starboard_cmd = self._clamp(self._starboard_cmd + self.params.rpm_increment, -self.params.max_rpm, self.params.max_rpm)

    def _handle_held_keys(self) -> None:
        """Rudder and bow thruster are continuous while held."""
        keys = pygame.key.get_pressed()
        p = self.params

        if keys[pygame.K_a]:
            self._rudder_cmd = self._clamp(self._rudder_cmd - p.rudder_increment_deg, -p.max_rudder_deg, p.max_rudder_deg)
        if keys[pygame.K_d]:
            self._rudder_cmd = self._clamp(self._rudder_cmd + p.rudder_increment_deg, -p.max_rudder_deg, p.max_rudder_deg)
        if keys[pygame.K_q]:
            self._bt_cmd = self._clamp(self._bt_cmd - p.bow_thruster_increment, -1.0, 1.0)
        if keys[pygame.K_e]:
            self._bt_cmd = self._clamp(self._bt_cmd + p.bow_thruster_increment, -1.0, 1.0)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render(self) -> None:
        self._screen.fill((10, 20, 30))
        lines = [
            f"Port RPM cmd:      {self._port_cmd:+7.1f}",
            f"Starboard RPM cmd: {self._starboard_cmd:+7.1f}",
            f"Rudder cmd [deg]:  {self._rudder_cmd:+7.2f}",
            f"Bow thruster:      {self._bt_cmd:+5.2f}",
            "",
            "W/S: throttle   A/D: rudder   Q/E: bow thruster   SPACE: zero",
        ]
        y = 10
        for line in lines:
            surf = self._font.render(line, True, (220, 220, 220))
            self._screen.blit(surf, (10, y))
            y += self._font.get_height() + 2
        pygame.display.flip()

    def _output(self, mode: str) -> ControllerOutput:
        return ControllerOutput(
            port_rpm_cmd=self._port_cmd,
            starboard_rpm_cmd=self._starboard_cmd,
            rudder_cmd_deg=self._rudder_cmd,
            bow_thruster_cmd_norm=self._bt_cmd,
            mode=mode,
        )

    def _zero_all(self) -> None:
        self._port_cmd = 0.0
        self._starboard_cmd = 0.0
        self._rudder_cmd = 0.0
        self._bt_cmd = 0.0

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))
