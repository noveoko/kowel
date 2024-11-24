# progress_tracker.py
import time
from focus_stacking.utils import format_time
from typing import List, Dict, Union, Tuple


class ProgressTracker:
    def __init__(self, total_phases: int = 3) -> None:
        self.total_phases = total_phases
        self.current_phase = 0
        self.phase_start_time = time.time()
        self.start_time = time.time()
        self.progress_history: List[Tuple[float, float]] = []
        self.history_window = 30
        self.phase_names = ["Optimizing", "Aligning", "Stacking"]
        self.phase_weights = [0.2, 0.4, 0.4]

    def next_phase(self) -> None:
        """Move to next phase"""
        self.current_phase = min(self.current_phase + 1, self.total_phases - 1)
        self.phase_start_time = time.time()
        self.progress_history.clear()

    def update_progress(self, phase_progress: float) -> Dict[str, Union[str, float]]:
        """Update progress and return time estimate"""
        current_time = time.time()
        self.progress_history.append((current_time, phase_progress))

        # Clean old history
        cutoff_time = current_time - self.history_window
        self.progress_history = [
            (t, p) for t, p in self.progress_history if t >= cutoff_time
        ]

        # Calculate speed and estimate
        if len(self.progress_history) >= 2:
            recent_progress = self.progress_history[-1][1] - self.progress_history[0][1]
            time_diff = self.progress_history[-1][0] - self.progress_history[0][0]
            if time_diff > 0 and recent_progress > 0:
                progress_per_second = recent_progress / time_diff
                remaining_in_phase = 100 - phase_progress
                phase_estimate = (
                    remaining_in_phase / progress_per_second
                    if progress_per_second > 0
                    else 0
                )

                # Calculate total progress across all phases
                total_progress = sum(
                    self.phase_weights[i]
                    * (
                        100
                        if i < self.current_phase
                        else (phase_progress if i == self.current_phase else 0)
                    )
                    for i in range(self.total_phases)
                )

                remaining_phases_time = sum(
                    self.phase_weights[i] * 100 * (1 / progress_per_second)
                    for i in range(self.current_phase + 1, self.total_phases)
                )

                total_estimate = phase_estimate + remaining_phases_time

                return {
                    "phase_name": self.phase_names[self.current_phase],
                    "phase_progress": phase_progress,
                    "phase_estimate": phase_estimate,
                    "total_progress": total_progress,
                    "total_estimate": total_estimate,
                    "elapsed": current_time - self.start_time,
                }

        return {
            "phase_name": self.phase_names[self.current_phase],
            "phase_progress": phase_progress,
            "phase_estimate": 0,
            "total_progress": sum(
                self.phase_weights[i]
                * (
                    100
                    if i < self.current_phase
                    else (phase_progress if i == self.current_phase else 0)
                )
                for i in range(self.total_phases)
            ),
            "total_estimate": 0,
            "elapsed": current_time - self.start_time,
        }
