"""Summarize paired Skill experiments from recorded observations."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    success: bool
    accuracy: Annotated[float, Field(ge=0, le=1)]
    triggered: bool
    tokens: Annotated[int, Field(ge=0)]
    seconds: Annotated[float, Field(ge=0)]


class Trial(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[str, Field(min_length=1)]
    without_skill: Observation
    with_skill: Observation


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    runtime: Annotated[str, Field(min_length=1)]
    model: Annotated[str, Field(min_length=1)]
    skill_version: Annotated[str, Field(min_length=1)]
    trials: Annotated[list[Trial], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_trials(self):
        if len({trial.id for trial in self.trials}) != len(self.trials):
            raise ValueError("trial IDs must be unique")
        return self

    def summarize(self) -> dict:
        count = len(self.trials)
        groups = {}
        for arm in ("without_skill", "with_skill"):
            observations = [getattr(trial, arm) for trial in self.trials]
            groups[arm] = {
                "success_rate": sum(obs.success for obs in observations) / count,
                "accuracy": sum(obs.accuracy for obs in observations) / count,
                "trigger_rate": sum(obs.triggered for obs in observations) / count,
                "total_tokens": sum(obs.tokens for obs in observations),
                "mean_seconds": sum(obs.seconds / count for obs in observations),
            }
        return {
            "schema_version": 1,
            "runtime": self.runtime,
            "model": self.model,
            "skill_version": self.skill_version,
            "trial_count": count,
            **groups,
            "delta": {
                metric: value - groups["without_skill"][metric]
                for metric, value in groups["with_skill"].items()
            },
        }
