"""Abstract base class defining the fermentation subject interface."""

import abc


class FermentationSubject(abc.ABC):
    """
    Represents something that ferments (dough or starter).

    Subclasses encode the reference table mapping temperature to
    expected duration and target rise percentage.
    """

    @abc.abstractmethod
    def expected_hours(self, temp_f: float) -> float:
        """Expected fermentation duration at the given temperature (°F)."""

    @abc.abstractmethod
    def target_rise_pct(self, temp_f: float) -> float:
        """Target rise percentage to end fermentation at the given temperature."""
