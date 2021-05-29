from typing import Optional

commits_number_limit: int = 100


class Runner:
    def __init__(self, name: str, description: str, docker_id: str):
        self.ID: Optional[int] = None
        self.name: str = name
        self.description: str = description
        self.docker_ID: str = docker_id


class Commit:
    def __init__(self, hash: str, timepoint: int):
        self.ID: Optional[int] = None
        self.hash: str = hash
        self.timepoint: int = timepoint
