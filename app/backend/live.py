"""Replay clock. The replayed year is streamed as if it were arriving now: the clock advances `speed` simulated hours per real second."""
from __future__ import annotations
import time
import pandas as pd


class LiveClock:
    def __init__(self, start: pd.Timestamp, end: pd.Timestamp, begin_after_days: int = 45, speed_h_per_s: float = 12.0):
        self.start, self.end = start, end
        self.t0 = start + pd.Timedelta(days=begin_after_days)          # begin with some history on screen
        self.sim = self.t0
        self.speed = speed_h_per_s
        self.playing = True
        self._wall = time.monotonic()

    def _advance(self):
        now = time.monotonic()
        if self.playing:
            self.sim = self.sim + pd.Timedelta(hours=(now - self._wall) * self.speed)
            if self.sim >= self.end:                                   # loop the year
                self.sim = self.start + pd.Timedelta(days=45)
        self._wall = now

    def now(self) -> pd.Timestamp:
        self._advance()
        return self.sim.floor("h")

    def state(self) -> dict:
        t = self.now()
        return dict(sim_time=str(t), playing=self.playing, speed_hours_per_second=self.speed, start=str(self.start), end=str(self.end),
                    progress=float((t - self.start) / (self.end - self.start)))

    def control(self, action: str, value=None):
        self._advance()
        if action == "play": self.playing = True
        elif action == "pause": self.playing = False
        elif action == "speed": self.speed = float(value)
        elif action == "seek": self.sim = min(max(pd.Timestamp(value), self.start + pd.Timedelta(days=2)), self.end - pd.Timedelta(hours=1))
        elif action == "reset": self.sim = self.t0
        return self.state()
