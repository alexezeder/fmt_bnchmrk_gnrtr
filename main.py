#!/usr/bin/env python3
import glob
import hashlib
import json
import os
import re
import tempfile
import time
from typing import List, Tuple, Optional

import git
from docker import DockerClient, from_env, errors

from classes import Runner, Commit
from database import Database
from fmt_bnchmrk_git_repository import FmtBnchmrkRepo
from fmt_git_repository import FmtRepo
from site_generator import SiteGenerator
from tools import StepPrinter


def get_image_name_for_runner(runner_name: str) -> str:
    return 'fmt_bnchmrk:{}'.format(runner_name)


def get_stat_results(temp_dir_name: str) -> List[Tuple[str, float]]:
    results = list()
    compilation_time_total: float = 0.0
    files = glob.glob(os.path.join(temp_dir_name, 'compilation_time_*.txt'))
    for file_path in files:
        with open(file_path, 'r') as result_txt:
            lines = [line.rstrip() for line in result_txt]
            for line in lines:
                match = re.match(r"^real\t(\d+)m([\d.]+)s", line)
                if match:
                    minutes = float(match.group(1))
                    seconds = float(match.group(2))
                    compilation_time_total += seconds + minutes * 60
    compilation_time = compilation_time_total / len(files)
    results.append(('compilation_time', compilation_time))

    with open(os.path.join(temp_dir_name, 'static_library_size.txt'), 'r') as result_txt:
        library_size = int(result_txt.read())
        results.append(('static_library_size', library_size))

    with open(os.path.join(temp_dir_name, 'shared_library_size.txt'), 'r') as result_txt:
        library_size = int(result_txt.read())
        results.append(('shared_library_size', library_size))

    return results


def get_suites_results(temp_dir_name: str) -> List[Tuple[str, float]]:
    results = list()

    files = glob.glob(os.path.join(temp_dir_name, '*.json'))
    for file_path in files:
        with open(file_path, 'r') as results_json:
            parsed = json.load(results_json)
            for benchmark in parsed['benchmarks']:
                result_name = str(benchmark['name'])
                result_time = float(benchmark['real_time'])
                results.append((result_name, result_time))

    return results


def execute_task(docker_client: DockerClient, fmt_repo: FmtRepo, fmt_bnchmrk_repo: FmtBnchmrkRepo, commit: Commit,
                 runner: Runner) -> Optional[List[Tuple[str, float]]]:
    fmt_repo.set_current_commit(commit.hash)

    temp_dir = tempfile.TemporaryDirectory()
    temp_dir_name = temp_dir.name
    volumes = {
        fmt_repo.get_directory(): {'bind': '/fmt', 'mode': 'ro'},
        fmt_bnchmrk_repo.get_directory(): {'bind': '/benchmarks', 'mode': 'ro'},
        temp_dir_name: {'bind': '/output', 'mode': 'rw'}
    }

    try:
        docker_client.containers.run(get_image_name_for_runner(runner.name), detach=False, volumes=volumes)
    except errors.ContainerError:
        return None

    results = get_stat_results(temp_dir_name)
    results.extend(get_suites_results(temp_dir_name))
    return results


def main():
    with StepPrinter('Preparing fmt_bnchmrk repository'):
        fmt_bnchmrk_repo = FmtBnchmrkRepo()
    with StepPrinter('Preparing {fmt} repository'):
        fmt_repo = FmtRepo()
    with StepPrinter('Preparing site generator'):
        site_generator = SiteGenerator()
    with StepPrinter('Initializing Docker client'):
        docker_client = from_env()
    with StepPrinter('Preparing runners'):
        runner_directories = glob.glob('runners/*')
        runners: List[Runner] = list()
        for runner_directory in runner_directories:
            tag_name = os.path.basename(runner_directory)
            image = docker_client.images.build(path=runner_directory,
                                               tag=get_image_name_for_runner(tag_name),
                                               rm=True)[0]
            description = image.labels['description']
            runners.append(Runner(tag_name, description, image.id))

    with StepPrinter('Preparing components info'):
        bnchmrk_commit_hash: str = fmt_bnchmrk_repo.get_commit_hash()
        gnrtr_commit_hash: str = git.Repo('.').commit('HEAD').hexsha
        hash_md5 = hashlib.md5()
        hash_md5.update(bnchmrk_commit_hash.encode('utf-8'))
        hash_md5.update(gnrtr_commit_hash.encode('utf-8'))
        for runner in runners:
            hash_md5.update(runner.docker_ID.encode('utf-8'))
        final_components_hash: str = hash_md5.hexdigest()

    with StepPrinter('Preparing database'):
        db = Database('.', final_components_hash, bnchmrk_commit_hash, gnrtr_commit_hash)
    with db, StepPrinter('Synchronizing runners info with database'):
        db.synchronize_runners(runners)

    last_hash: str = ''
    while True:
        with StepPrinter('Updating {fmt} repository'):
            fmt_repo.update()
            commits = fmt_repo.get_available_commits()
        with db, StepPrinter('Updating commits info in database'):
            db.update_commits(commits)

        for commit in commits:
            for runner in runners:
                if commit.ID is not None:
                    continue
                with StepPrinter('Executing task on commit "{}" with runner "{}"'.format(commit.hash, runner.name)):
                    results = execute_task(docker_client, fmt_repo, fmt_bnchmrk_repo, commit, runner)
                with db, StepPrinter('Saving results to database'):
                    db.save_results(commit, runner, results)

            new_hash: str = db.calculate_hash()
            if last_hash != new_hash:
                temp_dir = tempfile.TemporaryDirectory()
                with db, StepPrinter('Generating website'):
                    site_generator.generate(db, fmt_repo, runners, temp_dir.name)
                    fmt_bnchmrk_repo.commit_pages(temp_dir.name)
                    last_hash = new_hash

        time.sleep(60)


if __name__ == '__main__':
    main()
