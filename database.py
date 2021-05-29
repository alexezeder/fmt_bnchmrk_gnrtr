import hashlib
import os
import sqlite3
from typing import List, Optional, Tuple

from classes import Runner, Commit


class Database:
    def __init__(self,
                 db_files_directory: str,
                 final_components_hash: str,
                 bnchmrk_commit_hash: str,
                 gnrtr_commit_hash: str):
        db_file_name: str = 'bnchmrk_{}.db'.format(final_components_hash)
        self.db_file_path: str = os.path.join(db_files_directory, db_file_name)
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
                    ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
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
            cursor.execute(
                '''
                INSERT INTO meta (key, value)
                VALUES
                    ('fmt_bnchmrk commit', '{bnchmrk_commit_hash}'),
                    ('fmt_bnchmrk_gnrtr commit', '{gnrtr_commit_hash}');
                '''.format(
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
        return self._get_identifier_("commits", "hash", commit.hash)

    def update_commits(self, commits: List[Commit]):
        for commit in commits:
            identifier: Optional[int] = self._get_commit_identifier_(commit)
            if identifier is not None:
                commit.ID = identifier
                continue

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
            INSERT INTO commits (hash, timepoint)
            VALUES ('{hash}', {timepoint});
            '''.format(
                hash=commit.hash,
                timepoint=commit.timepoint
            ))
        commit.ID = cursor.lastrowid
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
                commits.timepoint AS commit_timepoint,
                results.name AS result_name,
                results.time AS result_time
            FROM
                results
            INNER JOIN commits ON commits.ID = results.commit_ID
            INNER JOIN runners ON runners.ID = results.runner_ID
            WHERE
                runners.ID = '{runner_id}'
            ORDER BY
                commit_timepoint ASC;
            '''.format(
                runner_id=runner_id
            ))
        return list(exec_result)

    def get_meta_values(self) -> List[Tuple]:
        cursor = self.connection.cursor()
        exec_result = cursor.execute(
            '''
            SELECT
                *
            FROM
                meta;
            ''')
        return list(exec_result)
