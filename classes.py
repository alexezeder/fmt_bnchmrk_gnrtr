import os
import pickle
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
        self.is_processed: bool = False


class Config:
    default_max_threads: int = os.cpu_count()
    default_compilation_runs: int = 4
    default_compilations_pause: float = 0.5
    default_benchmark_runs: int = 2
    default_sleep_time: int = 60
    default_commit_bnchmrk_pages: bool = False
    default_website_output_dir: str = os.getcwd()
    default_database_dir: str = os.getcwd()
    default_skip_faulty_commits: bool = False

    def __init__(self, max_threads: int, compilation_runs: int, compilations_pause: float, benchmark_runs: int,
                 sleep_time: int, commit_bnchmrk_pages: bool, website_output_dir: str, database_dir: str,
                 skip_faulty_commits: bool):
        self.ID: Optional[int] = None
        self.max_threads: int = max_threads
        self.compilation_runs: int = compilation_runs
        self.compilations_pause: float = compilations_pause
        self.benchmark_runs: int = benchmark_runs
        self.sleep_time: int = sleep_time
        self.commit_bnchmrk_pages: bool = commit_bnchmrk_pages
        if commit_bnchmrk_pages:
            self.website_output_dir: Optional[str] = None
        else:
            self.website_output_dir: Optional[str] = website_output_dir
        self.database_dir: str = database_dir
        self.skip_faulty_commits: bool = skip_faulty_commits

    def as_bytes(self) -> bytes:
        return pickle.dumps(self)
