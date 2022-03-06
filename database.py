import hashlib
import os
import platform
import re
import sqlite3
import subprocess
from typing import List, Optional, Tuple

from classes import Runner, Commit, Config


class Database:
    def __init__(self,
                 config: Config,
                 final_components_hash: str,
                 bnchmrk_commit_hash: str,
                 gnrtr_commit_hash: str):
        db_file_name: str = 'bnchmrk_{}.db'.format(final_components_hash)
        self.db_file_path: str = os.path.join(config.database_dir, db_file_name)
        if not os.path.exists(self.db_file_path):
            self.connection = sqlite3.connect(self.db_file_path)
            cursor = self.connection.cursor()
            cursor.execute(
                '''
                CREATE TABLE meta
                (
                    key TEXT NOT NULL,
                    value TEXT NOT NULL
                )
                ''')
            cursor.execute(
                '''
                CREATE TABLE commits
                (
                    ID INTEGER NOT NULL PRIMARY KEY,
                    hash TEXT NOT NULL,
                    timepoint INTEGER NOT NULL
                )
                ''')
            cursor.execute(
                '''
                CREATE TABLE runners
                (
                    ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL
                )
                ''')
            cursor.execute(
                '''
                CREATE TABLE results
                (
                    commit_ID INTEGER NOT NULL,
                    runner_ID INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    time REAL NOT NULL,
                    FOREIGN KEY (commit_ID) REFERENCES commits (ID),
                    FOREIGN KEY (runner_ID) REFERENCES runners (ID)
                )
                ''')

            lsb_release: str = subprocess.run(['lsb_release', '-d'], stdout=subprocess.PIPE).stdout.decode('utf-8')
            lsb_release_match = re.search("Description:\s*(.+)", lsb_release)
            lsb_release = lsb_release_match.group(1) if lsb_release_match else 'unknown platform'
            kernel_release: str = subprocess.run(['uname', '-r'], stdout=subprocess.PIPE).stdout.decode('utf-8')[:-1]
            architecture: str = platform.machine()
            lscpu_output: str = subprocess.run(['lscpu'], stdout=subprocess.PIPE).stdout.decode('utf-8')
            cpu_name_match = re.search("Model name:\s*(.+)", lscpu_output)
            cpu_name: str = cpu_name_match.group(1) if cpu_name_match else 'unknown model name'
            cpus_amount_match = re.search("CPU\(s\):\s*(.+)", lscpu_output)
            cpus_amount: str = cpus_amount_match.group(1) if cpus_amount_match else 'unknown CPUs amount'
            max_threads: int = config.max_threads
            compilation_runs: int = config.compilation_runs
            benchmark_runs: int = config.benchmark_runs

            cursor.execute(
                '''
                INSERT INTO meta (key, value)
                VALUES
                    ('platform', '{lsb_release} {kernel_release}'),
                    ('architecture', '{architecture}'),
                    ('processor', '{processor_model_name} {processor_cpus_amount}'),
                    ('max threads', '{max_threads}'),
                    ('compilation runs', '{compilation_runs}'),
                    ('each benchmark runs', '{benchmark_runs}'),
                    ('fmt_bnchmrk commit', '{bnchmrk_commit_hash}'),
                    ('fmt_bnchmrk_gnrtr commit', '{gnrtr_commit_hash}');
                '''.format(
                    lsb_release=lsb_release,
                    kernel_release=kernel_release,
                    architecture=architecture,
                    processor_model_name=cpu_name,
                    processor_cpus_amount=cpus_amount,
                    max_threads=max_threads,
                    compilation_runs=compilation_runs,
                    benchmark_runs=benchmark_runs,
                    bnchmrk_commit_hash=bnchmrk_commit_hash,
                    gnrtr_commit_hash=gnrtr_commit_hash,
                ))
            self.connection.commit()
            self.connection.close()

    def __del__(self):
        pass

    def __enter__(self):
        self.connection = sqlite3.connect(self.db_file_path)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.connection.close()

    def has_table(self, table_name: str) -> bool:
        cursor = self.connection.cursor()
        exec_result = list(
            cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="{table_name}";'.format(
                table_name=table_name)))
        return len(exec_result) > 0

    def _get_identifier_(self, table_name: str, column_name: str, value: str) -> Optional[int]:
        cursor = self.connection.cursor()
        exec_result = cursor.execute(
            'SELECT ID FROM {table_name} WHERE {column_name} = "{value}";'.format(
                table_name=table_name,
                column_name=column_name,
                value=value
            ))
        for row in exec_result:
            return row[0]
        return None

    def _get_runner_identifier_(self, runner: Runner) -> Optional[int]:
        return self._get_identifier_("runners", "name", runner.name)

    def synchronize_runners(self, runners: List[Runner]):
        for runner in runners:
            identifier: Optional[int] = self._get_runner_identifier_(runner)
            if identifier is not None:
                runner.ID = identifier
                continue

            cursor = self.connection.cursor()
            cursor.execute(
                '''
                INSERT INTO runners (name, description)
                VALUES ('{name}', '{description}');
                '''.format(
                    name=runner.name,
                    description=runner.description
                ))
            runner.ID = cursor.lastrowid
        self.connection.commit()

    def _get_commit_identifier_(self, commit: Commit) -> Optional[int]:
        cursor = self.connection.cursor()
        exec_result = cursor.execute(
            'SELECT ID FROM commits WHERE ID = "{ID}";'.format(
                ID=commit.ID
            ))
        for row in exec_result:
            return row[0]
        return None

    def update_commits(self, commits: List[Commit]):
        for commit in commits:
            identifier: Optional[int] = self._get_commit_identifier_(commit)
            commit.is_processed = identifier is not None

    def has_results_for(self, commit: Commit, runner: Runner):
        cursor = self.connection.cursor()
        exec_result = cursor.execute(
            '''
            SELECT
                *
            FROM
                results
            WHERE
                commit_ID = {commit_ID} AND
                runner_ID = {runner_ID};
            '''.format(
                commit_ID=commit.ID,
                runner_ID=runner.ID
            ))
        return len(list(exec_result)) > 0

    def save_results(self, commit: Commit, runner: Runner, results: Optional[List[Tuple[str, float]]]):
        cursor = self.connection.cursor()
        cursor.execute(
            '''
            INSERT INTO commits (ID, hash, timepoint)
            VALUES ({ID}, '{hash}', {timepoint});
            '''.format(
                ID=commit.ID,
                hash=commit.hash,
                timepoint=commit.timepoint
            ))
        if results is not None:
            cursor.executemany(
                '''
                INSERT INTO results (commit_ID, runner_ID, name, time)
                VALUES ({commit_ID}, {runner_ID}, ?, ?);
                '''.format(
                    commit_ID=commit.ID,
                    runner_ID=runner.ID
                ), results)
        self.connection.commit()

    def calculate_hash(self) -> str:
        hash_md5 = hashlib.md5()
        with open(self.db_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def get_results_for(self, runner_id: int):
        cursor = self.connection.cursor()
        exec_result = cursor.execute(
            '''
            SELECT
                commits.hash AS commit_hash,
                commits.ID AS commit_ID,
                results.name AS result_name,
                results.time AS result_time
            FROM
                results
            INNER JOIN commits ON commits.ID = results.commit_ID
            INNER JOIN runners ON runners.ID = results.runner_ID
            WHERE
                runners.ID = '{runner_id}'
            ORDER BY
                commit_ID DESC;
            '''.format(
                runner_id=runner_id
            ))
        return list(exec_result)

    def get_meta_values(self) -> List[Tuple[str, str]]:
        cursor = self.connection.cursor()
        exec_result = cursor.execute(
            '''
            SELECT
                *
            FROM
                meta;
            ''')
        return list(exec_result)
